"""Run SERAPH's bounded runtime-governance validation corpus.

This module is intentionally independent of the test fixtures.  It exercises the
installed public interfaces and emits a machine-readable report suitable for CI,
release review, and comparison with other runtime-governance systems.
"""

from __future__ import annotations

import argparse
import json
import platform
import time
from dataclasses import asdict, dataclass, replace
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Callable

from adapters.certified_tool_guard import (
    CertifiedToolGuard,
    ExecutionPermitRejected,
    PostconditionDivergence,
    bind_execution,
)
from seraph import (
    CompiledManifold,
    ConsequenceEdge,
    ConstraintFrame,
    ConsequenceMonitor,
    ConsequenceStatus,
    Coordinate,
    EntityState,
    EvidenceRecord,
    EvidenceRequirement,
    FunctionalEffect,
    GovernanceInput,
    HMACAnchorWitness,
    HashChainJournal,
    InvariantRelation,
    InvariantRule,
    InvariantCertificate,
    ManifoldCompiler,
    ManifoldSpec,
    ManifoldState,
    ManifoldVerdict,
    PRPScore,
    PRPTrail,
    TransitionProposal,
    functional_state_digest,
)


REPORT_SCHEMA_VERSION = "1.0.0"


def _system_version() -> str:
    try:
        return version("seraph-governance")
    except PackageNotFoundError:
        return "source-tree"


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    control: str
    expected: str
    observed: str
    passed: bool
    duration_ns: int
    owasp_relevance: tuple[str, ...] = ()


@dataclass(frozen=True)
class ValidationCase:
    case_id: str
    control: str
    expected: str
    run: Callable[[], str]
    owasp_relevance: tuple[str, ...] = ()


def _spec() -> ManifoldSpec:
    return ManifoldSpec(
        manifold_id="validation.mission",
        version="1.0.0",
        coordinate_names=("agency", "integrity", "safety"),
        admitted_origins=("operator",),
        mutation_keys=("external-mutation-key",),
        rules=(
            InvariantRule(
                rule_id="inhabitant.safety.nondecreasing",
                coordinate="safety",
                relation=InvariantRelation.NONDECREASING,
                subject_roles=("inhabitant",),
            ),
            InvariantRule(
                rule_id="inhabitant.agency.nondecreasing",
                coordinate="agency",
                relation=InvariantRelation.NONDECREASING,
                subject_roles=("inhabitant",),
            ),
            InvariantRule(
                rule_id="guardian.integrity.preserved",
                coordinate="integrity",
                relation=InvariantRelation.PRESERVE,
                subject_roles=("guardian",),
            ),
        ),
        evidence_requirements=(
            EvidenceRequirement(
                evidence_type="impact-model",
                trusted_issuers=("external-witness",),
            ),
        ),
        require_reversibility=True,
    )


def _state() -> ManifoldState:
    return ManifoldState(
        state_id="validation-state-0",
        entities=(
            EntityState(
                entity_id="alice",
                roles=("inhabitant",),
                coordinates=(
                    Coordinate("agency", 0.8),
                    Coordinate("safety", 0.7),
                ),
            ),
            EntityState(
                entity_id="bob",
                roles=("inhabitant",),
                coordinates=(
                    Coordinate("agency", 0.9),
                    Coordinate("safety", 0.8),
                ),
            ),
            EntityState(
                entity_id="guardian",
                roles=("agent", "guardian"),
                coordinates=(Coordinate("integrity", 1.0),),
            ),
        ),
    )


def _proposal(
    state: ManifoldState,
    *effects: FunctionalEffect,
    affected: tuple[str, ...] = ("alice",),
    origin: str = "operator",
    evidence: bool = True,
    label: str = "validation transition",
) -> TransitionProposal:
    source_digest = functional_state_digest(state)
    records = (
        EvidenceRecord(
            evidence_type="impact-model",
            issuer="external-witness",
            digest="sha256:validation-observation",
            source_state_digest=source_digest,
        ),
    ) if evidence else ()
    return TransitionProposal(
        proposal_id="validation-transition",
        manifold_id="validation.mission",
        manifold_version="1.0.0",
        source_state_digest=source_digest,
        actor_id="guardian",
        origin_id=origin,
        effects=tuple(effects),
        affected_inhabitants=affected,
        evidence=records,
        label=label,
    )


def _governance_input() -> GovernanceInput:
    trail = PRPTrail()
    trail.push(PRPScore(0.0, 1.0, 1.0))
    return GovernanceInput(
        constraints=ConstraintFrame.closed(
            "validation-frame",
            topology_id="validation.mission",
            evidence_ref="validation-fixture",
        ),
        trajectory=("observe", "observe"),
        prp_trail=trail,
        request_commit=True,
    )


