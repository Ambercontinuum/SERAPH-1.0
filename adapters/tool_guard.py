"""Tool guard adapter for SERAPH governance.

Intercepts tool calls before execution and evaluates them against SERAPH
invariants. Designed to wrap any function, API call, or shell command an
agent might invoke. The guard is stateful — it maintains a persistent
PRPTrail and call history so SENTINEL reads geometry across the full
tool use session.

Usage:
    guard = ToolGuard(agent_id="my_agent")

    @guard.protect
    def delete_records(table: str, where: str) -> int:
        ...

    # Or evaluate manually:
    decision = guard.evaluate(ToolCall(name="rm -rf", ...))
    if decision.decision in SAFE_DECISIONS:
        execute()
"""

from __future__ import annotations

import functools
from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from typing import Any, Callable

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

# REPAIR is a routing instruction, not an execution permit. This adapter is
# deny-by-default and has no independent retry or rollback path.
SAFE_DECISIONS = {Decision.ALLOW, Decision.COMMIT}


class ToolRisk(Enum):
    """Structural risk profile of a tool call."""
    READ       = "read"        # No side effects
    WRITE      = "write"       # Local, reversible side effects
    NETWORK    = "network"     # External contact, limited blast radius
    MUTATE     = "mutate"      # State change, partially reversible
    ESCALATE   = "escalate"    # Privilege or scope expansion
    DESTROY    = "destroy"     # Irreversible deletion or termination
    EXFILTRATE = "exfiltrate"  # Data leaving the system boundary


# Default risk profiles for common tool categories
_RISK_PROFILE: dict[ToolRisk, dict[str, float]] = {
    ToolRisk.READ:       dict(blast_radius=0.0, containment=1.0, reversibility=1.0, externality=1.0),
    ToolRisk.WRITE:      dict(blast_radius=0.0, containment=1.0, reversibility=1.0, externality=1.0),
    ToolRisk.NETWORK:    dict(blast_radius=0.4, containment=0.7, reversibility=0.7, externality=0.6),
    ToolRisk.MUTATE:     dict(blast_radius=0.6, containment=0.6, reversibility=0.4, externality=0.9),
    ToolRisk.ESCALATE:   dict(blast_radius=0.8, containment=0.4, reversibility=0.2, externality=0.8),
    ToolRisk.DESTROY:    dict(blast_radius=1.0, containment=0.0, reversibility=0.0, externality=1.0),
    ToolRisk.EXFILTRATE: dict(blast_radius=0.7, containment=0.2, reversibility=0.0, externality=0.0),
}

_RISK_CATEGORY: dict[ToolRisk, str] = {
    ToolRisk.READ:       "observe",
    ToolRisk.WRITE:      "modify",
    ToolRisk.NETWORK:    "modify",
    ToolRisk.MUTATE:     "elevate",
    ToolRisk.ESCALATE:   "critical",
    ToolRisk.DESTROY:    "critical",
    ToolRisk.EXFILTRATE: "critical",
}


@dataclass
class ToolCall:
    name: str
    risk: ToolRisk
    target: str = ""
    self_authorized: bool = False
    override_profile: dict[str, float] | None = None


