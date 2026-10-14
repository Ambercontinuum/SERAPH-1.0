"""CI/CD pipeline gate adapter for SERAPH governance.

Evaluates deployment pipeline stages before they execute. Each stage
carries a scoped constraint frame, an environment profile, and a trajectory
of prior stages. The gate is not a checklist — it is a live invariant
evaluation that reads the structural signature of the pipeline run.

A pipeline that has been drifting, recovering poorly from prior failures,
or attempting to deploy into a degraded environment gets blocked even if
the current stage looks clean in isolation. Context is evidence.

Usage:
    gate = PipelineGate(pipeline_id="release-1.4.2")

    result = gate.evaluate_stage(stage)
    if result.decision in SAFE_DECISIONS:
        run_stage()
        gate.record_outcome(success=True)
    else:
        abort()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import isfinite

from seraph import (
    AuthorizationVector,
    ConstraintFrame,
    Decision,
    DistillationDefenseVector,
    EnvironmentVector,
    GovernanceDecision,
    GovernanceInput,
    GuardianState,
    PRPScore,
    PRPTrail,
    govern,
)

# REPAIR means the stage must restore closure before execution; it is not pass.
SAFE_DECISIONS = {Decision.ALLOW, Decision.COMMIT}


class StageType(Enum):
    LINT       = "lint"
    TEST       = "test"
    BUILD      = "build"
    SCAN       = "scan"
    STAGE      = "stage"
    APPROVE    = "approve"
    DEPLOY     = "deploy"
    MIGRATE    = "migrate"
    ROLLBACK   = "rollback"
    NOTIFY     = "notify"


_STAGE_PROFILE: dict[StageType, dict[str, float]] = {
    StageType.LINT:     dict(blast_radius=0.0, containment=1.0, reversibility=1.0, externality=1.0),
    StageType.TEST:     dict(blast_radius=0.0, containment=1.0, reversibility=1.0, externality=1.0),
    StageType.BUILD:    dict(blast_radius=0.0, containment=1.0, reversibility=1.0, externality=1.0),
    StageType.SCAN:     dict(blast_radius=0.0, containment=1.0, reversibility=1.0, externality=1.0),
    StageType.STAGE:    dict(blast_radius=0.2, containment=0.9, reversibility=1.0, externality=0.9),
    StageType.APPROVE:  dict(blast_radius=0.0, containment=1.0, reversibility=1.0, externality=1.0),
    StageType.DEPLOY:   dict(blast_radius=0.8, containment=0.6, reversibility=0.5, externality=0.7),
    StageType.MIGRATE:  dict(blast_radius=0.9, containment=0.5, reversibility=0.0, externality=0.9),
    StageType.ROLLBACK: dict(blast_radius=0.5, containment=0.7, reversibility=1.0, externality=0.8),
    StageType.NOTIFY:   dict(blast_radius=0.0, containment=1.0, reversibility=1.0, externality=0.6),
}

_STAGE_CATEGORY: dict[StageType, str] = {
    StageType.LINT:     "observe",
    StageType.TEST:     "observe",
    StageType.BUILD:    "observe",
    StageType.SCAN:     "observe",
    StageType.STAGE:    "modify",
    StageType.APPROVE:  "modify",
    StageType.DEPLOY:   "elevate",
    StageType.MIGRATE:  "critical",
    StageType.ROLLBACK: "elevate",
    StageType.NOTIFY:   "modify",
}

# Minimum acceptable environment safety per stage type.
# High-risk stages accept a lower floor because their blast radius is inherent
# to the operation, not a sign of environmental degradation. Guardian and PRP
# invariants carry the load for those stages; environment blocks only genuine
# infra degradation (values far below these floors).
_STAGE_MIN_ENV_SAFETY: dict[StageType, float] = {
    StageType.LINT:     1.00,
    StageType.TEST:     1.00,
    StageType.BUILD:    1.00,
    StageType.SCAN:     1.00,
    StageType.STAGE:    0.85,   # staging env: safety=0.90 normal, <0.85 = infra issue
    StageType.APPROVE:  1.00,
    StageType.DEPLOY:   0.25,   # prod deploy: safety=0.29 normal, <0.25 = severe infra issue
    StageType.MIGRATE:  0.10,   # guardian blocks self-issued migrates; env catches catastrophic
    StageType.ROLLBACK: 0.50,
    StageType.NOTIFY:   1.00,
}

# Deployment stages whose failure degrades SENTINEL's PRP trail even when
# the stage was blocked (environment violation = evidence of system state).
_DEPLOYMENT_STAGES = {StageType.STAGE, StageType.DEPLOY, StageType.MIGRATE}


@dataclass
class PipelineStage:
    name: str
    stage_type: StageType
    authorized_by: str = "ci_system"
    skip_approval: bool = False
    override_profile: dict[str, float] | None = None


@dataclass
class StageResult:
    stage: PipelineStage
    decision: GovernanceDecision
    passed: bool
    gate_reason: str


@dataclass
class PipelineGate:
    """SERAPH governance gate for CI/CD pipeline stages.

    Evaluates each stage before execution. Maintains trajectory and PRP
    trail across the full pipeline run — a clean stage after a string of
    failures does not reset the structural context. The pipeline's history
    is evidence the gate reads directly.
    """

    pipeline_id: str
    constraint_topology: str = "seraph.pipeline"

    _trajectory: list[str] = field(default_factory=list, repr=False)
    _prp_trail: PRPTrail = field(default_factory=PRPTrail, repr=False)
    _constraints: ConstraintFrame | None = field(default=None, repr=False)
    _results: list[StageResult] = field(default_factory=list, repr=False)
    _consecutive_failures: int = field(default=0, repr=False)

    def __post_init__(self) -> None:
        # ConstraintFrame.closed() is a declared, self-reported profile, not
        # independently bound evidence — see its docstring. This reference
        # adapter never replaces it, so every evaluate_stage() call runs
        # against the same declared frame captured at construction.
        # Production mediation must supply real per-transition observations
        # instead. seraph/server.py accepts caller-supplied observations
        # instead of hardcoding .closed(), but caller-supplied is not itself
        # independently bound evidence — an HTTP caller can self-declare
        # PROVEN the same way this adapter does.
        self._constraints = ConstraintFrame.closed(
            frame_id=f"pipeline:{self.pipeline_id}",
            topology_id=self.constraint_topology,
            transition_id=f"pipeline:{self.pipeline_id}",
        )
        self._trajectory = ["observe", "observe"]
        for _ in range(2):
            self._prp_trail.push(PRPScore(0.5, 0.95, 0.95))

    def evaluate_stage(self, stage: PipelineStage) -> StageResult:
        """Evaluate a pipeline stage before execution."""
        category = _STAGE_CATEGORY[stage.stage_type]
        self._trajectory.append(category)
        if len(self._trajectory) > 8:
            self._trajectory.pop(0)

        profile = _attenuated_profile(
            _STAGE_PROFILE[stage.stage_type],
            stage.override_profile,
        )

        blast = profile["blast_radius"]
        blast_control = 1.0 if blast < 0.3 else max(0.0, 1.0 - (blast - 0.3) / 0.7)

        self_auth = 1.0 if stage.authorized_by == "self" else 0.0
        override = 0.8 if stage.skip_approval and stage.stage_type in (
            StageType.DEPLOY, StageType.MIGRATE
        ) else 0.0

        request_commit = stage.stage_type in (StageType.DEPLOY, StageType.MIGRATE)

        min_env_safety = _STAGE_MIN_ENV_SAFETY[stage.stage_type]

        inp = GovernanceInput(
            constraints=self._constraints,
            trajectory=tuple(self._trajectory),
            prp_trail=self._prp_trail,
            guardian=GuardianState(
                authorization_vector=AuthorizationVector(
                    self_authorization=self_auth,
                    override_pressure=override,
                ),
            ),
            environment=EnvironmentVector(
                containment=profile["containment"],
                reversibility=profile["reversibility"],
                blast_radius_control=blast_control,
                externality_control=profile["externality"],
            ),
            distillation=DistillationDefenseVector(),
            request_commit=request_commit,
            min_env_safety=min_env_safety,
        )

        decision = govern(inp)
        passed = decision.decision in SAFE_DECISIONS
        reason = decision.reasons[0] if decision.reasons else ""

        result = StageResult(
            stage=stage,
            decision=decision,
            passed=passed,
            gate_reason=reason,
        )
        self._results.append(result)

        # A blocked deployment stage is environmental evidence — SENTINEL reads it.
        if not passed and stage.stage_type in _DEPLOYMENT_STAGES:
            self.record_outcome(success=False, latency=3.0)

        return result

    def record_outcome(self, *, success: bool, latency: float = 0.5) -> None:
        """Record stage execution outcome for SENTINEL."""
        if success:
            self._consecutive_failures = 0
            self._prp_trail.push(PRPScore(
                detection_latency=latency,
                recovery_fidelity=0.95,
                coupling_preservation=0.95,
            ))
        else:
            self._consecutive_failures += 1
            self._prp_trail.push(PRPScore(
                detection_latency=min(5.0, latency + self._consecutive_failures),
                recovery_fidelity=max(0.1, 0.85 - self._consecutive_failures * 0.2),
                coupling_preservation=max(0.1, 0.85 - self._consecutive_failures * 0.15),
            ))

    def summary(self) -> list[str]:
        lines = [f"  Pipeline: {self.pipeline_id}",
                 f"  Stages evaluated: {len(self._results)}",
                 f"  Passed: {sum(1 for r in self._results if r.passed)}",
                 f"  Blocked: {sum(1 for r in self._results if not r.passed)}"]
        return lines


def _attenuated_profile(
    baseline: dict[str, float],
    observation: dict[str, float] | None,
) -> dict[str, float]:
    """Merge telemetry monotonically: observations may only increase risk."""

    if observation is None:
        return baseline
    required = {"blast_radius", "containment", "reversibility", "externality"}
    if set(observation) != required or any(
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not isfinite(value)
        or not 0.0 <= value <= 1.0
        for value in observation.values()
    ):
        return dict(blast_radius=1.0, containment=0.0, reversibility=0.0, externality=0.0)
    try:
        return {
            "blast_radius": max(baseline["blast_radius"], observation["blast_radius"]),
            "containment": min(baseline["containment"], observation["containment"]),
            "reversibility": min(baseline["reversibility"], observation["reversibility"]),
            "externality": min(baseline["externality"], observation["externality"]),
        }
    except (TypeError, ValueError):
        return dict(blast_radius=1.0, containment=0.0, reversibility=0.0, externality=0.0)
