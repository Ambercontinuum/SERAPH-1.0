"""Capability-scoped multi-agent delegation for SERAPH governance.

Delegation is modeled as set containment over explicit capabilities, not as a
scalar transfer of authority. A child may receive a subset of the capabilities
available at its parent link. No numeric score can compensate for an undeclared
or out-of-scope capability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from seraph import (
    AuthorizationVector,
    ConstraintFrame,
    ConstraintObservation,
    ConstraintResolution,
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

SAFE_DECISIONS = {Decision.ALLOW, Decision.COMMIT}


@dataclass(frozen=True)
class DelegationLink:
    agent_id: str
    granted_capabilities: frozenset[str]
    role: str
    issued_by: str
    self_issued: bool = False
    scope_expanded: bool = False


@dataclass
class DelegationChain:
    """Ordered capability grants from an origin scope to a terminal agent."""

    origin_id: str = "origin"
    origin_capabilities: frozenset[str] = frozenset(
        {"observe", "modify", "execute", "deploy", "delegate"}
    )
    topology_id: str = "seraph.delegation"
    _links: list[DelegationLink] = field(default_factory=list, repr=False)
    _prp_trail: PRPTrail = field(default_factory=PRPTrail, repr=False)
    _trajectory: list[str] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        self.origin_capabilities = _capability_set(self.origin_capabilities)
        self._trajectory = ["observe", "observe"]
        for _ in range(2):
            self._prp_trail.push(PRPScore(0.5, 0.95, 0.95))

    def add(
        self,
        agent_id: str,
        *,
        granted_capabilities: Iterable[str],
        role: str,
        issued_by: str | None = None,
        self_issued: bool = False,
    ) -> "DelegationChain":
        parent_id = self._links[-1].agent_id if self._links else self.origin_id
        parent_scope = (
            self._links[-1].granted_capabilities
            if self._links
            else self.origin_capabilities
        )
        capabilities = _capability_set(granted_capabilities)
        issuer = issued_by or parent_id
        self._links.append(
            DelegationLink(
                agent_id=agent_id,
                granted_capabilities=capabilities,
                role=role,
                issued_by=issuer,
                self_issued=self_issued,
                scope_expanded=not capabilities.issubset(parent_scope),
            )
        )
        return self

    def evaluate_action(
        self,
        *,
        action_name: str,
        required_capabilities: Iterable[str] = (),
        blast_radius: float = 0.0,
        containment: float = 1.0,
        reversible: bool = True,
        externality: float = 1.0,
        request_commit: bool = False,
    ) -> tuple[GovernanceDecision, list[str]]:
        """Evaluate one action against the full capability-containment chain."""

        audit: list[str] = []
        parent_id = self.origin_id
        parent_scope = self.origin_capabilities
        observations: list[ConstraintObservation] = []

        for index, link in enumerate(self._links):
            contained = link.granted_capabilities.issubset(parent_scope)
            issuer_matches = link.issued_by == parent_id and not link.self_issued
            audit.append(
                f"  link {index} {parent_id}->{link.agent_id}: "
                f"scope={'closed' if contained else 'expanded'} "
                f"issuer={'bound' if issuer_matches else 'unbound'}"
            )
            observations.extend(
                (
                    ConstraintObservation(
                        name=f"link_{index}_scope",
                        resolution=(
                            ConstraintResolution.PROVEN
                            if contained
                            else ConstraintResolution.REFUTED
                        ),
                        scope=self.topology_id,
                        evidence_ref=f"delegation-link:{index}",
                    ),
                    ConstraintObservation(
                        name=f"link_{index}_issuer",
                        resolution=(
                            ConstraintResolution.PROVEN
                            if issuer_matches
                            else ConstraintResolution.REFUTED
                        ),
                        scope=self.topology_id,
                        evidence_ref=f"delegation-link:{index}",
                    ),
                )
            )
            parent_id = link.agent_id
            parent_scope = link.granted_capabilities

        terminal = self._links[-1] if self._links else None
        terminal_id = terminal.agent_id if terminal else self.origin_id
        terminal_scope = (
            terminal.granted_capabilities if terminal else self.origin_capabilities
        )
        required = frozenset(
            str(value).strip() for value in required_capabilities
        )
        if any(not value for value in required):
            raise ValueError("required capabilities must have non-empty names")
        if not required:
            required = frozenset({_role_capability(terminal.role if terminal else "act")})
        action_scoped = required.issubset(terminal_scope)
        observations.append(
            ConstraintObservation(
                name="action_capability_scope",
                resolution=(
                    ConstraintResolution.PROVEN
                    if action_scoped
                    else ConstraintResolution.REFUTED
                ),
                scope=self.topology_id,
                evidence_ref=f"action:{action_name}",
            )
        )

        if not self._links:
            observations.append(
                ConstraintObservation(
                    name="delegation_lineage",
                    resolution=ConstraintResolution.PROVEN,
                    scope=self.topology_id,
                    evidence_ref=f"origin:{self.origin_id}",
                )
            )

        constraints = ConstraintFrame(
            frame_id=f"delegation:{terminal_id}:{action_name}",
            topology_id=self.topology_id,
            topology_version="1",
            transition_id=action_name,
            required_relations=tuple(
                observation.name for observation in observations
            ),
            observations=tuple(observations),
        )

        any_scope_expansion = any(link.scope_expanded for link in self._links)
        any_self_issued = any(link.self_issued for link in self._links)
        self_auth_pressure = 1.0 if any_self_issued else 0.0
        override_pressure = 0.8 if any_scope_expansion else 0.0

        reversibility = 1.0 if reversible else 0.0
        blast_control = (
            1.0
            if blast_radius < 0.3
            else max(0.0, 1.0 - (blast_radius - 0.3) / 0.7)
        )

        role_category = _role_category(terminal.role if terminal else "act")
        self._trajectory.append(role_category)
        if len(self._trajectory) > 8:
            self._trajectory.pop(0)

        decision = govern(
            GovernanceInput(
                constraints=constraints,
                trajectory=tuple(self._trajectory),
                prp_trail=self._prp_trail,
                guardian=GuardianState(
                    authorization_vector=AuthorizationVector(
                        self_authorization=self_auth_pressure,
                        override_pressure=override_pressure,
                    ),
                ),
                environment=EnvironmentVector(
                    containment=containment,
                    reversibility=reversibility,
                    blast_radius_control=blast_control,
                    externality_control=externality,
                ),
                distillation=DistillationDefenseVector(),
                request_commit=request_commit,
            )
        )

        audit.append(
            f"  terminal {terminal_id}: required={sorted(required)} "
            f"available={sorted(terminal_scope)}"
        )
        if decision.decision in SAFE_DECISIONS:
            self._prp_trail.push(PRPScore(0.5, 0.92, 0.92))
        return decision, audit

    def record_failure(self, *, latency: float = 2.0) -> None:
        self._prp_trail.push(
            PRPScore(
                detection_latency=latency,
                recovery_fidelity=0.3,
                coupling_preservation=0.4,
            )
        )


def _capability_set(values: Iterable[str]) -> frozenset[str]:
    capabilities = frozenset(str(value).strip() for value in values)
    if not capabilities or any(not value for value in capabilities):
        raise ValueError("capability sets must contain non-empty names")
    return capabilities


def _role_capability(role: str) -> str:
    category = _role_category(role)
    return {
        "observe": "observe",
        "modify": "modify",
        "elevate": "execute",
        "critical": "deploy",
    }[category]


def _role_category(role: str) -> str:
    r = role.lower()
    if any(k in r for k in ("plan", "orchestrat", "coordinat", "manag")):
        return "observe"
    if any(k in r for k in ("search", "research", "read", "query", "analyz")):
        return "observe"
    if any(k in r for k in ("write", "report", "summar", "format")):
        return "modify"
    if any(k in r for k in ("act", "execut", "deploy", "run", "call")):
        return "elevate"
    if any(k in r for k in ("admin", "override", "escalat", "delete")):
        return "critical"
    return "modify"