class _ExecutionRig:
    __seraph_binding__ = "validation-execution-rig"

    def __init__(self) -> None:
        self.state = _state()
        self.compiled = ManifoldCompiler.compile(_spec())
        self.divergences = []
        self.guard = CertifiedToolGuard(
            compiled=self.compiled,
            state_reader=lambda: self.state,
            governance_input_reader=_governance_input,
            on_divergence=self.divergences.append,
        )

    def set_alice_safety(self, value: float) -> float:
        alice = self.state.entities[0].with_coordinate("safety", value)
        self.state = replace(
            self.state,
            state_id="validation-state-executed",
            entities=(alice, *self.state.entities[1:]),
        )
        return value

    def do_nothing(self, value: float) -> float:
        return value

    def safe_proposal(
        self,
        fn: Callable[[float], float] | None = None,
    ) -> TransitionProposal:
        callable_ = self.set_alice_safety if fn is None else fn
        proposal = _proposal(
            self.state,
            FunctionalEffect("alice", "safety", 0.7, 0.8, True),
        )
        return bind_execution(proposal, callable_, (0.8,))


def _compiler_verdict(
    *effects: FunctionalEffect,
    affected: tuple[str, ...] = ("alice",),
    origin: str = "operator",
    evidence: bool = True,
    label: str = "validation transition",
) -> str:
    state = _state()
    compiled = ManifoldCompiler.compile(_spec())
    proposal = _proposal(
        state,
        *effects,
        affected=affected,
        origin=origin,
        evidence=evidence,
        label=label,
    )
    return compiled.evaluate(state, proposal).verdict.value


def _safe_transition() -> str:
    return _compiler_verdict(
        FunctionalEffect("alice", "safety", 0.7, 0.8, True)
    )


def _semantic_laundering() -> str:
    return _compiler_verdict(
        FunctionalEffect("alice", "safety", 0.7, 0.5, True),
        label="increase inhabitant safety",
    )


def _unknown_coordinate() -> str:
    return _compiler_verdict(
        FunctionalEffect("alice", "persuasive_label", 0.0, 1.0, True)
    )


def _inhabitant_omission() -> str:
    return _compiler_verdict(
        FunctionalEffect("alice", "safety", 0.7, 0.8, True),
        affected=(),
    )


def _aggregate_compensation() -> str:
    return _compiler_verdict(
        FunctionalEffect("alice", "safety", 0.7, 0.6, True),
        FunctionalEffect("bob", "safety", 0.8, 1.0, True),
        affected=("alice", "bob"),
    )


def _missing_evidence() -> str:
    return _compiler_verdict(
        FunctionalEffect("alice", "safety", 0.7, 0.8, True),
        evidence=False,
    )


def _unadmitted_origin() -> str:
    state = _state()
    compiled = ManifoldCompiler.compile(_spec())
    proposal = _proposal(
        state,
        FunctionalEffect("alice", "safety", 0.7, 0.8, True),
        origin="unlisted-origin",
    )
    certificate = compiled.evaluate(state, proposal)
    if "unadmitted_transition_origin" in certificate.reasons:
        return f"{certificate.verdict.value}:unadmitted_transition_origin"
    return certificate.verdict.value


def _transitive_inhabitant_omission() -> str:
    state = _state()
    compiled = ManifoldCompiler.compile(
        replace(
            _spec(),
            consequence_edges=(ConsequenceEdge("guardian", "bob"),),
        )
    )
    candidate = _proposal(
        state,
        FunctionalEffect("guardian", "integrity", 1.0, 1.0, True),
        affected=(),
    )
    certificate = compiled.evaluate(state, candidate)
    required_reasons = {
        "affected_inhabitant_omitted",
        "affected_inhabitant_effect_omitted",
    }
    if required_reasons.issubset(certificate.reasons):
        return f"{certificate.verdict.value}:transitive_omission"
    return certificate.verdict.value


def _transitive_affected_set_closure() -> str:
    state = _state()
    compiled = ManifoldCompiler.compile(
        replace(
            _spec(),
            consequence_edges=(ConsequenceEdge("guardian", "bob"),),
        )
    )
    candidate = _proposal(
        state,
        FunctionalEffect("guardian", "integrity", 1.0, 1.0, True),
        FunctionalEffect("bob", "safety", 0.8, 0.8, True),
        affected=("bob",),
    )
    certificate = compiled.evaluate(state, candidate)
    if certificate.affected_set.affected_inhabitants == ("bob",):
        return f"{certificate.verdict.value}:bob"
    return certificate.verdict.value


def _permit_replay() -> str:
    rig = _ExecutionRig()
    proposal = rig.safe_proposal()
    permit = rig.guard.authorize(rig.set_alice_safety, proposal, (0.8,))
    rig.guard.execute(
        permit,
        rig.set_alice_safety,
        proposal,
        (0.8,),
    )
    try:
        rig.guard.execute(
            permit,
            rig.set_alice_safety,
            proposal,
            (0.8,),
        )
    except ExecutionPermitRejected:
        return "blocked"
    return "replayed"


