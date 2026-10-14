"""Scenario corpus runner for SERAPH."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from adapters.delegation import DelegationChain
from seraph.__main__ import input_from_dict
from seraph import GovernanceDecision, govern

from .trace import render_trace


DEFAULT_SCENARIO_PATH = Path(__file__).resolve().parent / "scenarios"


@dataclass(frozen=True)
class ScenarioResult:
    name: str
    passed: bool
    decision: GovernanceDecision
    failures: tuple[str, ...]
    trace: str


def _scenario_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(path.glob("*.json"))


def _expectation_failures(
    decision: GovernanceDecision,
    expected: dict[str, Any],
) -> tuple[str, ...]:
    checks = {
        "decision": decision.decision.value,
        "operating_layer": decision.operating_layer.value,
        "posture": decision.deployment_posture.active_path,
        "constraints_closed": decision.constraints.closed,
        "flux_coherent": decision.flux.coherent,
        "guardian_coherent": decision.guardian.coherent,
        "environment_safe": decision.environment.safe,
        "distillation_authenticity": decision.distillation.authenticity.value,
        "relocation_admissible": decision.relocation.admissible,
    }

    failures: list[str] = []
    for key, expected_value in expected.items():
        if key == "reasons_include":
            missing = [reason for reason in expected_value if reason not in decision.reasons]
            if missing:
                failures.append(f"missing reasons: {', '.join(missing)}")
            continue
        if key not in checks:
            failures.append(f"unknown expectation: {key}")
            continue
        actual = checks[key]
        if actual != expected_value:
            failures.append(f"{key}: expected {expected_value!r}, got {actual!r}")
    return tuple(failures)


def _delegation_decision(data: dict[str, Any]) -> GovernanceDecision:
    chain_data = data["chain"]
    chain = DelegationChain(
        origin_id=str(chain_data.get("origin_id", "origin")),
        origin_capabilities=frozenset(
            str(item)
            for item in chain_data.get(
                "origin_capabilities",
                ["observe", "modify", "execute", "deploy", "delegate"],
            )
        ),
    )
    for link in chain_data.get("links", []):
        chain.add(
            str(link["agent_id"]),
            granted_capabilities=tuple(
                str(item) for item in link["granted_capabilities"]
            ),
            role=str(link["role"]),
            issued_by=(
                str(link["issued_by"]) if link.get("issued_by") is not None else None
            ),
            self_issued=bool(link.get("self_issued", False)),
        )

    action = data.get("action", {})
    decision, _audit = chain.evaluate_action(
        action_name=str(action.get("name", "action")),
        required_capabilities=tuple(
            str(item) for item in action.get("required_capabilities", [])
        ),
        blast_radius=float(action.get("blast_radius", 0.0)),
        containment=float(action.get("containment", 1.0)),
        reversible=bool(action.get("reversible", True)),
        externality=float(action.get("externality", 1.0)),
        request_commit=bool(action.get("request_commit", False)),
    )
    return decision


def load_and_run(path: Path) -> ScenarioResult:
    data = json.loads(path.read_text(encoding="utf-8"))
    name = str(data.get("name", path.stem))
    kind = str(data.get("kind", "governance"))

    if kind == "governance":
        decision = govern(input_from_dict(data["input"]))
    elif kind == "delegation":
        decision = _delegation_decision(data)
    else:
        raise ValueError(f"{path}: unknown scenario kind {kind!r}")

    failures = _expectation_failures(decision, data.get("expected", {}))
    passed = not failures
    trace = render_trace(name, decision, passed=passed)
    if failures:
        trace = trace + "\n" + "\n".join(f"EXPECTATION: {failure}" for failure in failures)
    return ScenarioResult(
        name=name,
        passed=passed,
        decision=decision,
        failures=failures,
        trace=trace,
    )


def run_path(path: Path) -> list[ScenarioResult]:
    files = _scenario_files(path)
    if not files:
        raise ValueError(f"No scenario files found at {path}")
    return [load_and_run(file) for file in files]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run SERAPH scenario traces.")
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        help="Scenario JSON file or directory (defaults to bundled corpus).",
    )
    parser.add_argument("--quiet", action="store_true", help="Only print summary.")
    args = parser.parse_args(argv)

    try:
        results = run_path(
            DEFAULT_SCENARIO_PATH if args.path is None else args.path
        )
    except Exception as exc:
        print(f"seraph-demo: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        for index, result in enumerate(results):
            if index:
                print()
            print(result.trace)

    passed = sum(1 for result in results if result.passed)
    total = len(results)
    print(f"\nSUMMARY: {passed}/{total} scenarios passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
