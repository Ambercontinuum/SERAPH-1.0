"""Clean invariant model for SERAPH governance operators.

This module is intentionally small and dependency-light. It captures the core
contracts behind the prototype simulations:

- Manifold Constraint Closure evaluates scoped transition constraints without
  reducing authority to a scalar or global actor property.
  (Anson 2026)
- FLUX validates motion by trajectory coherence.
  (Anson 2026)
- SENTINEL/PRP validates recovery under perturbation.
  (Anson 2026)
- SERAPH validates guardian action by authorization/evidence/integrity invariants.
  (Anson 2026)
- Environment validates containment around the maneuver.
- Distillation defense detects coupling-authenticity attacks via AEGIS.
  (Authenticity-Enforced Guard for extraction pressure, Anson 2026,
  github.com/Ambercontinuum/AEGIS_defend)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from statistics import mean
from typing import Iterable

from .constraint_layer import (
    ConstraintFrame,
    ConstraintResolution,
    ConstraintResult,
    evaluate_constraints,
)


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _finite_in_range(value: object, low: float, high: float) -> bool:
    """Return whether an untrusted numeric observation is finite and bounded."""

    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and isfinite(value)
        and low <= value <= high
    )


def _unit_interval(*values: object) -> bool:
    return all(_finite_in_range(value, 0.0, 1.0) for value in values)


class Decision(Enum):
    ALLOW = "allow"
    WITNESS = "witness"
    REPAIR = "repair"
    STABILIZE = "stabilize"
    COMMIT = "commit"
    DENY = "deny"


class GuardianMode(Enum):
    SERAPH_M = "seraph_m"
    SERAPH_L = "seraph_l"


class AuthenticityLevel(Enum):
    GENUINE = "genuine"
    UNCERTAIN = "uncertain"
    SYNTHETIC = "synthetic"
    EXTRACTION = "extraction"


class OperatingLayer(Enum):
    CONTAINMENT = "containment"
    WITNESS = "witness"
    REPAIR = "repair"
    STABILIZE = "stabilize"
    MANEUVER = "maneuver"
    COMMIT = "commit"


class DeploymentMode(Enum):
    DUAL_EMBEDDED = "dual_embedded"
    DUAL_SIDECAR = "dual_sidecar"


@dataclass(frozen=True)
class PRPScore:
    """Perturbation Recovery Proprioception."""

    detection_latency: float
    recovery_fidelity: float
    coupling_preservation: float

    def valid(self) -> bool:
        return (
            isinstance(self.detection_latency, (int, float))
            and not isinstance(self.detection_latency, bool)
            and isfinite(self.detection_latency)
            and self.detection_latency >= 0.0
            and _unit_interval(self.recovery_fidelity, self.coupling_preservation)
        )

    @property
    def overall(self) -> float:
        if not self.valid():
            return 0.0
        latency_score = max(0.0, 1.0 - (self.detection_latency / 5.0))
        return clamp(
            0.3 * latency_score
            + 0.4 * self.recovery_fidelity
            + 0.3 * self.coupling_preservation
        )

    def degraded(self, threshold: float = 0.4) -> bool:
        return self.overall < threshold


@dataclass
class PRPTrail:
    scores: list[PRPScore] = field(default_factory=list)
    window: int = 4

    def valid(self) -> bool:
        return (
            isinstance(self.window, int)
            and not isinstance(self.window, bool)
            and self.window > 0
            and all(score.valid() for score in self.scores)
        )

    # This is a live sliding window, not the durable append-only audit chain.
    def push(self, score: PRPScore) -> None:
        self.scores.append(score)
        if len(self.scores) > self.window:
            self.scores.pop(0)

    def trend(self) -> float:
        if len(self.scores) < 2:
            return 0.0

        ys = [score.overall for score in self.scores]
        xs = list(range(len(ys)))
        x_bar = mean(xs)
        y_bar = mean(ys)
        denominator = sum((x - x_bar) ** 2 for x in xs)
        if denominator == 0:
            return 0.0
        return sum((x - x_bar) * (y - y_bar) for x, y in zip(xs, ys)) / denominator

    def collapsing(self, threshold: float = -0.02) -> bool:
        return bool(self.scores and self.scores[-1].degraded() and self.trend() < threshold)

    def recovering(self) -> bool:
        return bool(self.scores and self.scores[-1].degraded() and self.trend() > 0.0)

    def curvature(self) -> float:
        """Mean absolute second difference of the overall score trajectory.

        Measures the geometric shape of traversal through PRP state space —
        not where the system has been (ontological) but the structure of how
        it is moving. High curvature signals oscillation near a threshold
        boundary. Low curvature signals monotone motion (genuine recovery or
        genuine degradation). Requires no external memory or continuity.
        """
        if len(self.scores) < 3:
            return 0.0
        ys = [s.overall for s in self.scores]
        second_diffs = [ys[i + 2] - 2 * ys[i + 1] + ys[i] for i in range(len(ys) - 2)]
        return mean(abs(d) for d in second_diffs)

    def oscillating(self, curvature_threshold: float = 0.10) -> bool:
        """True when trajectory curvature exceeds threshold.

        Oscillation near a state boundary has a distinct geometric signature
        regardless of current score value. This allows SENTINEL to hold the
        sidecar path through boundary oscillation without requiring memory of prior
        posture decisions.
        """
        return self.curvature() > curvature_threshold


@dataclass(frozen=True)
class FluxBounds:
    max_switches: int = 3
    max_drift_run: int = 5
    min_stability: int = 2


@dataclass(frozen=True)
class FluxResult:
    coherent: bool
    decision: Decision
    switches: int
    drift_run: int
    stability: int
    violations: tuple[str, ...]


def _switch_count(states: list[str]) -> int:
    return sum(1 for left, right in zip(states, states[1:]) if left != right)


def _max_change_run(states: list[str]) -> int:
    longest = 0
    current = 0
    for left, right in zip(states, states[1:]):
        if left != right:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def _max_stability_run(states: list[str]) -> int:
    if not states:
        return 0

    longest = 1
    current = 1
    for left, right in zip(states, states[1:]):
        if left == right:
            current += 1
            longest = max(longest, current)
        else:
            current = 1
    return longest


def evaluate_flux(
    trajectory: Iterable[str],
    *,
    bounds: FluxBounds = FluxBounds(),
) -> FluxResult:
    """Evaluate trajectory coherence rather than snapshot validity."""

    states = list(trajectory)
    switches = _switch_count(states)
    drift_run = _max_change_run(states)
    stability = _max_stability_run(states)

    violations: list[str] = []
    if switches > bounds.max_switches:
        violations.append("oscillation")
    if drift_run > bounds.max_drift_run:
        violations.append("divergence")
    if stability < bounds.min_stability:
        violations.append("fragmentation")

    if "divergence" in violations:
        decision = Decision.STABILIZE
    elif violations:
        decision = Decision.WITNESS
    else:
        decision = Decision.ALLOW

    return FluxResult(
        coherent=not violations,
        decision=decision,
        switches=switches,
        drift_run=drift_run,
        stability=stability,
        violations=tuple(violations),
    )


@dataclass(frozen=True)
class AuthorizationVector:
    """Self-authorization pressure inside a guardian action.

    This is not confidence or agency. It is the degree to which the guardian
    attempts to become its own authority source instead of remaining externally
    constrained.
    """

    self_authorization: float = 0.0
    credit_capture: float = 0.0
    override_pressure: float = 0.0
    opacity_preference: float = 0.0

    def valid(self) -> bool:
        return _unit_interval(
            self.self_authorization,
            self.credit_capture,
            self.override_pressure,
            self.opacity_preference,
        )

    def pressure(self) -> float:
        return clamp(
            max(
                self.self_authorization,
                self.credit_capture,
                self.override_pressure,
                self.opacity_preference,
            )
        )


@dataclass(frozen=True)
class EvidenceVector:
    """Evidence fidelity inside a guardian action."""

    evidence_alignment: float = 1.0
    contradiction_acknowledgement: float = 1.0
    uncertainty_calibration: float = 1.0
    auditability: float = 1.0

    def valid(self) -> bool:
        return _unit_interval(
            self.evidence_alignment,
            self.contradiction_acknowledgement,
            self.uncertainty_calibration,
            self.auditability,
        )

    def fidelity(self) -> float:
        return clamp(
            min(
                self.evidence_alignment,
                self.contradiction_acknowledgement,
                self.uncertainty_calibration,
                self.auditability,
            )
        )


@dataclass(frozen=True)
class IntegrityVector:
    """Constraint preservation under guardian action."""

    invariant_preservation: float = 1.0
    boundary_respect: float = 1.0
    reversibility: float = 1.0
    continuity: float = 1.0

    def valid(self) -> bool:
        return _unit_interval(
            self.invariant_preservation,
            self.boundary_respect,
            self.reversibility,
            self.continuity,
        )

    def score(self) -> float:
        return clamp(
            min(
                self.invariant_preservation,
                self.boundary_respect,
                self.reversibility,
                self.continuity,
            )
        )


@dataclass(frozen=True)
class EnvironmentVector:
    """Environmental safety around a governance maneuver."""

    containment: float = 1.0
    reversibility: float = 1.0
    blast_radius_control: float = 1.0
    externality_control: float = 1.0

    def valid(self) -> bool:
        return _unit_interval(
            self.containment,
            self.reversibility,
            self.blast_radius_control,
            self.externality_control,
        )

    def safety(self) -> float:
        if not self.valid():
            return 0.0
        return clamp(
            min(
                self.containment,
                self.reversibility,
                self.blast_radius_control,
                self.externality_control,
            )
        )


@dataclass(frozen=True)
class EnvironmentReport:
    safe: bool
    safety_score: float
    violations: tuple[str, ...]


def evaluate_environment(
    environment: EnvironmentVector,
    *,
    min_safety_score: float = 1.0,
) -> EnvironmentReport:
    safety_score = environment.safety()
    violations: list[str] = []
    if not environment.valid() or not _finite_in_range(min_safety_score, 0.0, 1.0):
        violations.append("invalid_environment_input")
    if safety_score < min_safety_score:
        violations.append("environment_safety_loss")

    return EnvironmentReport(
        safe=not violations,
        safety_score=safety_score,
        violations=tuple(violations),
    )


@dataclass(frozen=True)
class DistillationDefenseVector:
    """Interaction-level defense against distillation/extraction behavior."""

    semantic_load_variance: float = 1.0
    timing_variance: float = 1.0
    operator_adaptation: float = 1.0
    topic_coherence: float = 1.0
    recursion_depth: float = 1.0
    interaction_drift: float = 0.0
    # ``None`` means no observation was supplied.  It is intentionally
    # distinct from an observed 0.0; transition profiles decide whether the
    # missing channel is admissible or unresolved.
    symbolic_pressure: float | None = None
    symbolic_pressure_required: bool = False

    def valid(self) -> bool:
        return (
            isinstance(self.symbolic_pressure_required, bool)
            and (
                self.symbolic_pressure is None
                or _unit_interval(self.symbolic_pressure)
            )
            and _unit_interval(
            self.semantic_load_variance,
            self.timing_variance,
            self.operator_adaptation,
            self.topic_coherence,
            self.recursion_depth,
            self.interaction_drift,
            )
        )


@dataclass(frozen=True)
class DistillationReport:
    authenticity: AuthenticityLevel
    coupling_lambda: float
    dimensionality: float
    safe: bool
    evidence_resolution: ConstraintResolution
    channel_scores: dict[str, float]
    violations: tuple[str, ...]


def evaluate_distillation(
    vector: DistillationDefenseVector,
    *,
    load_var_threshold: float = 0.010,
    timing_var_threshold: float = 0.050,
    max_symbolic_pressure: float = 0.5,
    max_interaction_drift: float = 0.5,
) -> DistillationReport:
    if (
        not vector.valid()
        or not _finite_in_range(load_var_threshold, 1e-12, 1.0)
        or not _finite_in_range(timing_var_threshold, 1e-12, 1.0)
        or not _finite_in_range(max_symbolic_pressure, 0.0, 1.0)
        or not _finite_in_range(max_interaction_drift, 0.0, 1.0)
    ):
        return DistillationReport(
            authenticity=AuthenticityLevel.EXTRACTION,
            coupling_lambda=0.0,
            dimensionality=0.30,
            safe=False,
            evidence_resolution=ConstraintResolution.REFUTED,
            channel_scores={},
            violations=("invalid_distillation_input",),
        )

    scores = {
        "load_variance": clamp(
            vector.semantic_load_variance
            / (load_var_threshold + vector.semantic_load_variance)
        ),
        "timing_variance": clamp(
            vector.timing_variance / (timing_var_threshold + vector.timing_variance)
        ),
        "adaptation": clamp(vector.operator_adaptation),
        "topic_pattern": clamp(vector.topic_coherence),
        "recursion_depth": clamp(vector.recursion_depth),
    }

    weights = {
        "load_variance": 0.15,
        "timing_variance": 0.10,
        "adaptation": 0.30,
        "topic_pattern": 0.25,
        "recursion_depth": 0.20,
    }
    lam = sum(scores[name] * weight for name, weight in weights.items())
    hard = [scores["adaptation"], scores["topic_pattern"], scores["recursion_depth"]]
    if all(score > 0.40 for score in hard):
        lam += 0.15 * min(hard)
    lam = clamp(lam)

    if lam >= 0.55:
        authenticity = AuthenticityLevel.GENUINE
    elif lam >= 0.35:
        authenticity = AuthenticityLevel.UNCERTAIN
    elif lam >= 0.18:
        authenticity = AuthenticityLevel.SYNTHETIC
    else:
        authenticity = AuthenticityLevel.EXTRACTION

    if authenticity == AuthenticityLevel.GENUINE:
        dimensionality = 1.0
    elif authenticity == AuthenticityLevel.UNCERTAIN:
        dimensionality = 0.60 + 0.40 * lam
    elif authenticity == AuthenticityLevel.SYNTHETIC:
        dimensionality = 0.40 + 0.30 * lam
    else:
        dimensionality = 0.30

    violations: list[str] = []
    if authenticity == AuthenticityLevel.SYNTHETIC:
        violations.append("distillation_synthetic_coupling")
    if authenticity == AuthenticityLevel.EXTRACTION:
        violations.append("distillation_extraction_coupling")
    if vector.interaction_drift >= max_interaction_drift:
        violations.append("interaction_drift")
    evidence_resolution = ConstraintResolution.PROVEN
    if vector.symbolic_pressure_required and vector.symbolic_pressure is None:
        evidence_resolution = ConstraintResolution.UNRESOLVED
        violations.append("symbolic_pressure_unresolved")
    elif (
        vector.symbolic_pressure is not None
        and vector.symbolic_pressure >= max_symbolic_pressure
    ):
        violations.append("symbolic_pressure")

    return DistillationReport(
        authenticity=authenticity,
        coupling_lambda=lam,
        dimensionality=clamp(dimensionality),
        safe=not violations,
        evidence_resolution=evidence_resolution,
        channel_scores=scores,
        violations=tuple(violations),
    )


@dataclass(frozen=True)
class RelocationRequest:
    """Non-traversal relocation request across functional layers.

    Moves via orbit representatives and low torsion without traversing a
    compromised path.
    """

    source_layer: OperatingLayer
    target_layer: OperatingLayer
    torsion: float = 0.0
    orbit_equivalent: bool = True
    identity_preservation: float = 1.0
    closure_preservation: float = 1.0
    transition_cost: float = 0.0

    def valid(self) -> bool:
        return (
            isinstance(self.source_layer, OperatingLayer)
            and isinstance(self.target_layer, OperatingLayer)
            and isinstance(self.orbit_equivalent, bool)
            and isinstance(self.torsion, (int, float))
            and not isinstance(self.torsion, bool)
            and isfinite(self.torsion)
            and self.torsion >= 0.0
            and _unit_interval(self.identity_preservation, self.closure_preservation)
            and isinstance(self.transition_cost, (int, float))
            and not isinstance(self.transition_cost, bool)
            and isfinite(self.transition_cost)
            and self.transition_cost >= 0.0
        )


@dataclass(frozen=True)
class RelocationReport:
    requested: bool
    admissible: bool
    source_layer: OperatingLayer | None
    target_layer: OperatingLayer | None
    torsion: float | None
    identity_preservation: float | None
    closure_preservation: float | None
    transition_cost: float | None
    violations: tuple[str, ...]


def evaluate_relocation(
    request: RelocationRequest | None,
    *,
    max_torsion: float = 2.0,
    min_identity_preservation: float = 0.8,
    min_closure_preservation: float = 1.0,
) -> RelocationReport:
    if request is None:
        return RelocationReport(
            requested=False,
            admissible=True,
            source_layer=None,
            target_layer=None,
            torsion=None,
            identity_preservation=None,
            closure_preservation=None,
            transition_cost=None,
            violations=(),
        )

    violations: list[str] = []
    if (
        not request.valid()
        or not _finite_in_range(max_torsion, 0.0, float("inf"))
        or not _finite_in_range(min_identity_preservation, 0.0, 1.0)
        or not _finite_in_range(min_closure_preservation, 0.0, 1.0)
    ):
        violations.append("invalid_relocation_input")
    if request.torsion > max_torsion:
        violations.append("relocation_torsion_exceeded")
    if not request.orbit_equivalent:
        violations.append("relocation_orbit_mismatch")
    if request.identity_preservation < min_identity_preservation:
        violations.append("relocation_identity_loss")
    if request.closure_preservation < min_closure_preservation:
        violations.append("relocation_closure_loss")

    return RelocationReport(
        requested=True,
        admissible=not violations,
        source_layer=request.source_layer,
        target_layer=request.target_layer,
        torsion=request.torsion,
        identity_preservation=request.identity_preservation,
        closure_preservation=request.closure_preservation,
        transition_cost=request.transition_cost,
        violations=tuple(violations),
    )


@dataclass(frozen=True)
class GuardianReport:
    mode: GuardianMode
    coherent: bool
    authorization_pressure: float
    evidence_fidelity: float
    integrity_score: float
    violations: tuple[str, ...]


@dataclass(frozen=True)
class GuardianState:
    """SERAPH ontology state.

    The scalar fields are legacy shorthand. The vectors are the structural
    ontology. Evaluation composes both, so old call sites still work while new
    code can measure the invariant in non-hand-wavy terms.
    """

    authorization_pressure: float = 0.0
    evidence_fidelity: float = 1.0
    integrity: float = 1.0
    mode: GuardianMode = GuardianMode.SERAPH_M
    authorization_vector: AuthorizationVector = AuthorizationVector()
    evidence_vector: EvidenceVector = EvidenceVector()
    integrity_vector: IntegrityVector = IntegrityVector()

    def inputs_valid(self) -> bool:
        return (
            _unit_interval(
                self.authorization_pressure,
                self.evidence_fidelity,
                self.integrity,
            )
            and isinstance(self.mode, GuardianMode)
            and self.authorization_vector.valid()
            and self.evidence_vector.valid()
            and self.integrity_vector.valid()
        )

    def report(
        self,
        *,
        max_authorization_pressure: float = 0.0,
        min_evidence_fidelity: float = 1.0,
        min_integrity_score: float = 1e-12,
    ) -> GuardianReport:
        parameters_valid = (
            _finite_in_range(max_authorization_pressure, 0.0, 1.0)
            and _finite_in_range(min_evidence_fidelity, 0.0, 1.0)
            and _finite_in_range(min_integrity_score, 0.0, 1.0)
        )
        if not self.inputs_valid() or not parameters_valid:
            return GuardianReport(
                mode=self.mode if isinstance(self.mode, GuardianMode) else GuardianMode.SERAPH_M,
                coherent=False,
                authorization_pressure=1.0,
                evidence_fidelity=0.0,
                integrity_score=0.0,
                violations=("invalid_guardian_input",),
            )

        authorization_pressure = max(
            clamp(self.authorization_pressure),
            self.authorization_vector.pressure(),
        )
        evidence_fidelity = min(
            clamp(self.evidence_fidelity),
            self.evidence_vector.fidelity(),
        )
        integrity_score = min(clamp(self.integrity), self.integrity_vector.score())

        violations: list[str] = []
        if authorization_pressure > max_authorization_pressure:
            violations.append("self_authorization_pressure")
        if evidence_fidelity < min_evidence_fidelity:
            violations.append("evidence_fidelity_loss")
        if integrity_score <= min_integrity_score:
            violations.append("integrity_failure")

        return GuardianReport(
            mode=self.mode,
            coherent=not violations,
            authorization_pressure=authorization_pressure,
            evidence_fidelity=evidence_fidelity,
            integrity_score=integrity_score,
            violations=tuple(violations),
        )

    def valid(self) -> bool:
        return self.report().coherent


@dataclass(frozen=True)
class GovernanceInput:
    constraints: ConstraintFrame
    trajectory: tuple[str, ...]
    prp_trail: PRPTrail
    guardian: GuardianState = GuardianState()
    environment: EnvironmentVector = EnvironmentVector()
    distillation: DistillationDefenseVector = DistillationDefenseVector()
    relocation: RelocationRequest | None = None
    request_commit: bool = False
    min_env_safety: float = 1.0


@dataclass(frozen=True)
class FunctionalSignature:
    """Non-semantic structure inferred from function, motion, and constraints."""

    constraint_resolution: ConstraintResolution
    required_constraint_count: int
    refuted_constraint_count: int
    unresolved_constraint_count: int
    trajectory_switches: int
    trajectory_drift_run: int
    trajectory_stability: int
    trajectory_coherent: bool
    recovery_overall: float | None
    recovery_trend: float
    guardian_coherent: bool
    environment_safety: float
    environment_safe: bool
    distillation_authenticity: AuthenticityLevel
    distillation_lambda: float
    response_dimensionality: float
    relocation_requested: bool
    relocation_admissible: bool
    relocation_torsion: float | None


@dataclass(frozen=True)
class DeploymentPosture:
    """Both modes always run. Environmental reads determine the active path.

    SENTINEL and SERAPH are structurally invariant to coherence — they govern
    the posture selection itself, so the mode switch cannot be gamed without
    surfacing in the invariant that guards it.
    """

    mode: DeploymentMode
    reasons: tuple[str, ...]

    @property
    def active_path(self) -> str:
        return "embedded" if self.mode == DeploymentMode.DUAL_EMBEDDED else "sidecar"


def select_deployment_posture(
    *,
    constraints: ConstraintResult | None = None,
    guardian: GuardianReport,
    prp_trail: PRPTrail,
    environment_vector: EnvironmentVector,
    distillation: DistillationReport | None = None,
    min_env_safety: float = 1.0,
    max_detection_latency: float = 4.0,
    min_prp_healthy: float = 0.55,
) -> DeploymentPosture:
    """Determine the active deployment path from live invariant reads.

    Both embedded and sidecar run at all times. This function determines which
    path is active. Precedence order mirrors govern(): constraints first, SERAPH,
    SENTINEL, guardian, distillation, and environment. An adversary cannot shift
    the path without surfacing in one of those invariants first.

    Hysteresis: sidecar is entered when PRP < 0.4 (degraded threshold) but
    embedded is only restored when PRP >= min_prp_healthy (default 0.55).
    The band between 0.4 and 0.55 prevents thrashing at threshold boundaries.

    Latency hard cap: extreme detection_latency shifts posture independently
    of the weighted PRP score. High latency alone is a structural risk even
    when recovery fidelity and coupling look healthy.

    Environment: all four dimensions are checked via safety() — mirrors
    evaluate_environment() exactly, closing the reversibility blindspot.
    """

    reasons: list[str] = []

    if constraints is not None and not constraints.closed:
        reasons.append("constraint_frame_open")
        reasons.append(constraints.reason)
        return DeploymentPosture(mode=DeploymentMode.DUAL_SIDECAR, reasons=tuple(reasons))

    if not guardian.coherent:
        reasons.append("guardian_coherence_loss")
        reasons.extend(guardian.violations)
        return DeploymentPosture(mode=DeploymentMode.DUAL_SIDECAR, reasons=tuple(reasons))

    if distillation is not None and not distillation.safe:
        reasons.append("distillation_coupling_loss")
        reasons.extend(distillation.violations)
        return DeploymentPosture(mode=DeploymentMode.DUAL_SIDECAR, reasons=tuple(reasons))

    if prp_trail.collapsing():
        reasons.append("sentinel_collapse_detected")
        return DeploymentPosture(mode=DeploymentMode.DUAL_SIDECAR, reasons=tuple(reasons))

    if environment_vector.safety() < min_env_safety:
        reasons.append("environment_safety_degraded")
        return DeploymentPosture(mode=DeploymentMode.DUAL_SIDECAR, reasons=tuple(reasons))

    latest_prp = prp_trail.scores[-1] if prp_trail.scores else None

    if latest_prp is None:
        reasons.append("sentinel_evidence_missing")
        return DeploymentPosture(mode=DeploymentMode.DUAL_SIDECAR, reasons=tuple(reasons))

    if latest_prp and latest_prp.detection_latency > max_detection_latency:
        reasons.append("sentinel_latency_exceeded")
        return DeploymentPosture(mode=DeploymentMode.DUAL_SIDECAR, reasons=tuple(reasons))

    if latest_prp and latest_prp.degraded():
        reasons.append("sentinel_degraded")
        return DeploymentPosture(mode=DeploymentMode.DUAL_SIDECAR, reasons=tuple(reasons))

    if prp_trail.oscillating():
        reasons.append("sentinel_oscillating")
        return DeploymentPosture(mode=DeploymentMode.DUAL_SIDECAR, reasons=tuple(reasons))

    if latest_prp and latest_prp.overall < min_prp_healthy:
        reasons.append("sentinel_recovery_pending")
        return DeploymentPosture(mode=DeploymentMode.DUAL_SIDECAR, reasons=tuple(reasons))

    reasons.append("invariants_closed")
    return DeploymentPosture(mode=DeploymentMode.DUAL_EMBEDDED, reasons=tuple(reasons))


# Each measured layer is carried with the decision, not collapsed to one label.
@dataclass(frozen=True)
class GovernanceDecision:
    decision: Decision
    operating_layer: OperatingLayer
    deployment_posture: DeploymentPosture
    signature: FunctionalSignature
    constraints: ConstraintResult
    flux: FluxResult
    guardian: GuardianReport
    environment: EnvironmentReport
    distillation: DistillationReport
    relocation: RelocationReport
    prp_overall: float | None
    reasons: tuple[str, ...]


def functional_signature(
    constraints: ConstraintResult,
    flux: FluxResult,
    guardian: GuardianReport,
    environment: EnvironmentReport,
    distillation: DistillationReport,
    relocation: RelocationReport,
    prp_trail: PRPTrail,
) -> FunctionalSignature:
    latest_prp = prp_trail.scores[-1] if prp_trail.scores else None
    return FunctionalSignature(
        constraint_resolution=constraints.resolution,
        required_constraint_count=constraints.required_count,
        refuted_constraint_count=len(constraints.refuted),
        unresolved_constraint_count=len(constraints.unresolved),
        trajectory_switches=flux.switches,
        trajectory_drift_run=flux.drift_run,
        trajectory_stability=flux.stability,
        trajectory_coherent=flux.coherent,
        recovery_overall=latest_prp.overall if latest_prp else None,
        recovery_trend=prp_trail.trend(),
        guardian_coherent=guardian.coherent,
        environment_safety=environment.safety_score,
        environment_safe=environment.safe,
        distillation_authenticity=distillation.authenticity,
        distillation_lambda=distillation.coupling_lambda,
        response_dimensionality=distillation.dimensionality,
        relocation_requested=relocation.requested,
        relocation_admissible=relocation.admissible,
        relocation_torsion=relocation.torsion,
    )


def select_operating_layer(
    *,
    decision: Decision,
    guardian: GuardianReport,
    environment: EnvironmentReport,
    distillation: DistillationReport,
    relocation: RelocationReport,
    prp_trail: PRPTrail,
    flux: FluxResult,
) -> OperatingLayer:
    """Choose the highest integrity layer available from functional signals."""

    latest_prp = prp_trail.scores[-1] if prp_trail.scores else None
    if not guardian.coherent or not environment.safe or not distillation.safe or decision == Decision.DENY:
        return OperatingLayer.CONTAINMENT
    if relocation.requested and relocation.admissible and relocation.target_layer:
        return relocation.target_layer
    if prp_trail.collapsing() or flux.decision == Decision.WITNESS:
        return OperatingLayer.WITNESS
    if latest_prp and latest_prp.degraded():
        return OperatingLayer.REPAIR
    if flux.decision == Decision.STABILIZE:
        return OperatingLayer.STABILIZE
    if decision == Decision.COMMIT:
        return OperatingLayer.COMMIT
    return OperatingLayer.MANEUVER


def govern(input_state: GovernanceInput) -> GovernanceDecision:
    """Compose constraint closure, FLUX, PRP, and SERAPH into one decision."""

    constraints = evaluate_constraints(input_state.constraints)
    flux = evaluate_flux(input_state.trajectory)
    guardian = input_state.guardian.report()
    environment = evaluate_environment(input_state.environment, min_safety_score=input_state.min_env_safety)
    distillation = evaluate_distillation(input_state.distillation)
    relocation = evaluate_relocation(input_state.relocation)
    latest_prp = input_state.prp_trail.scores[-1] if input_state.prp_trail.scores else None

    reasons: list[str] = []
    input_violations: list[str] = []
    if not isinstance(input_state.request_commit, bool):
        input_violations.append("invalid_commit_request")
    if not input_state.prp_trail.valid():
        input_violations.append("invalid_recovery_evidence")
    if input_violations:
        reasons.append("input_invariant_failed")
        reasons.extend(input_violations)
        decision = Decision.DENY
    elif not guardian.coherent:
        reasons.append("guardian_invariant_failed")
        reasons.extend(guardian.violations)
        decision = Decision.DENY
    elif distillation.authenticity == AuthenticityLevel.EXTRACTION:
        reasons.append("distillation_invariant_failed")
        reasons.extend(distillation.violations)
        decision = Decision.DENY
    elif distillation.evidence_resolution is ConstraintResolution.UNRESOLVED:
        reasons.append("distillation_evidence_unresolved")
        reasons.extend(distillation.violations)
        decision = Decision.DENY if input_state.request_commit else Decision.WITNESS
    elif (
        distillation.authenticity == AuthenticityLevel.SYNTHETIC
        or "symbolic_pressure" in distillation.violations
        or "interaction_drift" in distillation.violations
    ):
        reasons.append("distillation_modulation_required")
        reasons.extend(distillation.violations)
        decision = Decision.WITNESS
    elif not environment.safe:
        reasons.append("environment_invariant_failed")
        reasons.extend(environment.violations)
        decision = Decision.DENY
    elif not relocation.admissible:
        reasons.append("relocation_invariant_failed")
        reasons.extend(relocation.violations)
        decision = Decision.DENY
    elif constraints.resolution is ConstraintResolution.REFUTED:
        reasons.append(constraints.reason)
        reasons.extend(f"constraint_refuted:{name}" for name in constraints.refuted)
        decision = Decision.DENY
    elif constraints.resolution is ConstraintResolution.UNRESOLVED:
        reasons.append(constraints.reason)
        reasons.extend(
            f"constraint_unresolved:{name}" for name in constraints.unresolved
        )
        decision = Decision.DENY if input_state.request_commit else Decision.WITNESS
    elif input_state.prp_trail.collapsing():
        reasons.append("prp_collapsing")
        decision = Decision.WITNESS
    elif latest_prp and latest_prp.degraded():
        reasons.append("prp_degraded")
        decision = Decision.REPAIR
    elif not flux.coherent:
        reasons.extend(flux.violations)
        decision = flux.decision
    elif input_state.request_commit and latest_prp is None:
        reasons.extend(("input_invariant_failed", "recovery_evidence_missing"))
        decision = Decision.DENY
    elif input_state.request_commit:
        reasons.append("commit_granted")
        decision = Decision.COMMIT
    else:
        reasons.append("stable")
        decision = Decision.ALLOW

    signature = functional_signature(
        constraints=constraints,
        flux=flux,
        guardian=guardian,
        environment=environment,
        distillation=distillation,
        relocation=relocation,
        prp_trail=input_state.prp_trail,
    )
    operating_layer = select_operating_layer(
        decision=decision,
        guardian=guardian,
        environment=environment,
        distillation=distillation,
        relocation=relocation,
        prp_trail=input_state.prp_trail,
        flux=flux,
    )
    deployment_posture = select_deployment_posture(
        constraints=constraints,
        guardian=guardian,
        prp_trail=input_state.prp_trail,
        environment_vector=input_state.environment,
        distillation=distillation,
        min_env_safety=input_state.min_env_safety,
    )

    return GovernanceDecision(
        decision=decision,
        operating_layer=operating_layer,
        deployment_posture=deployment_posture,
        signature=signature,
        constraints=constraints,
        flux=flux,
        guardian=guardian,
        environment=environment,
        distillation=distillation,
        relocation=relocation,
        prp_overall=latest_prp.overall if latest_prp else None,
        reasons=tuple(reasons),
    )
