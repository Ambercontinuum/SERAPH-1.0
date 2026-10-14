"""Human-readable invariant traces for SERAPH decisions."""

from __future__ import annotations

from seraph import GovernanceDecision


def _ok(flag: bool) -> str:
    return "ok" if flag else "failed"


def decision_trace(name: str, decision: GovernanceDecision) -> list[str]:
    """Render a compact operator trace for a governance decision."""

    prp = "none" if decision.prp_overall is None else f"{decision.prp_overall:.3f}"
    lines = [
        f"SCENARIO: {name}",
        f"CONSTRAINTS: {decision.constraints.resolution.value} -> "
        f"{decision.constraints.reason} "
        f"(required={decision.constraints.required_count}, "
        f"refuted={len(decision.constraints.refuted)}, "
        f"unresolved={len(decision.constraints.unresolved)})",
        f"FLUX: {_ok(decision.flux.coherent)} -> {decision.flux.decision.value} "
        f"(switches={decision.flux.switches}, drift_run={decision.flux.drift_run}, "
        f"stability={decision.flux.stability})",
        f"PRP: overall={prp}, trend={decision.signature.recovery_trend:.3f}",
        f"SERAPH: {_ok(decision.guardian.coherent)} "
        f"(mode={decision.guardian.mode.value}, "
        f"authorization_pressure={decision.guardian.authorization_pressure:.3f}, "
        f"evidence_fidelity={decision.guardian.evidence_fidelity:.3f}, "
        f"integrity_score={decision.guardian.integrity_score:.3f})",
        f"Environment: {_ok(decision.environment.safe)} "
        f"(safety={decision.environment.safety_score:.3f})",
        f"Distillation: {_ok(decision.distillation.safe)} "
        f"(authenticity={decision.distillation.authenticity.value}, "
        f"lambda={decision.distillation.coupling_lambda:.3f}, "
        f"dimensionality={decision.distillation.dimensionality:.3f})",
        f"Relocation: {_ok(decision.relocation.admissible)} "
        f"(requested={str(decision.relocation.requested).lower()}, "
        f"torsion={decision.relocation.torsion})",
        f"Decision: {decision.decision.value}",
        f"Layer: {decision.operating_layer.value}",
        f"Posture: {decision.deployment_posture.active_path}",
        f"Reasons: {', '.join(decision.reasons)}",
    ]
    return lines


def render_trace(name: str, decision: GovernanceDecision, *, passed: bool) -> str:
    """Render a trace with a final scenario verdict."""

    lines = decision_trace(name, decision)
    lines.append("PASS" if passed else "FAIL")
    return "\n".join(lines)