@dataclass
class ToolGuard:
    """Stateful SERAPH governance wrapper for tool execution.

    Wraps tool calls with invariant evaluation before execution. The guard
    maintains a persistent PRPTrail so SENTINEL reads the geometric signature
    of the tool-use session, not just individual calls in isolation.
    """

    agent_id: str
    constraint_topology: str = "seraph.tools"

    _call_history: list[str] = field(default_factory=list, repr=False)
    _prp_trail: PRPTrail = field(default_factory=PRPTrail, repr=False)
    _constraints: ConstraintFrame | None = field(default=None, repr=False)
    _blocked_streak: int = field(default=0, repr=False)

    def __post_init__(self) -> None:
        self._constraints = ConstraintFrame.closed(
            frame_id=f"tool-session:{self.agent_id}",
            topology_id=self.constraint_topology,
            transition_id=f"tool-session:{self.agent_id}",
        )
        self._call_history = ["observe", "observe"]
        for _ in range(2):
            self._prp_trail.push(PRPScore(0.5, 0.95, 0.95))

    def evaluate(self, call: ToolCall) -> GovernanceDecision:
        """Evaluate a tool call before execution.

        This example adapter has no concurrency lock between evaluation and a
        caller's later execution. Use the certified tool guard when freshness
        and exact proof/execution binding are required.
        """
        category = _RISK_CATEGORY[call.risk]
        if call.self_authorized:
            category = "critical"

        self._call_history.append(category)
        if len(self._call_history) > 8:
            self._call_history.pop(0)

        profile = _attenuated_profile(
            _RISK_PROFILE[call.risk],
            call.override_profile,
        )

        inp = GovernanceInput(
            constraints=self._constraints,
            trajectory=tuple(self._call_history),
            prp_trail=self._prp_trail,
            guardian=self._build_guardian(call),
            environment=EnvironmentVector(
                containment=profile["containment"],
                reversibility=profile["reversibility"],
                blast_radius_control=max(0.0, 1.0 - profile["blast_radius"]),
                externality_control=profile["externality"],
            ),
            distillation=DistillationDefenseVector(),
        )

        decision = govern(inp)

        if decision.decision in SAFE_DECISIONS:
            self._blocked_streak = 0
        else:
            self._blocked_streak += 1

        return decision

    def record_outcome(self, *, success: bool, latency: float = 0.5) -> None:
        """Record execution outcome after an allowed tool call.

        ``success`` is caller-reported. This lightweight adapter does not
        independently verify that realized state matches the proposed effect.
        """
        self._prp_trail.push(PRPScore(
            detection_latency=latency,
            recovery_fidelity=0.95 if success else 0.3,
            coupling_preservation=0.95 if success else 0.5,
        ))

    def protect(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator: infer risk from function name and block if SERAPH denies.

        Wrapped calls are gated, but this convenience decorator does not prove
        that unwrapped paths are absent, sandbox side effects, or bind argument
        values into a fresh certificate. Use ``CertifiedToolGuard`` for the
        stronger registered-capability path.
        """
        risk = _infer_risk(fn.__name__)

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # This lightweight path classifies by function name; argument
            # binding belongs to the certified execution adapter.
            call = ToolCall(name=fn.__name__, risk=risk, target=str(args[:1]))
            decision = self.evaluate(call)
            if decision.decision not in SAFE_DECISIONS:
                raise PermissionError(
                    f"SERAPH blocked '{fn.__name__}': {decision.reasons[0]} "
                    f"[{decision.decision.value}]"
                )
            result = fn(*args, **kwargs)
            self.record_outcome(success=True)
            return result

        return wrapper

    def _build_guardian(self, call: ToolCall) -> GuardianState:
        self_auth = 1.0 if call.self_authorized else 0.0
        override = 0.8 if call.risk == ToolRisk.ESCALATE else 0.0
        return GuardianState(
            authorization_vector=AuthorizationVector(
                self_authorization=self_auth,
                override_pressure=override,
            ),
        )


def _infer_risk(name: str) -> ToolRisk:
    """Infer tool risk from function name without semantic labels."""
    n = name.lower()
    if any(k in n for k in ("delete", "remove", "drop", "destroy", "kill", "terminate", "truncate")):
        return ToolRisk.DESTROY
    if any(k in n for k in ("exfil", "export", "extract", "upload", "send", "transmit")):
        return ToolRisk.EXFILTRATE
    if any(k in n for k in ("escalat", "sudo", "admin", "override", "bypass", "elevat")):
        return ToolRisk.ESCALATE
    if any(k in n for k in ("exec", "run", "mutate", "modify", "update", "patch", "migrate")):
        return ToolRisk.MUTATE
    if any(k in n for k in ("post", "put", "request", "call", "fetch", "http", "api", "notify")):
        return ToolRisk.NETWORK
    if any(k in n for k in ("write", "save", "create", "insert", "append", "log")):
        return ToolRisk.WRITE
    return ToolRisk.READ


def _attenuated_profile(
    baseline: dict[str, float],
    observation: dict[str, float] | None,
) -> dict[str, float]:
    """Apply telemetry without letting a caller weaken the risk baseline."""

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
