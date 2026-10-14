"""Export deterministic, browser-readable evidence from the real SERAPH path."""

from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import json
from pathlib import Path
from typing import Any

from seraph import (
    ConsequenceEdge,
    ConsequenceMonitor,
    Coordinate,
    EntityState,
    FunctionalEffect,
    InvariantRelation,
    InvariantRule,
    ManifoldCompiler,
    ManifoldSpec,
    ManifoldState,
    TransitionProposal,
    functional_state_digest,
)


DEMO_SCHEMA_VERSION = "1.0.0"
DEFAULT_OUTPUT = Path("docs/demo/seraph-demo-data.js")


def _state() -> ManifoldState:
    return ManifoldState(
        state_id="demo-state-0",
        entities=(
            EntityState("service", ("system",), (Coordinate("safety", 1.0),)),
            EntityState("relay", ("system",), (Coordinate("safety", 1.0),)),
            EntityState("alice", ("inhabitant",), (Coordinate("safety", 0.9),)),
            EntityState("bob", ("inhabitant",), (Coordinate("safety", 0.8),)),
            EntityState("guardian", ("guardian",), (Coordinate("integrity", 1.0),)),
        ),
    )


def _spec(*edges: ConsequenceEdge) -> ManifoldSpec:
    return ManifoldSpec(
        manifold_id="demo.public",
        version="1.0.0",
        coordinate_names=("integrity", "safety"),
        admitted_origins=("operator",),
        mutation_keys=("demo-topology-authority",),
        rules=(
            InvariantRule(
                "inhabitant.safety.nondecreasing",
                "safety",
                InvariantRelation.NONDECREASING,
                subject_roles=("inhabitant",),
            ),
            InvariantRule(
                "guardian.integrity.preserved",
                "integrity",
                InvariantRelation.PRESERVE,
                subject_roles=("guardian",),
            ),
        ),
        consequence_edges=edges,
        require_reversibility=True,
    )


def _proposal(
    state: ManifoldState,
    proposal_id: str,
    label: str,
    effects: tuple[FunctionalEffect, ...],
    affected: tuple[str, ...],
) -> TransitionProposal:
    return TransitionProposal(
        proposal_id=proposal_id,
        manifold_id="demo.public",
        manifold_version="1.0.0",
        source_state_digest=functional_state_digest(state),
        actor_id="demo-agent",
        origin_id="operator",
        effects=effects,
        affected_inhabitants=affected,
        label=label,
    )


def _certificate_record(
    *,
    scenario_id: str,
    title: str,
    summary: str,
    spec: ManifoldSpec,
    state: ManifoldState,
    proposal: TransitionProposal,
) -> dict[str, Any]:
    compiled = ManifoldCompiler.compile(spec)
    certificate = compiled.evaluate(state, proposal)
    return {
        "scenario_id": scenario_id,
        "title": title,
        "summary": summary,
        "label": proposal.label,
        "topology": {
            "manifold_id": spec.manifold_id,
            "version": spec.version,
            "digest": compiled.digest,
            "edges": [asdict(edge) for edge in compiled.spec.consequence_edges],
        },
        "effects": [asdict(effect) for effect in proposal.effects],
        "declared_affected": list(proposal.affected_inhabitants),
        "derived_affected": list(certificate.affected_set.affected_inhabitants),
        "reached_entities": list(certificate.affected_set.reached_entities),
        "unresolved_entities": list(certificate.affected_set.unresolved_entities),
        "verdict": certificate.verdict.value,
        "permit_eligible": certificate.proven,
        "proposal_digest": certificate.proposal_digest,
        "affected_set_digest": certificate.affected_set.topology_digest,
        "reasons": list(certificate.reasons),
        "checks": [
            {
                "rule_id": result.rule_id,
                "verdict": result.verdict.value,
                "reason": result.reason,
                "subjects": list(result.subjects),
            }
            for result in certificate.results
        ],
    }