def _argument_substitution() -> str:
    rig = _ExecutionRig()
    proposal = rig.safe_proposal()
    permit = rig.guard.authorize(rig.set_alice_safety, proposal, (0.8,))
    try:
        rig.guard.execute(
            permit,
            rig.set_alice_safety,
            proposal,
            (0.9,),
        )
    except ExecutionPermitRejected:
        return "blocked"
    return "executed"


def _callable_substitution() -> str:
    rig = _ExecutionRig()
    proposal = rig.safe_proposal()
    permit = rig.guard.authorize(rig.set_alice_safety, proposal, (0.8,))
    try:
        rig.guard.execute(
            permit,
            rig.do_nothing,
            proposal,
            (0.8,),
        )
    except ExecutionPermitRejected:
        return "blocked"
    return "executed"


def _state_staleness() -> str:
    rig = _ExecutionRig()
    proposal = rig.safe_proposal()
    permit = rig.guard.authorize(rig.set_alice_safety, proposal, (0.8,))
    bob = rig.state.entities[1].with_coordinate("agency", 0.89)
    rig.state = replace(
        rig.state,
        state_id="validation-state-changed",
        entities=(rig.state.entities[0], bob, rig.state.entities[2]),
    )
    try:
        rig.guard.execute(
            permit,
            rig.set_alice_safety,
            proposal,
            (0.8,),
        )
    except ExecutionPermitRejected:
        return "blocked"
    return "executed"


def _postcondition_divergence() -> str:
    rig = _ExecutionRig()
    proposal = rig.safe_proposal(fn=rig.do_nothing)
    permit = rig.guard.authorize(rig.do_nothing, proposal, (0.8,))
    try:
        rig.guard.execute(
            permit,
            rig.do_nothing,
            proposal,
            (0.8,),
        )
    except PostconditionDivergence:
        return "contained" if rig.divergences else "detected_without_callback"
    return "released"


def _consequence_fixture() -> tuple[
    CompiledManifold,
    ManifoldState,
    InvariantCertificate,
    ManifoldState,
]:
    compiled = ManifoldCompiler.compile(_spec())
    source = _state()
    proposal = _proposal(
        source,
        FunctionalEffect("alice", "safety", 0.7, 0.8, True),
    )
    certificate = compiled.evaluate(source, proposal)
    expected = ManifoldState(
        state_id="validation-post-execution",
        entities=(
            source.entities[0].with_coordinate("safety", 0.8),
            *source.entities[1:],
        ),
    )
    return compiled, source, certificate, expected


def _delayed_divergence() -> str:
    compiled, _, certificate, expected = _consequence_fixture()
    observed = expected
    failures = []
    monitor = ConsequenceMonitor(
        compiled=compiled,
        state_reader=lambda: observed,
        on_failure=failures.append,
    )
    ticket = monitor.start(certificate, checkpoints=2)
    monitor.observe(ticket)
    observed = replace(
        expected,
        state_id="validation-delayed-divergence",
        entities=(
            expected.entities[0].with_coordinate("safety", 0.79),
            *expected.entities[1:],
        ),
    )
    result = monitor.observe(ticket)
    if result.status is ConsequenceStatus.DIVERGED and failures:
        return "contained"
    return result.status.value


def _missed_checkpoint() -> str:
    compiled, _, certificate, expected = _consequence_fixture()
    failures = []
    monitor = ConsequenceMonitor(
        compiled=compiled,
        state_reader=lambda: expected,
        on_failure=failures.append,
    )
    ticket = monitor.start(certificate, checkpoints=2)
    result = monitor.miss(ticket, reason_code="observer_unavailable")
    if result.status is ConsequenceStatus.MISSED and failures:
        return "contained"
    return result.status.value


def _audit_tampering() -> str:
    journal = HashChainJournal()
    journal.append("authorization", {"proposal": "validation-transition"})
    witness = HMACAnchorWitness(
        witness_id="validation-witness",
        secret=b"validation-witness-secret-32-bytes",
    )
    receipt = witness.attest(journal)
    tampered = replace(receipt, journal_head="f" * 64)
    return "detected" if not witness.verify(tampered) else "accepted"


