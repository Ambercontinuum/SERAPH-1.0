"""Immutable registered-tool router over the certified execution membrane."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from types import MappingProxyType
from threading import Lock
from typing import Any, Callable

from seraph import (
    HashChainJournal,
    ManifoldState,
    TransitionProposal,
    content_digest,
)

from .certified_tool_guard import (
    CertifiedExecution,
    CertifiedToolGuard,
    ExecutionBindingError,
    ExecutionPermit,
    ExecutionPermitRejected,
    PostconditionDivergence,
    bind_execution,
    executable_digest,
)


class CapabilityRegistryError(ValueError):
    """Capability declarations are invalid, ambiguous, or mutable."""


class CapabilityDenied(PermissionError):
    """The requested tool or effects exceed the registered capability."""


@dataclass(frozen=True)
class CapabilityScope:
    """Functional effects one registered tool is allowed to propose."""

    coordinate: str
    subject_ids: tuple[str, ...] = ()
    subject_roles: tuple[str, ...] = ()

    def valid(self) -> bool:
        return (
            isinstance(self.coordinate, str)
            and bool(self.coordinate.strip())
            and bool(self.subject_ids or self.subject_roles)
            and all(
                isinstance(item, str) and bool(item.strip())
                for item in (*self.subject_ids, *self.subject_roles)
            )
            and len(set(self.subject_ids)) == len(self.subject_ids)
            and len(set(self.subject_roles)) == len(self.subject_roles)
        )

    def matches(
        self,
        subject_id: str,
        coordinate: str,
        state: ManifoldState,
    ) -> bool:
        entity = state.entity_map().get(subject_id)
        if entity is None or coordinate != self.coordinate:
            return False
        return (
            (not self.subject_ids or subject_id in self.subject_ids)
            and (
                not self.subject_roles
                or any(role in entity.roles for role in self.subject_roles)
            )
        )


@dataclass(frozen=True)
class RegisteredCapability:
    """One immutable tool registration and its maximum functional scope."""

    capability_id: str
    fn: Callable[..., Any]
    scopes: tuple[CapabilityScope, ...]
    allow_no_effects: bool = False

    def valid(self) -> bool:
        return (
            isinstance(self.capability_id, str)
            and bool(self.capability_id.strip())
            and callable(self.fn)
            and bool(self.scopes or self.allow_no_effects)
            and all(scope.valid() for scope in self.scopes)
            and isinstance(self.allow_no_effects, bool)
        )


class CapabilityRegistry:
    """Content-addressed registry that cannot be mutated after construction."""

    def __init__(self, capabilities: tuple[RegisteredCapability, ...]):
        if not capabilities or not all(
            capability.valid() for capability in capabilities
        ):
            raise CapabilityRegistryError("invalid capability registry")
        ids = [capability.capability_id for capability in capabilities]
        if len(set(ids)) != len(ids):
            raise CapabilityRegistryError("duplicate capability id")

        entries: dict[str, RegisteredCapability] = {}
        fingerprints: dict[str, str] = {}
        descriptors: list[dict[str, Any]] = []
        for capability in capabilities:
            try:
                fingerprint = executable_digest(capability.fn)
            except ExecutionBindingError as exc:
                raise CapabilityRegistryError(
                    f"unbound capability:{capability.capability_id}"
                ) from exc
            entries[capability.capability_id] = capability
            fingerprints[capability.capability_id] = fingerprint
            descriptors.append(
                {
                    "capability_id": capability.capability_id,
                    "executable_digest": fingerprint,
                    "scopes": tuple(
                        asdict(scope)
                        for scope in capability.scopes
                    ),
                    "allow_no_effects": capability.allow_no_effects,
                }
            )

        self._entries = MappingProxyType(entries)
        self._fingerprints = MappingProxyType(fingerprints)
        self.digest = content_digest(
            {"capabilities": tuple(sorted(
                descriptors,
                key=lambda item: item["capability_id"],
            ))}
        )

    @property
    def capability_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._entries))

    def resolve(self, capability_id: str) -> RegisteredCapability:
        try:
            return self._entries[capability_id]
        except KeyError as exc:
            raise CapabilityDenied("unknown capability") from exc

    def executable_unchanged(self, capability_id: str) -> bool:
        capability = self.resolve(capability_id)
        try:
            current = executable_digest(capability.fn)
        except ExecutionBindingError:
            return False
        return current == self._fingerprints[capability_id]


@dataclass(frozen=True)
class CapabilityPermit:
    """Public opaque handle; executable details remain inside the runtime."""

    token: str
    registry_digest: str
    capability_id: str
    call_digest: str
    proposal_digest: str


@dataclass(frozen=True)
class CapabilityExecution:
    capability_id: str
    execution: CertifiedExecution
    audit_head: str


@dataclass(frozen=True)
class _PendingCapability:
    public_permit: CapabilityPermit
    inner_permit: ExecutionPermit
    capability: RegisteredCapability
    proposal: TransitionProposal
    call_args: tuple[Any, ...]
    call_kwargs: dict[str, Any]


@dataclass
class CapabilityRuntime:
    """Route all known execution through immutable registered capabilities."""

    registry: CapabilityRegistry
    guard: CertifiedToolGuard
    journal: HashChainJournal = field(default_factory=HashChainJournal)
    _pending: dict[str, _PendingCapability] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )
    _lock: Lock = field(default_factory=Lock, init=False, repr=False)

    def authorize(
        self,
        capability_id: str,
        proposal: TransitionProposal,
        call_args: tuple[Any, ...] = (),
        call_kwargs: dict[str, Any] | None = None,
    ) -> CapabilityPermit:
        """Admit a registered tool without returning the callable."""

        kwargs = {} if call_kwargs is None else dict(call_kwargs)
        self.journal.append(
            "capability.authorization_requested",
            {
                "registry_digest": self.registry.digest,
                "capability_id": capability_id,
                "proposal_id": proposal.proposal_id,
            },
        )

        # Every declared effect must fit the immutable scope of
        # the registered callable before the manifold sees the transition.
        with self._lock:
            try:
                capability = self.registry.resolve(capability_id)
                if not self.registry.executable_unchanged(capability_id):
                    raise CapabilityDenied(
                        "registered executable changed after registry freeze"
                    )
                bound = bind_execution(
                    proposal,
                    capability.fn,
                    call_args,
                    kwargs,
                )
                if (
                    proposal.execution_binding
                    and proposal.execution_binding
                    != bound.execution_binding
                ):
                    raise CapabilityDenied(
                        "proposal is bound to a different executable"
                    )
                inner = self.guard.authorize(
                    capability.fn,
                    bound,
                    call_args,
                    kwargs,
                    state_validator=lambda state: self._validate_scope(
                        capability,
                        bound,
                        state,
                    ),
                )
            except (
                CapabilityDenied,
                ExecutionBindingError,
                ExecutionPermitRejected,
            ) as exc:
                self.journal.append(
                    "capability.authorization_denied",
                    {
                        "registry_digest": self.registry.digest,
                        "capability_id": capability_id,
                        "proposal_id": proposal.proposal_id,
                        "reason_type": type(exc).__name__,
                    },
                )
                if isinstance(exc, CapabilityDenied):
                    raise
                raise CapabilityDenied(str(exc)) from exc

            public = CapabilityPermit(
                token=inner.token,
                registry_digest=self.registry.digest,
                capability_id=capability_id,
                call_digest=inner.call_digest,
                proposal_digest=inner.proposal_digest,
            )
            self._pending[public.token] = _PendingCapability(
                public_permit=public,
                inner_permit=inner,
                capability=capability,
                proposal=bound,
                call_args=call_args,
                call_kwargs=kwargs,
            )
            self.journal.append(
                "capability.authorized",
                {
                    "registry_digest": self.registry.digest,
                    "capability_id": capability_id,
                    "call_digest": public.call_digest,
                    "proposal_digest": public.proposal_digest,
                    "permit_digest": content_digest(public),
                },
            )
            return public

    def execute(self, permit: CapabilityPermit) -> CapabilityExecution:
        """Consume an opaque permit and execute only its registered tool."""

        # The caller cannot supply a callable at execution time, and a failed,
        # altered, or replayed handle cannot regain admission.
        with self._lock:
            pending = self._pending.pop(permit.token, None)
            if pending is None or pending.public_permit != permit:
                self.journal.append(
                    "capability.permit_rejected",
                    {
                        "registry_digest": self.registry.digest,
                        "capability_id": permit.capability_id,
                        "permit_digest": content_digest(permit),
                    },
                )
                raise CapabilityDenied("capability permit is invalid or consumed")
            if (
                permit.registry_digest != self.registry.digest
                or not self.registry.executable_unchanged(permit.capability_id)
            ):
                self.journal.append(
                    "capability.execution_denied",
                    {
                        "registry_digest": self.registry.digest,
                        "capability_id": permit.capability_id,
                        "reason": "registry_or_executable_changed",
                    },
                )
                raise CapabilityDenied(
                    "registry or executable changed before execution"
                )
            self.journal.append(
                "capability.permit_consumed",
                {
                    "registry_digest": self.registry.digest,
                    "capability_id": permit.capability_id,
                    "permit_digest": content_digest(permit),
                },
            )

        try:
            execution = self.guard.execute(
                pending.inner_permit,
                pending.capability.fn,
                pending.proposal,
                pending.call_args,
                pending.call_kwargs,
            )
        except PostconditionDivergence as exc:
            self.journal.append(
                "capability.execution_diverged",
                {
                    "registry_digest": self.registry.digest,
                    "capability_id": permit.capability_id,
                    "realized_state_digest": (
                        exc.report.realized_state_digest
                    ),
                    "expected_state_digest": (
                        exc.report.expected_state_digest
                    ),
                },
            )
            raise
        except ExecutionPermitRejected as exc:
            self.journal.append(
                "capability.execution_denied",
                {
                    "registry_digest": self.registry.digest,
                    "capability_id": permit.capability_id,
                    "reason_type": type(exc).__name__,
                },
            )
            raise CapabilityDenied(str(exc)) from exc
        except BaseException as exc:
            self.journal.append(
                "capability.tool_error",
                {
                    "registry_digest": self.registry.digest,
                    "capability_id": permit.capability_id,
                    "error_type": type(exc).__name__,
                },
            )
            raise

        event = self.journal.append(
            "capability.executed",
            {
                "registry_digest": self.registry.digest,
                "capability_id": permit.capability_id,
                "call_digest": permit.call_digest,
                "proposal_digest": permit.proposal_digest,
                "realized_state_digest": (
                    execution.realization.realized_state_digest
                ),
            },
        )
        return CapabilityExecution(
            capability_id=permit.capability_id,
            execution=execution,
            audit_head=event.event_hash,
        )

    @staticmethod
    def _validate_scope(
        capability: RegisteredCapability,
        proposal: TransitionProposal,
        state: ManifoldState,
    ) -> None:
        if not proposal.effects and not capability.allow_no_effects:
            raise CapabilityDenied("capability requires declared effects")
        for effect in proposal.effects:
            if not any(
                scope.matches(
                    effect.subject_id,
                    effect.coordinate,
                    state,
                )
                for scope in capability.scopes
            ):
                raise CapabilityDenied(
                    "proposed effect exceeds capability scope"
                )
