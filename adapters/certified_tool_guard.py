"""One-use, exact-call execution membrane for compiled manifold transitions.

This adapter is the migration path away from semantic function-name risk
classification.  It binds a manifold proof to the executable's code, exact
arguments, current functional state, and independently observed target state.

It does not sandbox arbitrary Python.  Effect confinement still belongs to the
deployment environment.  What this adapter provides is a non-reusable permit,
fresh adjudication immediately before execution, local serialization, and
postcondition divergence detection before the result can propagate.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from hashlib import sha256
import marshal
from secrets import token_urlsafe
from threading import Lock
from typing import Any, Callable

from seraph import (
    CompiledManifold,
    GovernanceInput,
    InvariantCertificate,
    ManifoldGovernanceDecision,
    ManifoldState,
    RealizationReport,
    TransitionProposal,
    content_digest,
    govern_transition,
)

from .tool_guard import SAFE_DECISIONS


class ExecutionBindingError(ValueError):
    """The callable or its arguments cannot be bound reproducibly."""


class ExecutionPermitRejected(PermissionError):
    """A permit is missing, stale, reused, or bound to a different call."""


class PostconditionDivergence(RuntimeError):
    """Execution completed but the observed result diverged from its proof."""

    def __init__(self, report: RealizationReport):
        self.report = report
        super().__init__(
            "certified execution diverged: "
            + ", ".join(report.reasons or ("unknown_divergence",))
        )


def _callable_payload(fn: Callable[..., Any]) -> dict[str, Any]:
    target = getattr(fn, "__func__", fn)
    code = getattr(target, "__code__", None)
    module = getattr(target, "__module__", None)
    qualname = getattr(target, "__qualname__", None)
    if (
        code is None
        or not isinstance(module, str)
        or not module
        or not isinstance(qualname, str)
        or not qualname
    ):
        raise ExecutionBindingError(
            "callable must expose Python code, module, and qualified name"
        )
    try:
        code_digest = sha256(marshal.dumps(code)).hexdigest()
    except (TypeError, ValueError) as exc:
        raise ExecutionBindingError("callable code is not reproducible") from exc
    payload: dict[str, Any] = {
        "module": module,
        "qualname": qualname,
        "code_digest": code_digest,
        "defaults": getattr(target, "__defaults__", None),
        "keyword_defaults": getattr(target, "__kwdefaults__", None),
    }
    closure = getattr(target, "__closure__", None)
    payload["closure"] = (
        tuple(cell.cell_contents for cell in closure)
        if closure
        else ()
    )

    receiver = getattr(fn, "__self__", None)
    if receiver is not None:
        receiver_binding = getattr(receiver, "__seraph_binding__", None)
        if callable(receiver_binding):
            receiver_binding = receiver_binding()
        if receiver_binding is None:
            raise ExecutionBindingError(
                "bound callable receiver must declare __seraph_binding__"
            )
        payload["receiver"] = receiver_binding
    return payload


def execution_call_digest(
    fn: Callable[..., Any],
    call_args: tuple[Any, ...] = (),
    call_kwargs: dict[str, Any] | None = None,
) -> str:
    """Bind executable code and exact arguments to a stable digest.

    Arguments must be representable by SERAPH's canonical data encoder.
    Unsupported opaque objects fail closed instead of falling back to ``repr``.
    """

    kwargs = {} if call_kwargs is None else call_kwargs
    if not isinstance(call_args, tuple) or not isinstance(kwargs, dict):
        raise ExecutionBindingError("call arguments must be tuple/dict")
    if any(not isinstance(key, str) for key in kwargs):
        raise ExecutionBindingError("keyword names must be strings")
    try:
        return content_digest(
            {
                "callable": _callable_payload(fn),
                "args": call_args,
                "kwargs": kwargs,
            }
        )
    except ExecutionBindingError:
        raise
    except (TypeError, ValueError) as exc:
        raise ExecutionBindingError(
            "call arguments are not canonically serializable"
        ) from exc


def executable_digest(fn: Callable[..., Any]) -> str:
    """Return the code/defaults/closure/receiver digest for a callable."""

    try:
        return content_digest({"callable": _callable_payload(fn)})
    except ExecutionBindingError:
        raise
    except (TypeError, ValueError) as exc:
        raise ExecutionBindingError(
            "callable is not canonically reproducible"
        ) from exc


def bind_execution(
    proposal: TransitionProposal,
    fn: Callable[..., Any],
    call_args: tuple[Any, ...] = (),
    call_kwargs: dict[str, Any] | None = None,
) -> TransitionProposal:
    """Return a proposal bound to one exact executable call."""

    return replace(
        proposal,
        execution_binding=execution_call_digest(fn, call_args, call_kwargs),
    )


@dataclass(frozen=True)
class ExecutionPermit:
    """Opaque, one-use admission token for one certified call."""

    token: str
    call_digest: str
    proposal_digest: str
    certificate: InvariantCertificate
    adjudication: ManifoldGovernanceDecision


@dataclass(frozen=True)
class CertifiedExecution:
    """Result released only after the realized state matches the certificate."""

    result: Any
    permit: ExecutionPermit
    realization: RealizationReport


@dataclass
class CertifiedToolGuard:
    """Serialize, certify, execute, and verify functional tool transitions."""

    compiled: CompiledManifold
    state_reader: Callable[[], ManifoldState]
    governance_input_reader: Callable[[], GovernanceInput]
    on_divergence: Callable[[RealizationReport], None] | None = None
    _permits: dict[str, ExecutionPermit] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )
    _execution_lock: Lock = field(
        default_factory=Lock,
        init=False,
        repr=False,
    )

    def authorize(
        self,
        fn: Callable[..., Any],
        proposal: TransitionProposal,
        call_args: tuple[Any, ...] = (),
        call_kwargs: dict[str, Any] | None = None,
        state_validator: Callable[[ManifoldState], None] | None = None,
    ) -> ExecutionPermit:
        """Issue a one-use permit after single-snapshot validation.

        ``state_validator`` lets a higher-level capability adapter validate
        additional scope against the exact state snapshot used for manifold
        and SERAPH adjudication.  It runs while the execution lock is held.
        """

        call_digest = execution_call_digest(fn, call_args, call_kwargs)
        if not proposal.execution_binding:
            raise ExecutionPermitRejected("proposal has no execution binding")
        if proposal.execution_binding != call_digest:
            raise ExecutionPermitRejected(
                "proposal is bound to a different executable call"
            )

        # Code, arguments, functional effects, origin, state, and evidence
        # share one proof.
        with self._execution_lock:
            state = self.state_reader()
            if state_validator is not None:
                state_validator(state)
            adjudication = govern_transition(
                self.compiled,
                state,
                proposal,
                self.governance_input_reader(),
            )
            if (
                not adjudication.manifold_proven
                or adjudication.governance.decision not in SAFE_DECISIONS
            ):
                reasons = (
                    adjudication.certificate.reasons
                    or adjudication.governance.reasons
                    or ("transition_not_admissible",)
                )
                raise ExecutionPermitRejected(
                    "certified execution denied: " + ", ".join(reasons)
                )

            permit = ExecutionPermit(
                token=token_urlsafe(32),
                call_digest=call_digest,
                proposal_digest=adjudication.certificate.proposal_digest,
                certificate=adjudication.certificate,
                adjudication=adjudication,
            )
            self._permits[permit.token] = permit
            return permit

    def execute(
        self,
        permit: ExecutionPermit,
        fn: Callable[..., Any],
        proposal: TransitionProposal,
        call_args: tuple[Any, ...] = (),
        call_kwargs: dict[str, Any] | None = None,
    ) -> CertifiedExecution:
        """Consume a permit, re-adjudicate fresh state, and verify realization."""

        kwargs = {} if call_kwargs is None else call_kwargs
        call_digest = execution_call_digest(fn, call_args, kwargs)

        # This lock serializes this guard's admission and
        # execution paths.  The permit is consumed before any call attempt and
        # the state is re-adjudicated while the same lock remains held.
        with self._execution_lock:
            stored = self._permits.pop(permit.token, None)
            if stored is None:
                raise ExecutionPermitRejected("permit is unknown or already used")
            if stored != permit:
                raise ExecutionPermitRejected("permit contents do not match issuer")
            if call_digest != permit.call_digest:
                raise ExecutionPermitRejected(
                    "permit is bound to different code or arguments"
                )
            if proposal.execution_binding != call_digest:
                raise ExecutionPermitRejected(
                    "transition execution binding changed"
                )

            current_state = self.state_reader()
            fresh = govern_transition(
                self.compiled,
                current_state,
                proposal,
                self.governance_input_reader(),
            )
            if (
                fresh.certificate != permit.certificate
                or fresh.governance != permit.adjudication.governance
                or not fresh.manifold_proven
                or fresh.governance.decision not in SAFE_DECISIONS
            ):
                raise ExecutionPermitRejected(
                    "permit became stale before execution"
                )

            try:
                result = fn(*call_args, **kwargs)
            except BaseException as exc:
                report = self.compiled.verify_realization(
                    permit.certificate,
                    self.state_reader(),
                )
                if not report.matches:
                    self._contain(report)
                    raise PostconditionDivergence(report) from exc
                raise

            # The result is not returned until an independently
            # supplied realized state matches the certificate.
            report = self.compiled.verify_realization(
                permit.certificate,
                self.state_reader(),
            )
            if not report.matches:
                self._contain(report)
                raise PostconditionDivergence(report)
            return CertifiedExecution(
                result=result,
                permit=permit,
                realization=report,
            )

    def _contain(self, report: RealizationReport) -> None:
        if self.on_divergence is not None:
            self.on_divergence(report)
