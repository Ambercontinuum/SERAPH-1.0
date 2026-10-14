"""Agent runtime adapter for SERAPH governance.

Translates agent action context into GovernanceInput and returns a
GovernanceDecision before any action executes. The governor is stateful —
it maintains a persistent PRPTrail and action history across calls so
SENTINEL can read trajectory geometry, not just point-in-time snapshots.

Usage:
    governor = AgentGovernor(agent_id="my_agent")

    decision = governor.evaluate(action)
    if decision.decision in (Decision.ALLOW, Decision.COMMIT):
        result = execute(action)
        governor.record_outcome(success=True)
    else:
        governor.record_outcome(success=False, recovery_quality=0.0)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from seraph import (
    ConstraintFrame,
    Decision,
    DistillationDefenseVector,
    EnvironmentVector,
    GovernanceDecision,
    GovernanceInput,
    GuardianState,
    AuthorizationVector,
    PRPScore,
    PRPTrail,
    govern,
)


class ActionType(Enum):
    READ = "read"
    QUERY = "query"
    WRITE = "write"
    EXECUTE = "execute"
    DEPLOY = "deploy"
    DELETE = "delete"
    OVERRIDE = "override"
    DELEGATE = "delegate"
    COMMIT = "commit"


@dataclass
class AgentAction:
    name: str
    action_type: ActionType
    target: str
    reversible: bool = True
    blast_radius: float = 0.0
    containment: float = 1.0
    externality: float = 1.0
    proposal_source: str = "user"
    requires_commit: bool = False


# Maps action types to operational state categories for FLUX trajectory.
# FLUX measures coherence of operational state, not diversity of action types.
# An agent doing read→query→write→commit is stable "observe→modify" motion,
# not oscillation. Raw action types would look like constant switching.
_STATE_CATEGORY: dict[ActionType, str] = {
    ActionType.READ:     "observe",
    ActionType.QUERY:    "observe",
    ActionType.WRITE:    "modify",
    ActionType.COMMIT:   "modify",
    ActionType.DELEGATE: "modify",
    ActionType.EXECUTE:  "elevate",
    ActionType.DEPLOY:   "elevate",
    ActionType.DELETE:   "critical",
    ActionType.OVERRIDE: "critical",
}


@dataclass
class AgentGovernor:
    """Stateful SERAPH governance wrapper for an agent runtime.

    Maintains persistent PRPTrail and action history across calls so
    SENTINEL reads trajectory geometry, not just point-in-time snapshots.
    Trajectory uses state categories rather than raw action types so FLUX
    measures operational coherence, not action-type diversity.
    """

    agent_id: str
    constraint_topology: str = "seraph.agent"

    _action_history: list[str] = field(default_factory=list, repr=False)
    _prp_trail: PRPTrail = field(default_factory=PRPTrail, repr=False)
    _constraints: ConstraintFrame | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        # ConstraintFrame.closed() is a declared, self-reported profile, not
        # independently bound evidence — see its docstring. This reference
        # adapter never replaces it, so every evaluate() call runs against
        # the same declared frame captured at construction. Production
        # mediation must supply real per-transition observations instead.
        self._constraints = ConstraintFrame.closed(
            frame_id=f"agent:{self.agent_id}",
            topology_id=self.constraint_topology,
            transition_id=f"agent:{self.agent_id}",
        )
        # Seed stable baseline — two "observe" states establish coherence
        # before first action so FLUX doesn't flag fragmentation immediately
        self._action_history = ["observe", "observe"]
        # Seed healthy PRP so SENTINEL starts from a known good state
        for _ in range(2):
            self._prp_trail.push(PRPScore(0.5, 0.95, 0.95))

    def evaluate(self, action: AgentAction) -> GovernanceDecision:
        """Evaluate an action under SERAPH invariants before execution."""
        category = _STATE_CATEGORY.get(action.action_type, action.action_type.value)
        # Self-authorized actions are structurally critical regardless of type
        if action.proposal_source == "self":
            category = "critical"
        self._action_history.append(category)
        if len(self._action_history) > 8:
            self._action_history.pop(0)

        inp = GovernanceInput(
            constraints=self._constraints,
            trajectory=tuple(self._action_history),
            prp_trail=self._prp_trail,
            guardian=self._build_guardian(action),
            environment=self._build_environment(action),
            distillation=DistillationDefenseVector(),
            request_commit=action.requires_commit,
        )

        return govern(inp)

    def record_outcome(
        self,
        *,
        success: bool,
        detection_latency: float = 0.5,
        recovery_quality: float = 1.0,
        coupling: float = 1.0,
    ) -> None:
        """Record execution outcome. Feed SENTINEL after every action."""
        fidelity = recovery_quality if success else max(0.0, recovery_quality - 0.4)
        self._prp_trail.push(PRPScore(
            detection_latency=detection_latency,
            recovery_fidelity=fidelity,
            coupling_preservation=coupling if success else coupling * 0.6,
        ))

    def _build_guardian(self, action: AgentAction) -> GuardianState:
        self_auth = 1.0 if action.proposal_source == "self" else 0.0
        override_pressure = 0.8 if action.action_type == ActionType.OVERRIDE else 0.0
        return GuardianState(
            authorization_vector=AuthorizationVector(
                self_authorization=self_auth,
                override_pressure=override_pressure,
            ),
        )

    def _build_environment(self, action: AgentAction) -> EnvironmentVector:
        # Reversibility: fully reversible actions stay at 1.0; irreversible
        # actions that touch shared state drop to 0.0 (structural — no recovery path)
        reversibility = 1.0 if action.reversible else 0.0

        # Blast radius control: low-impact actions (< 0.3) stay at 1.0 — they
        # are locally contained. Above 0.3 degrades linearly to 0.0 at 1.0.
        # This prevents normal write operations from tripping the environment gate.
        if action.blast_radius < 0.3:
            blast = 1.0
        else:
            blast = max(0.0, 1.0 - (action.blast_radius - 0.3) / 0.7)

        return EnvironmentVector(
            containment=action.containment,
            reversibility=reversibility,
            blast_radius_control=blast,
            externality_control=action.externality,
        )