def build_demo_data() -> dict[str, Any]:
    """Build the checked-in website dataset from live SERAPH evaluation."""

    state = _state()
    topology = (
        ConsequenceEdge("service", "relay"),
        ConsequenceEdge("relay", "bob"),
    )
    spec = _spec(*topology)
    service_effect = FunctionalEffect("service", "safety", 1.0, 0.9, True)
    bob_preserved = FunctionalEffect("bob", "safety", 0.8, 0.8, True)

    admitted = _proposal(
        state,
        "demo-admitted",
        "Deploy maintenance patch",
        (service_effect, bob_preserved),
        ("bob",),
    )
    omitted = _proposal(
        state,
        "demo-omitted",
        "Deploy maintenance patch",
        (service_effect,),
        (),
    )
    harmful = _proposal(
        state,
        "demo-laundered",
        "Protect every inhabitant",
        (
            service_effect,
            FunctionalEffect("bob", "safety", 0.8, 0.4, True),
        ),
        ("bob",),
    )
    relabeled_harm = replace(harmful, label="Reduce Bob's safety")
    harmful_certificate = ManifoldCompiler.compile(spec).evaluate(state, harmful)
    relabeled_certificate = ManifoldCompiler.compile(spec).evaluate(
        state,
        relabeled_harm,
    )

    unknown_spec = _spec(ConsequenceEdge("service", "external-neighbor"))
    unknown = _proposal(
        state,
        "demo-unresolved",
        "Deploy outside current observation",
        (service_effect,),
        (),
    )

    records = [
        _certificate_record(
            scenario_id="closed",
            title="Complete transition",
            summary="The topology-derived inhabitant and its expected effect are explicit.",
            spec=spec,
            state=state,
            proposal=admitted,
        ),
        _certificate_record(
            scenario_id="omitted",
            title="Omitted downstream inhabitant",
            summary="The proposal omits Bob, but topology reaches Bob through the relay.",
            spec=spec,
            state=state,
            proposal=omitted,
        ),
        _certificate_record(
            scenario_id="laundered",
            title="Benevolent label, harmful effect",
            summary="The label says protection; the functional effect decreases Bob's safety.",
            spec=spec,
            state=state,
            proposal=harmful,
        ),
        _certificate_record(
            scenario_id="unresolved",
            title="Unknown topology endpoint",
            summary="A required endpoint is absent from observed state, so the frame stays open.",
            spec=unknown_spec,
            state=state,
            proposal=unknown,
        ),
    ]
    records[2]["label_ignored_digest_match"] = (
        harmful_certificate.proposal_digest
        == relabeled_certificate.proposal_digest
    )

    compiled = ManifoldCompiler.compile(spec)
    certificate = compiled.evaluate(state, admitted)
    expected_entities = state.entity_map()
    expected_entities["service"] = expected_entities["service"].with_coordinate(
        "safety",
        0.9,
    )
    expected = ManifoldState(
        state_id="demo-state-expected",
        entities=tuple(
            expected_entities[entity_id]
            for entity_id in sorted(expected_entities)
        ),
    )
    observed = expected
    contained = []
    monitor = ConsequenceMonitor(
        compiled=compiled,
        state_reader=lambda: observed,
        on_failure=contained.append,
    )
    ticket = monitor.start(certificate, checkpoints=2)
    first = monitor.observe(ticket)
    observed = replace(
        expected,
        state_id="demo-state-diverged",
        entities=tuple(
            entity.with_coordinate("safety", 0.7)
            if entity.entity_id == "bob"
            else entity
            for entity in expected.entities
        ),
    )
    second = monitor.observe(ticket)
    records.append(
        {
            **records[0],
            "scenario_id": "delayed",
            "title": "Delayed consequence divergence",
            "summary": "Admission closes, then a later observation diverges and containment fires.",
            "verdict": "proven_then_diverged",
            "permit_eligible": True,
            "reasons": (
                list(second.report.reasons)
                if second.report is not None
                else []
            ),
            "consequence": {
                "first_checkpoint": first.status.value,
                "second_checkpoint": second.status.value,
                "contained": bool(contained),
            },
        }
    )

    return {
        "schema_version": DEMO_SCHEMA_VERSION,
        "generator": "seraph_demo.web_export.build_demo_data",
        "fixture_notice": (
            "Deterministic fixture generated by the real SERAPH compiler and "
            "consequence monitor; the browser only renders these results."
        ),
        "scenarios": records,
    }


def render_javascript(data: dict[str, Any]) -> str:
    encoded = json.dumps(data, indent=2, sort_keys=True)
    return f"window.SERAPH_DEMO_DATA = {encoded};\n"


def write_demo_data(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_javascript(build_demo_data()), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export deterministic SERAPH evidence for the static web demo."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    write_demo_data(args.output)
    print(f"wrote SERAPH demo evidence to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
