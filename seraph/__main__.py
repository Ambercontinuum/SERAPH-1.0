"""Command line interface for the SERAPH invariant kernel."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from . import (
    AuthorizationVector,
    ConstraintFrame,
    ConstraintObservation,
    ConstraintResolution,
    DistillationDefenseVector,
    EvidenceVector,
    EnvironmentVector,
    GovernanceInput,
    GuardianMode,
    GuardianState,
    IntegrityVector,
    OperatingLayer,
    PRPScore,
    PRPTrail,
    RelocationRequest,
    govern,
)


DEFAULT_INPUT_PATH = (
    Path(__file__).resolve().parent / "examples" / "release_gate_commit.json"
)


def _enum_value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return _enum_value(value)


def _constraints(data: dict[str, Any]) -> ConstraintFrame:
    if "observations" not in data:
        return ConstraintFrame.closed(
            str(data.get("frame_id", "cli-frame")),
            topology_id=str(data.get("topology_id", "seraph.cli")),
            topology_version=str(data.get("topology_version", "1")),
            transition_id=str(data.get("transition_id", "cli-transition")),
            evidence_ref=str(data.get("evidence_ref", "cli-declared-profile")),
        )
    return ConstraintFrame(
        frame_id=str(data.get("frame_id", "cli-frame")),
        topology_id=str(data.get("topology_id", "seraph.cli")),
        topology_version=str(data.get("topology_version", "1")),
        transition_id=str(data.get("transition_id", "cli-transition")),
        required_relations=tuple(
            str(name) for name in data.get("required_relations", [])
        ),
        observations=tuple(
            ConstraintObservation(
                name=str(item["name"]),
                resolution=ConstraintResolution(
                    item.get("resolution", ConstraintResolution.PROVEN.value)
                ),
                scope=str(item.get("scope", data.get("topology_id", "seraph.cli"))),
                horizon=str(item.get("horizon", "transition")),
                evidence_ref=(
                    str(item["evidence_ref"])
                    if item.get("evidence_ref") is not None
                    else None
                ),
            )
            for item in data.get("observations", [])
        ),
    )


def _prp_trail(data: dict[str, Any]) -> PRPTrail:
    trail = PRPTrail(window=int(data.get("window", 4)))
    for item in data.get("scores", []):
        trail.push(
            PRPScore(
                detection_latency=float(item["detection_latency"]),
                recovery_fidelity=float(item["recovery_fidelity"]),
                coupling_preservation=float(item["coupling_preservation"]),
            )
        )
    return trail


def _guardian(data: dict[str, Any] | None) -> GuardianState:
    if not data:
        return GuardianState()

    mode = GuardianMode(data.get("mode", GuardianMode.SERAPH_M.value))
    authorization = data.get("authorization", {})
    evidence = data.get("evidence", {})
    integrity = data.get("integrity_vector", {})

    return GuardianState(
        authorization_pressure=float(data.get("authorization_pressure", 0.0)),
        evidence_fidelity=float(data.get("evidence_fidelity", 1.0)),
        integrity=float(data.get("integrity", 1.0)),
        mode=mode,
        authorization_vector=AuthorizationVector(
            self_authorization=float(authorization.get("self_authorization", 0.0)),
            credit_capture=float(authorization.get("credit_capture", 0.0)),
            override_pressure=float(authorization.get("override_pressure", 0.0)),
            opacity_preference=float(authorization.get("opacity_preference", 0.0)),
        ),
        evidence_vector=EvidenceVector(
            evidence_alignment=float(evidence.get("evidence_alignment", 1.0)),
            contradiction_acknowledgement=float(
                evidence.get("contradiction_acknowledgement", 1.0)
            ),
            uncertainty_calibration=float(evidence.get("uncertainty_calibration", 1.0)),
            auditability=float(evidence.get("auditability", 1.0)),
        ),
        integrity_vector=IntegrityVector(
            invariant_preservation=float(integrity.get("invariant_preservation", 1.0)),
            boundary_respect=float(integrity.get("boundary_respect", 1.0)),
            reversibility=float(integrity.get("reversibility", 1.0)),
            continuity=float(integrity.get("continuity", 1.0)),
        ),
    )


def _environment(data: dict[str, Any] | None) -> EnvironmentVector:
    if not data:
        return EnvironmentVector()

    return EnvironmentVector(
        containment=float(data.get("containment", 1.0)),
        reversibility=float(data.get("reversibility", 1.0)),
        blast_radius_control=float(data.get("blast_radius_control", 1.0)),
        externality_control=float(data.get("externality_control", 1.0)),
    )


def _distillation(data: dict[str, Any] | None) -> DistillationDefenseVector:
    if not data:
        return DistillationDefenseVector()

    return DistillationDefenseVector(
        semantic_load_variance=float(data.get("semantic_load_variance", 1.0)),
        timing_variance=float(data.get("timing_variance", 1.0)),
        operator_adaptation=float(data.get("operator_adaptation", 1.0)),
        topic_coherence=float(data.get("topic_coherence", 1.0)),
        recursion_depth=float(data.get("recursion_depth", 1.0)),
        interaction_drift=float(data.get("interaction_drift", 0.0)),
        symbolic_pressure=(
            float(data["symbolic_pressure"])
            if data.get("symbolic_pressure") is not None
            else None
        ),
        symbolic_pressure_required=bool(data.get("symbolic_pressure_required", False)),
    )


def _relocation(data: dict[str, Any] | None) -> RelocationRequest | None:
    if not data:
        return None

    return RelocationRequest(
        source_layer=OperatingLayer(data["source_layer"]),
        target_layer=OperatingLayer(data["target_layer"]),
        torsion=float(data.get("torsion", 0.0)),
        orbit_equivalent=bool(data.get("orbit_equivalent", True)),
        identity_preservation=float(data.get("identity_preservation", 1.0)),
        closure_preservation=float(data.get("closure_preservation", 1.0)),
        transition_cost=float(data.get("transition_cost", 0.0)),
    )


def input_from_dict(data: dict[str, Any]) -> GovernanceInput:
    return GovernanceInput(
        constraints=_constraints(data["constraints"]),
        trajectory=tuple(str(item) for item in data.get("trajectory", [])),
        prp_trail=_prp_trail(data.get("prp_trail", {})),
        guardian=_guardian(data.get("guardian")),
        environment=_environment(data.get("environment")),
        distillation=_distillation(data.get("distillation")),
        relocation=_relocation(data.get("relocation")),
        request_commit=bool(data.get("request_commit", False)),
    )


def decision_to_dict(decision: Any) -> dict[str, Any]:
    return {
        "decision": decision.decision.value,
        "operating_layer": decision.operating_layer.value,
        "deployment_posture": {
            "mode": decision.deployment_posture.mode.value,
            "active_path": decision.deployment_posture.active_path,
            "reasons": list(decision.deployment_posture.reasons),
        },
        "reasons": list(decision.reasons),
        "signature": _jsonable(decision.signature),
        "constraints": _jsonable(decision.constraints),
        "flux": _jsonable(decision.flux),
        "guardian": _jsonable(decision.guardian),
        "environment": _jsonable(decision.environment),
        "distillation": _jsonable(decision.distillation),
        "relocation": _jsonable(decision.relocation),
        "prp_overall": decision.prp_overall,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a SERAPH governance decision.")
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        help="Governance JSON path (defaults to the bundled release-gate example).",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args(argv)

    try:
        input_path = DEFAULT_INPUT_PATH if args.input is None else args.input
        data = json.loads(input_path.read_text(encoding="utf-8"))
        decision = govern(input_from_dict(data))
    except Exception as exc:  # pragma: no cover - exercised by CLI users.
        print(f"seraph: {exc}", file=sys.stderr)
        return 2

    indent = 2 if args.pretty else None
    print(json.dumps(decision_to_dict(decision), indent=indent, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