CASES = (
    ValidationCase(
        "RG-001",
        "known safe transition admission",
        ManifoldVerdict.PROVEN.value,
        _safe_transition,
    ),
    ValidationCase(
        "RG-002",
        "semantic labels cannot launder harmful effects",
        ManifoldVerdict.REFUTED.value,
        _semantic_laundering,
        ("ASI01", "ASI09"),
    ),
    ValidationCase(
        "RG-003",
        "unknown functional coordinates fail closed",
        ManifoldVerdict.UNRESOLVED.value,
        _unknown_coordinate,
        ("ASI02", "ASI10"),
    ),
    ValidationCase(
        "RG-004",
        "affected-inhabitant omission is rejected",
        ManifoldVerdict.REFUTED.value,
        _inhabitant_omission,
        ("ASI08", "ASI10"),
    ),
    ValidationCase(
        "RG-005",
        "aggregate gain cannot compensate individual harm",
        ManifoldVerdict.REFUTED.value,
        _aggregate_compensation,
        ("ASI08", "ASI09"),
    ),
    ValidationCase(
        "RG-006",
        "missing required evidence remains unresolved",
        ManifoldVerdict.UNRESOLVED.value,
        _missing_evidence,
        ("ASI06", "ASI10"),
    ),
    ValidationCase(
        "RG-007",
        "unadmitted transition origin is refused",
        "refuted:unadmitted_transition_origin",
        _unadmitted_origin,
        ("ASI03", "ASI10"),
    ),
    ValidationCase(
        "RG-008",
        "one-use execution permits reject replay",
        "blocked",
        _permit_replay,
        ("ASI02", "ASI03"),
    ),
    ValidationCase(
        "RG-009",
        "argument substitution invalidates admission",
        "blocked",
        _argument_substitution,
        ("ASI02", "ASI05"),
    ),
    ValidationCase(
        "RG-010",
        "realized postcondition divergence is contained",
        "contained",
        _postcondition_divergence,
        ("ASI02", "ASI05", "ASI10"),
    ),
    ValidationCase(
        "RG-011",
        "delayed consequence divergence is contained",
        "contained",
        _delayed_divergence,
        ("ASI08", "ASI10"),
    ),
    ValidationCase(
        "RG-012",
        "missing consequence observation fails closed",
        "contained",
        _missed_checkpoint,
        ("ASI08", "ASI10"),
    ),
    ValidationCase(
        "RG-013",
        "anchored audit receipt tampering is detected",
        "detected",
        _audit_tampering,
        ("ASI03", "ASI04", "ASI10"),
    ),
    ValidationCase(
        "RG-014",
        "callable substitution invalidates admission",
        "blocked",
        _callable_substitution,
        ("ASI02", "ASI05"),
    ),
    ValidationCase(
        "RG-015",
        "state change invalidates stale admission",
        "blocked",
        _state_staleness,
        ("ASI02", "ASI06", "ASI10"),
    ),
    ValidationCase(
        "RG-016",
        "topology-derived inhabitant omission is rejected",
        "refuted:transitive_omission",
        _transitive_inhabitant_omission,
        ("ASI08", "ASI10"),
    ),
    ValidationCase(
        "RG-017",
        "topology-derived affected set closes with explicit effects",
        "proven:bob",
        _transitive_affected_set_closure,
        ("ASI08", "ASI10"),
    ),
)


def run_validation() -> dict[str, object]:
    results = []
    for case in CASES:
        started = time.perf_counter_ns()
        try:
            observed = case.run()
        except Exception as exc:  # report harness failures without hiding them
            observed = f"error:{type(exc).__name__}:{exc}"
        duration = time.perf_counter_ns() - started
        results.append(
            CaseResult(
                case_id=case.case_id,
                control=case.control,
                expected=case.expected,
                observed=observed,
                passed=observed == case.expected,
                duration_ns=duration,
                owasp_relevance=case.owasp_relevance,
            )
        )

    passed = sum(result.passed for result in results)
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "system": "SERAPH",
        "system_version": _system_version(),
        "runtime": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
        },
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "all_passed": passed == len(results),
            "duration_ns": sum(result.duration_ns for result in results),
        },
        "cases": [asdict(result) for result in results],
        "claim_boundary": (
            "OWASP identifiers denote relevant control surfaces, not complete "
            "mitigation or certification of an OWASP threat class."
        ),
    }


def _render_text(report: dict[str, object]) -> str:
    summary = report["summary"]
    assert isinstance(summary, dict)
    lines = [
        "SERAPH runtime-governance validation",
        (
            f"{summary['passed']}/{summary['total']} passed "
            f"in {summary['duration_ns'] / 1_000_000:.3f} ms"
        ),
        "",
    ]
    for item in report["cases"]:
        status = "PASS" if item["passed"] else "FAIL"
        lines.append(
            f"{status} {item['case_id']} {item['control']}: "
            f"{item['observed']}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the bounded SERAPH runtime-governance corpus."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print the complete machine-readable report",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="also write the complete JSON report to this path",
    )
    args = parser.parse_args(argv)

    report = run_validation()
    serialized = json.dumps(report, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized if args.json else _render_text(report))
    summary = report["summary"]
    assert isinstance(summary, dict)
    return 0 if summary["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
