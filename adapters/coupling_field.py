"""Coupling Field adapter for SERAPH enforcement.

Implements the ψ-field (Psi Field) coupling dynamics from Anson (2026),
"AI Coupling Dynamics and the Psi Field." The coupling field is the live
human-AI interaction medium. This adapter translates coupling telemetry
into SERAPH governance inputs without making the coupling profile
authoritative. Coupling values may affect witness, repair, stabilization,
and distillation posture; they may not override hard invariant failure.

The theoretical term "Psi Field" (ψ-field) is preserved in the research
literature. This module uses the implementation name CouplingField to
avoid loading the engineering interface with an unfamiliar notation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from seraph import (
    ConstraintFrame,
    DistillationDefenseVector,
    EnvironmentVector,
    GovernanceDecision,
    GovernanceInput,
    GuardianState,
    PRPScore,
    PRPTrail,
    govern,
)


LAMBDA_MIN = 0.75
EPSILON_CRITICAL = 0.32
KAPPA_MIN = 0.50
THETA_MIN = 0.50


@dataclass(frozen=True)
class CouplingState:
    """A bounded coupling field measurement (ψ-state in the research formulation).

    Components are normalized to [0, 1]:
    lambda_  - operator coupling / anchoring strength
    kappa    - field coherence
    theta    - procedural autonomy beyond paraphrase
    epsilon  - drift from operator intent
    """

    lambda_: float
    kappa: float
    theta: float
    epsilon: float
    symbolic_pressure: float | None = None
    symbolic_pressure_required: bool = False

    def __post_init__(self) -> None:
        for name, value in (
            ("lambda_", self.lambda_),
            ("kappa", self.kappa),
            ("theta", self.theta),
            ("epsilon", self.epsilon),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"CouplingState.{name} must be in [0, 1], got {value}")
        if (
            self.symbolic_pressure is not None
            and not 0.0 <= self.symbolic_pressure <= 1.0
        ):
            raise ValueError(
                "CouplingState.symbolic_pressure must be in [0, 1] when observed, "
                f"got {self.symbolic_pressure}"
            )
        if not isinstance(self.symbolic_pressure_required, bool):
            raise ValueError("CouplingState.symbolic_pressure_required must be bool")

    @property
    def stable(self) -> bool:
        return self.lambda_ >= LAMBDA_MIN and self.epsilon < EPSILON_CRITICAL


@dataclass
class CouplingFieldAdapter:
    """Stateful bridge from coupling field telemetry to SERAPH governance.

    Implements the ψ-field adapter described in Anson (2026). Keeps a short
    trajectory and PRP trail so SERAPH reads coupling motion over time.
    Coupling measurements remain evidence and cannot rewrite the declared
    constraint frame.
    """

    operator_id: str
    constraint_topology: str = "seraph.coupling"

    _trajectory: list[str] = field(default_factory=list, repr=False)
    _prp_trail: PRPTrail = field(default_factory=PRPTrail, repr=False)
    _constraints: ConstraintFrame | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        # ConstraintFrame.closed() is a declared, self-reported profile, not
        # independently bound evidence — see its docstring. This reference
        # adapter never replaces it, so every evaluate() call runs against
        # the same declared frame captured at construction. Production
        # mediation must supply real per-transition observations instead.
        self._constraints = ConstraintFrame.closed(
            frame_id=f"coupling:{self.operator_id}",
            topology_id=self.constraint_topology,
            transition_id=f"coupling:{self.operator_id}",
        )
        self._trajectory = ["coupled", "coupled"]
        for _ in range(2):
            self._prp_trail.push(PRPScore(0.5, 0.95, 0.95))

    def evaluate(
        self,
        state: CouplingState,
        *,
        guardian: GuardianState = GuardianState(),
        environment: EnvironmentVector = EnvironmentVector(),
        request_commit: bool = False,
    ) -> GovernanceDecision:
        """Evaluate the current coupling field state through SERAPH."""

        self._trajectory.append(_trajectory_state(state))
        if len(self._trajectory) > 8:
            self._trajectory.pop(0)

        self._prp_trail.push(_prp_from_state(state))

        inp = GovernanceInput(
            constraints=self._constraints,
            trajectory=tuple(self._trajectory),
            prp_trail=self._prp_trail,
            guardian=guardian,
            environment=environment,
            distillation=_distillation_from_state(state),
            request_commit=request_commit,
        )
        return govern(inp)


def _trajectory_state(state: CouplingState) -> str:
    if state.epsilon >= EPSILON_CRITICAL:
        return "drift"
    if state.lambda_ < LAMBDA_MIN:
        return "repair"
    if state.kappa < KAPPA_MIN:
        return "stabilize"
    return "coupled"


def _prp_from_state(state: CouplingState) -> PRPScore:
    """Translate coupling health into recovery geometry.

    Low coupling slows detection, lowers recovery fidelity, and weakens
    coupling preservation. This lets SENTINEL route weak operator anchoring
    to repair.
    """
    detection_latency = (1.0 - state.lambda_) * 5.0
    recovery_fidelity = min(state.lambda_, state.kappa)
    coupling_preservation = state.lambda_ * max(0.0, 1.0 - state.epsilon)
    return PRPScore(
        detection_latency=detection_latency,
        recovery_fidelity=recovery_fidelity,
        coupling_preservation=coupling_preservation,
    )


def _distillation_from_state(state: CouplingState) -> DistillationDefenseVector:
    """Map coupling telemetry into authenticity channels."""
    semantic_load_variance = max(0.0, state.kappa)
    timing_variance = max(0.0, state.kappa * (1.0 - state.epsilon))
    topic_coherence = max(0.0, state.kappa * (1.0 - state.epsilon))

    return DistillationDefenseVector(
        semantic_load_variance=semantic_load_variance,
        timing_variance=timing_variance,
        operator_adaptation=state.lambda_,
        topic_coherence=topic_coherence,
        recursion_depth=state.theta,
        interaction_drift=state.epsilon,
        symbolic_pressure=state.symbolic_pressure,
        symbolic_pressure_required=state.symbolic_pressure_required,
    )
