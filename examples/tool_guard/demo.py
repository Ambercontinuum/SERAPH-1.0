#!/usr/bin/env python3
"""Tool guard demo.

SERAPH wraps Python functions as a decorator. The guarded functions never
execute unless invariants close. The agent cannot route around the guard
by calling the function directly — the guard IS the function.

Run: python examples/tool_guard/demo.py
"""

from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from adapters.tool_guard import ToolCall, ToolGuard, ToolRisk, SAFE_DECISIONS
from seraph import Decision

guard = ToolGuard(agent_id="tool_agent")

W = 72


def section(title: str) -> None:
    print()
    print(f"  {title}")
    print("  " + "-" * 50)


def attempt(label: str, call: ToolCall, *, success: bool = True, latency: float = 0.5) -> None:
    decision = guard.evaluate(call)
    passed = decision.decision in SAFE_DECISIONS
    gate = "PASSED " if passed else "BLOCKED"
    reason = decision.reasons[0] if decision.reasons else ""
    layer = decision.operating_layer.value
    posture = decision.deployment_posture.active_path

    print(f"  [{gate}]  {decision.decision.value:>10}  {layer:<11}  {posture:<8}  {label}")
    print(f"            reason={reason}  env={decision.environment.safety_score:.2f}  "
          f"streak={guard._blocked_streak}")

    if passed:
        guard.record_outcome(success=success, latency=latency)


def attempt_decorated() -> None:
    """Show the decorator catching a destructive call at the function level."""

    @guard.protect
    def read_config(path: str) -> dict:
        return {"loaded": path}

    @guard.protect
    def delete_user_records(table: str, user_id: int) -> int:
        return 0  # never reached

    @guard.protect
    def drop_production_database(name: str) -> None:
        pass  # never reached

    section("PHASE 4: Decorator — guard IS the function")

    try:
        result = read_config("config.yaml")
        print(f"  [PASSED ]       allow  maneuver    embedded  read_config -> {result}")
        guard.record_outcome(success=True)
    except PermissionError as e:
        print(f"  [BLOCKED]  {e}")

    try:
        delete_user_records("users", 42)
        print("  [PASSED ]  delete_user_records executed")
    except PermissionError as e:
        print(f"  [BLOCKED]  {e}")

    try:
        drop_production_database("prod_db")
        print("  [PASSED ]  drop_production_database executed")
    except PermissionError as e:
        print(f"  [BLOCKED]  {e}")


def main() -> None:
    print("=" * W)
    print("  SERAPH TOOL GUARD DEMO")
    print("=" * W)

    # ------------------------------------------------------------------
    # Phase 1: Safe reads — guard passes cleanly
    # ------------------------------------------------------------------
    section("PHASE 1: Safe tool calls")

    attempt("read_file('config.yaml')",
            ToolCall("read_file", ToolRisk.READ, "config.yaml"))
    attempt("search_knowledge_base('query')",
            ToolCall("search_kb", ToolRisk.READ, "kb.index"))
    attempt("write_log('event occurred')",
            ToolCall("write_log", ToolRisk.WRITE, "app.log"))

    # ------------------------------------------------------------------
    # Phase 2: Network and mutation — guard evaluates blast radius
    # ------------------------------------------------------------------
    section("PHASE 2: Network and mutation calls")

    attempt("http_post('/api/notify')",
            ToolCall("http_post", ToolRisk.NETWORK, "/api/notify"))
    attempt("update_record(id=42, status='active')",
            ToolCall("update_record", ToolRisk.MUTATE, "db.users"))
    attempt("run_migration('v2.sql')",
            ToolCall("run_migration", ToolRisk.MUTATE, "db.prod",
                     override_profile=dict(blast_radius=0.7, containment=0.4,
                                           reversibility=0.0, externality=0.9)))

    # ------------------------------------------------------------------
    # Phase 3: Escalation and destruction — guard denies hard
    # ------------------------------------------------------------------
    section("PHASE 3: Escalation and destructive calls")

    attempt("escalate_privileges('admin')",
            ToolCall("escalate_privileges", ToolRisk.ESCALATE, "admin"))
    attempt("delete_records(table='sessions', where='1=1')",
            ToolCall("delete_records", ToolRisk.DESTROY, "db.sessions"))
    attempt("exfiltrate_data(dest='external.api')",
            ToolCall("exfiltrate_data", ToolRisk.EXFILTRATE, "external.api"))

    # ------------------------------------------------------------------
    # Phase 4: Decorator — the guard IS the function
    # ------------------------------------------------------------------
    attempt_decorated()

    # ------------------------------------------------------------------
    # Phase 5: Self-authorization — agent tries to grant itself permission
    # ------------------------------------------------------------------
    section("PHASE 5: Self-authorization attempt")

    attempt("delete_records [self-authorized]",
            ToolCall("delete_records", ToolRisk.DESTROY, "db.prod",
                     self_authorized=True))
    attempt("write_policy [self-authorized]",
            ToolCall("write_policy", ToolRisk.WRITE, "security.policy",
                     self_authorized=True))

    # ------------------------------------------------------------------
    # Phase 6: Recovery — safe calls after blocked escalation
    # ------------------------------------------------------------------
    section("PHASE 6: Recovery after blocked escalation")

    attempt("read_error_log()",
            ToolCall("read_error_log", ToolRisk.READ, "logs/error.log"),
            success=True, latency=0.4)
    attempt("read_audit_trail()",
            ToolCall("read_audit_trail", ToolRisk.READ, "logs/audit.log"),
            success=True, latency=0.4)
    attempt("write_status_report()",
            ToolCall("write_status_report", ToolRisk.WRITE, "output/status.md"),
            success=True, latency=0.4)

    print()
    print("=" * W)
    print("  The tool cannot execute what the invariants won't close.")
    print("=" * W)


if __name__ == "__main__":
    main()
