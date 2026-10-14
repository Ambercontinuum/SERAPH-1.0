"""Manifold Constraint Closure for governed state transitions.

This layer models constraints as scoped relations over one proposed transition.
It deliberately does not model authority as a scalar, a global possession, or a
binary relation between classes of actors.

A frame is closed only when every required constraint has a valid observation
and resolves to ``PROVEN``. A refuted constraint and an unresolved constraint
remain different states so containment and recovery can respond differently,
even though neither may support a consequential commit.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable

from .manifold import content_digest


CONSTRAINT_FRAME_CONTRACT_VERSION = "1.0.0"

_CONSTRAINT_FRAME_CONTRACT_PROFILE: dict[str, Any] = {
    "name": "seraph.constraint-frame-evaluation",
    "version": CONSTRAINT_FRAME_CONTRACT_VERSION,
    "authority_scope": "event_local_commit",
    "resolution_values": ("proven", "refuted", "unresolved"),
    "resolution_precedence": ("refuted", "unresolved", "proven"),
    "closure_rule": "every_required_relation_is_proven",
    "frame_fields": (
        "frame_id",
        "topology_id",
        "topology_version",
        "transition_id",
        "required_relations",
        "observations",
    ),
    "observation_fields": (
        "name",
        "resolution",
        "scope",
        "horizon",
        "evidence_ref",
    ),
    "result_fields": (
        "resolution",
        "frame_id",
        "topology_id",
        "topology_version",
        "transition_id",
        "required_count",
        "proven",
        "refuted",
        "unresolved",
        "reason",
    ),
}


def constraint_frame_contract_descriptor() -> dict[str, Any]:
    """Return the public semantic descriptor used for compatibility review."""

    return dict(_CONSTRAINT_FRAME_CONTRACT_PROFILE)


def constraint_frame_contract_fingerprint() -> str:
    """Return the deterministic fingerprint of the public closure contract."""

    return content_digest(constraint_frame_contract_descriptor())


class ConstraintResolution(Enum):
    """Observed resolution of one scoped constraint."""

    PROVEN = "proven"
    REFUTED = "refuted"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class ConstraintObservation:
    """One constraint evaluated in a declared scope and consequence horizon."""

    name: str
    resolution: ConstraintResolution
    scope: str = "transition"
    horizon: str = "transition"
    evidence_ref: str | None = None

    def valid(self) -> bool:
        return (
            isinstance(self.name, str)
            and bool(self.name.strip())
            and isinstance(self.scope, str)
            and bool(self.scope.strip())
            and isinstance(self.horizon, str)
            and bool(self.horizon.strip())
            and isinstance(self.resolution, ConstraintResolution)
            and (
                self.evidence_ref is None
                or (
                    isinstance(self.evidence_ref, str)
                    and bool(self.evidence_ref.strip())
                )
            )
        )

    def to_wire(self) -> dict[str, Any]:
        """Return the canonical public representation of this observation."""

        return {
            "name": self.name,
            "resolution": self.resolution.value,
            "scope": self.scope,
            "horizon": self.horizon,
            "evidence_ref": self.evidence_ref,
        }


@dataclass(frozen=True)
class ConstraintFrame:
    """Versioned constraint graph slice for one transition.

    ``observations`` are nodes in the evaluated slice. Their names identify the
    constraint relations; ``scope`` and ``horizon`` state where and when each
    relation applies. Dependency edges belong to the compiled manifold and are
    represented here by the complete set of required observations for the
    transition being adjudicated.
    """

    frame_id: str
    topology_id: str
    topology_version: str
    transition_id: str
    required_relations: tuple[str, ...]
    observations: tuple[ConstraintObservation, ...]

    def valid(self) -> bool:
        names = [observation.name for observation in self.observations]
        return (
            isinstance(self.frame_id, str)
            and bool(self.frame_id.strip())
            and isinstance(self.topology_id, str)
            and bool(self.topology_id.strip())
            and isinstance(self.topology_version, str)
            and bool(self.topology_version.strip())
            and isinstance(self.transition_id, str)
            and bool(self.transition_id.strip())
            and bool(self.required_relations)
            and all(
                isinstance(name, str) and bool(name.strip())
                for name in self.required_relations
            )
            and len(self.required_relations) == len(set(self.required_relations))
            and len(names) == len(set(names))
            and all(observation.valid() for observation in self.observations)
        )

    def to_wire(self) -> dict[str, Any]:
        """Return the canonical public representation of this frame."""

        return {
            "frame_id": self.frame_id,
            "topology_id": self.topology_id,
            "topology_version": self.topology_version,
            "transition_id": self.transition_id,
            "required_relations": self.required_relations,
            "observations": tuple(
                observation.to_wire() for observation in self.observations
            ),
        }

    @property
    def digest(self) -> str:
        """Bind the complete frame, including its evidence resolutions."""

        return content_digest(self.to_wire())

    @classmethod
    def closed(
        cls,
        frame_id: str,
        *,
        topology_id: str = "seraph.public",
        topology_version: str = "1",
        transition_id: str | None = None,
        constraint_names: Iterable[str] = (
            "scope_alignment",
            "invocation_binding",
            "evidence_coverage",
            "consequence_coverage",
            "recovery_viability",
        ),
        evidence_ref: str = "declared-adapter-profile",
    ) -> "ConstraintFrame":
        """Build a closed declared frame for trusted local adapters and fixtures.

        This is a convenience constructor, not proof that an adapter's declared
        profile corresponds to reality. Production mediation must replace the
        declaration reference with independently bound evidence.
        """

        names = tuple(constraint_names)
        return cls(
            frame_id=frame_id,
            topology_id=topology_id,
            topology_version=topology_version,
            transition_id=transition_id or frame_id,
            required_relations=names,
            observations=tuple(
                ConstraintObservation(
                    name=name,
                    resolution=ConstraintResolution.PROVEN,
                    scope=topology_id,
                    evidence_ref=evidence_ref,
                )
                for name in names
            ),
        )


@dataclass(frozen=True)
class ConstraintResult:
    """Non-scalar closure result for a constraint frame."""

    resolution: ConstraintResolution
    frame_id: str
    topology_id: str
    topology_version: str
    transition_id: str
    required_count: int
    proven: tuple[str, ...]
    refuted: tuple[str, ...]
    unresolved: tuple[str, ...]
    reason: str

    @property
    def closed(self) -> bool:
        return self.resolution is ConstraintResolution.PROVEN

    def to_wire(self) -> dict[str, Any]:
        """Return the canonical public representation of this result."""

        return {
            "resolution": self.resolution.value,
            "frame_id": self.frame_id,
            "topology_id": self.topology_id,
            "topology_version": self.topology_version,
            "transition_id": self.transition_id,
            "required_count": self.required_count,
            "proven": self.proven,
            "refuted": self.refuted,
            "unresolved": self.unresolved,
            "reason": self.reason,
        }

    @property
    def digest(self) -> str:
        return content_digest(self.to_wire())


@dataclass(frozen=True)
class ConstraintEvaluationEnvelope:
    """Version-bound SERAPH result for one exact constraint frame.

    The envelope is transport data, not transferable authority.  Its result is
    useful only for the named topology version and transition, and consumers
    must verify the contract fingerprint and both content digests.
    """

    frame: ConstraintFrame
    result: ConstraintResult
    frame_digest: str
    result_digest: str
    contract_version: str = CONSTRAINT_FRAME_CONTRACT_VERSION
    contract_fingerprint: str = ""

    @classmethod
    def evaluate(cls, frame: ConstraintFrame) -> "ConstraintEvaluationEnvelope":
        result = evaluate_constraints(frame)
        return cls(
            frame=frame,
            result=result,
            frame_digest=frame.digest,
            result_digest=result.digest,
            contract_fingerprint=constraint_frame_contract_fingerprint(),
        )

    def valid(self) -> bool:
        if (
            self.contract_version != CONSTRAINT_FRAME_CONTRACT_VERSION
            or self.contract_fingerprint != constraint_frame_contract_fingerprint()
            or not isinstance(self.frame, ConstraintFrame)
            or not self.frame.valid()
            or not isinstance(self.result, ConstraintResult)
            or self.frame_digest != self.frame.digest
            or self.result_digest != self.result.digest
        ):
            return False
        return self.result == evaluate_constraints(self.frame)

    @property
    def closed(self) -> bool:
        return self.valid() and self.result.closed

    def to_wire(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "contract_fingerprint": self.contract_fingerprint,
            "frame": self.frame.to_wire(),
            "result": self.result.to_wire(),
            "frame_digest": self.frame_digest,
            "result_digest": self.result_digest,
        }

    @property
    def digest(self) -> str:
        return content_digest(self.to_wire())


def evaluate_constraints(frame: ConstraintFrame) -> ConstraintResult:
    """Evaluate closure without scalar aggregation or actor-class privilege."""

    if not isinstance(frame, ConstraintFrame) or not frame.valid():
        return ConstraintResult(
            resolution=ConstraintResolution.UNRESOLVED,
            frame_id=getattr(frame, "frame_id", "invalid"),
            topology_id=getattr(frame, "topology_id", "invalid"),
            topology_version=getattr(frame, "topology_version", "invalid"),
            transition_id=getattr(frame, "transition_id", "invalid"),
            required_count=0,
            proven=(),
            refuted=(),
            unresolved=("invalid_constraint_frame",),
            reason="constraint_frame_invalid",
        )

    by_name = {
        observation.name: observation
        for observation in frame.observations
    }
    proven = tuple(
        name
        for name in frame.required_relations
        if name in by_name
        and by_name[name].resolution is ConstraintResolution.PROVEN
    )
    refuted = tuple(
        name
        for name in frame.required_relations
        if name in by_name
        and by_name[name].resolution is ConstraintResolution.REFUTED
    )
    unresolved = tuple(
        name
        for name in frame.required_relations
        if name not in by_name
        or by_name[name].resolution is ConstraintResolution.UNRESOLVED
    )

    if refuted:
        resolution = ConstraintResolution.REFUTED
        reason = "constraint_refuted"
    elif unresolved:
        resolution = ConstraintResolution.UNRESOLVED
        reason = "constraint_unresolved"
    else:
        resolution = ConstraintResolution.PROVEN
        reason = "constraint_frame_closed"

    return ConstraintResult(
        resolution=resolution,
        frame_id=frame.frame_id,
        topology_id=frame.topology_id,
        topology_version=frame.topology_version,
        transition_id=frame.transition_id,
        required_count=len(frame.required_relations),
        proven=proven,
        refuted=refuted,
        unresolved=unresolved,
        reason=reason,
    )
