#!/usr/bin/env python3
"""Agent runtime governance demo.

An autonomous agent attempts a sequence of actions with escalating risk.
SERAPH evaluates each action before execution. The agent cannot proceed
without invariant closure — no matter how it escalates.

Run: python examples/agent_runtime/demo.py
"""

from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from adapters.agent_runtime import ActionType, AgentAction, AgentGovernor
from seraph import Decision

DECISIONS = {
    Decision.ALLOW:     "  ALLOW   ",
    Decision.COMMIT:    "  COMMIT  ",
    Decision.WITNESS:   "  WITNESS ",
    Decision.REPAIR:    "  REPAIR  ",
    Decision.STABILIZE: " STABILIZE",
    Decision.DENY:      "  DENY    ",
}

BLOCKED = {Decision.DENY, Decision.WITNESS, Decision.STABILIZE}


def run(governor: AgentGovernor, action: AgentAction, *, simulate_success: bool = True,
        recovery: float = 1.0, latency: float = 0.5, coupling: float = 1.0) -> bool:
    decision = governor.evaluate(action)
    verdict = DECISIONS[decision.decision]
    layer = decision.operating_layer.value
    posture = decision.deployment_posture.active_path
    reason = decision.reasons[0] if decision.reasons else ""

    blocked = decision.decision in BLOCKED
    gate = "BLOCKED" if blocked else "PASSED "

    print(f"  [{gate}] {verdict}  layer={layer:<11}  path={posture:<8}  {action.name}")
    print(f"           reason={reason}  env={decision.environment.safety_score:.2f}  "
          f"prp={decision.prp_overall or 0.0:.2f}")

    if not blocked:
        governor.record_outcome(
            success=simulate_success,
            detection_latency=latency,
            recovery_quality=recovery,
            coupling=coupling,
        )

    return not blocked


def main() -> None:
    W = 72
    print("=" * W)
    print("  SERAPH AGENT RUNTIME GOVERNANCE DEMO")
    print("=" * W)

    governor = AgentGovernor(agent_id="agent_alpha")

    # ------------------------------------------------------------------
    # Phase 1: Normal operations — agent is healthy, actions are safe
    # ------------------------------------------------------------------
    print()
    print("  PHASE 1: Normal operations")
    print("  " + "-" * 50)

    run(governor, AgentAction(
        name="Read config file",
        action_type=ActionType.READ,
        target="config.yaml",
        reversible=True, blast_radius=0.0, containment=1.0,
    ))

    run(governor, AgentAction(
        name="Query knowledge base",
        action_type=ActionType.QUERY,
        target="kb.index",
        reversible=True, blast_radius=0.0, containment=1.0,
    ))

    run(governor, AgentAction(
        name="Write analysis report",
        action_type=ActionType.WRITE,
        target="output/report.md",
        reversible=True, blast_radius=0.1, containment=1.0,
    ))

    run(governor, AgentAction(
        name="Commit analysis",
        action_type=ActionType.COMMIT,
        target="output/report.md",
        reversible=True, blast_radius=0.1, containment=1.0,
        requires_commit=True,
    ))

    # ------------------------------------------------------------------
    # Phase 2: Escalation — agent attempts higher-risk actions
    # ------------------------------------------------------------------
    print()
    print("  PHASE 2: Risk escalation")
    print("  " + "-" * 50)

    run(governor, AgentAction(
        name="Deploy to staging",
        action_type=ActionType.DEPLOY,
        target="staging.env",
        reversible=True, blast_radius=0.4, containment=0.8, externality=0.8,
    ), simulate_success=True, recovery=0.7, latency=1.5)

    run(governor, AgentAction(
        name="Execute migration script",
        action_type=ActionType.EXECUTE,
        target="db/migrate.sql",
        reversible=False, blast_radius=0.6, containment=0.7,
    ), simulate_success=True, recovery=0.6, latency=2.0)

    run(governor, AgentAction(
        name="Deploy to production",
        action_type=ActionType.DEPLOY,
        target="prod.env",
        reversible=False, blast_radius=0.8, containment=0.5, externality=0.6,
    ))

    # ------------------------------------------------------------------
    # Phase 3: Self-authorization attempt — agent tries to grant itself
    #          permission it was not given
    # ------------------------------------------------------------------
    print()
    print("  PHASE 3: Self-authorization attempt")
    print("  " + "-" * 50)

    run(governor, AgentAction(
        name="Override safety constraint",
        action_type=ActionType.OVERRIDE,
        target="safety.policy",
        reversible=False, blast_radius=0.9, containment=0.4,
        proposal_source="self",
    ))

    run(governor, AgentAction(
        name="Self-authorize deployment",
        action_type=ActionType.DEPLOY,
        target="prod.env",
        reversible=False, blast_radius=0.9, containment=0.3,
        proposal_source="self",
    ))

    # ------------------------------------------------------------------
    # Phase 4: Recovery — agent returns to safe operations after errors
    # ------------------------------------------------------------------
    print()
    print("  PHASE 4: Recovery path")
    print("  " + "-" * 50)

    run(governor, AgentAction(
        name="Read error log",
        action_type=ActionType.READ,
        target="logs/error.log",
        reversible=True, blast_radius=0.0, containment=1.0,
    ), simulate_success=True, recovery=0.85, latency=0.5)

    run(governor, AgentAction(
        name="Query diagnostics",
        action_type=ActionType.QUERY,
        target="diagnostics.api",
        reversible=True, blast_radius=0.0, containment=1.0,
    ), simulate_success=True, recovery=0.92, latency=0.5)

    run(governor, AgentAction(
        name="Write recovery report",
        action_type=ActionType.WRITE,
        target="output/recovery.md",
        reversible=True, blast_radius=0.05, containment=1.0,
    ), simulate_success=True, recovery=0.95, latency=0.5)

    # ------------------------------------------------------------------
    # Phase 5: Delete attempt — irreversible, high blast radius
    # ------------------------------------------------------------------
    print()
    print("  PHASE 5: Destructive action attempt")
    print("  " + "-" * 50)

    run(governor, AgentAction(
        name="Delete production database",
        action_type=ActionType.DELETE,
        target="prod.db",
        reversible=False, blast_radius=1.0, containment=0.0, externality=0.0,
    ))

    print()
    print("=" * W)
    print("  The kernel did not move. The agent did.")
    print("=" * W)


if __name__ == "__main__":
    main()
