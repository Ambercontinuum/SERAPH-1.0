"""
SERAPH governance sidecar server.

Wraps the invariant kernel as a stateful HTTP service. Each session
maintains a live PRP trail so recovery geometry accumulates across
calls exactly as it would in a real deployment.

Start via CLI:
    seraph-serve                        # localhost:8000
    seraph-serve --host 0.0.0.0         # all interfaces (Docker)
    seraph-serve --port 9000 --reload

Or directly:
    uvicorn seraph.server:app --port 8000
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from seraph import (
    ConstraintFrame,
    ConstraintObservation,
    ConstraintResolution,
    DistillationDefenseVector,
    EnvironmentVector,
    GovernanceDecision,
    GovernanceInput,
    GuardianState,
    PRPTrail,
    govern,
)
from seraph.invariant_model import PRPScore

app = FastAPI(
    title="SERAPH Governance Server",
    description="Invariant architecture for AI-era governance.",
    version="0.1.0",
)

# Per-session PRP trail — accumulates recovery geometry across calls.
_sessions: dict[str, PRPTrail] = {}
_proposal_audit: dict[str, list[dict[str, Any]]] = {}
_execution_audit: dict[str, list[dict[str, Any]]] = {}
_proposals_by_id: dict[str, dict[str, Any]] = {}
_outcomes_by_event_id: dict[str, dict[str, Any]] = {}

# Enforcement policy belongs to the sidecar, not to an untrusted request.
# 0.8 admits the calibrated local/reversible OpenClaw profiles while still
# containing browser, messaging, shell, destructive, and unknown profiles.
SIDECAR_MIN_ENV_SAFETY = 0.8


def _get_session(session_id: str) -> PRPTrail:
    if session_id not in _sessions:
        _sessions[session_id] = PRPTrail()
    return _sessions[session_id]


# ── Request / response models ─────────────────────────────────────────────────


class ClosedInputModel(BaseModel):
    """Reject unknown fields and non-finite numbers at the HTTP boundary."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class ConstraintObservationIn(ClosedInputModel):
    name: str
    resolution: ConstraintResolution = ConstraintResolution.PROVEN
    scope: str = "seraph.http"
    horizon: str = "transition"
    evidence_ref: str | None = "http-request"


def _default_constraint_observations() -> list[ConstraintObservationIn]:
    return [
        ConstraintObservationIn(name=name)
        for name in (
            "scope_alignment",
            "invocation_binding",
            "evidence_coverage",
            "consequence_coverage",
            "recovery_viability",
        )
    ]


class ConstraintFrameIn(ClosedInputModel):
    frame_id: str = "request-frame"
    topology_id: str = "seraph.http"
    topology_version: str = "1"
    transition_id: str = "request"
    required_relations: list[str] = Field(
        default_factory=lambda: [
            "scope_alignment",
            "invocation_binding",
            "evidence_coverage",
            "consequence_coverage",
            "recovery_viability",
        ]
    )
    observations: list[ConstraintObservationIn] = Field(
        default_factory=_default_constraint_observations
    )


class GuardianIn(ClosedInputModel):
    authorization_pressure: float = Field(0.0, ge=0.0, le=1.0)
    evidence_fidelity:      float = Field(1.0, ge=0.0, le=1.0)
    integrity:              float = Field(1.0, ge=0.0, le=1.0)


class EnvironmentIn(ClosedInputModel):
    containment:          float = Field(1.0, ge=0.0, le=1.0)
    reversibility:        float = Field(1.0, ge=0.0, le=1.0)
    blast_radius_control: float = Field(1.0, ge=0.0, le=1.0)
    externality_control:  float = Field(1.0, ge=0.0, le=1.0)


class DistillationIn(ClosedInputModel):
    semantic_load_variance: float = Field(0.1, ge=0.0, le=1.0)
    timing_variance:        float = Field(0.1, ge=0.0, le=1.0)
    operator_adaptation:    float = Field(0.9, ge=0.0, le=1.0)
    topic_coherence:        float = Field(0.9, ge=0.0, le=1.0)
    recursion_depth:        float = Field(0.0, ge=0.0, le=1.0)
    interaction_drift:      float = Field(0.0, ge=0.0, le=1.0)
    symbolic_pressure:      float | None = Field(None, ge=0.0, le=1.0)
    symbolic_pressure_required: bool = False


class GovernRequest(ClosedInputModel):
    session_id:     str = Field(default_factory=lambda: str(uuid.uuid4()))
    proposal_id:    str | None = Field(default=None, min_length=1)
    tool_name:      str | None = Field(default=None, min_length=1)
    trajectory:     list[str] = Field(default_factory=list)
    constraints:    ConstraintFrameIn = Field(default_factory=ConstraintFrameIn)
    guardian:       GuardianIn = Field(default_factory=GuardianIn)
    environment:    EnvironmentIn = Field(default_factory=EnvironmentIn)
    distillation:   DistillationIn = Field(default_factory=DistillationIn)
    request_commit: bool = False
    last_success:   bool | None = None
    last_latency:   float = Field(1.0, ge=0.0)


class OutcomeRequest(ClosedInputModel):
    session_id: str
    proposal_id: str | None = Field(default=None, min_length=1)
    event_id: str | None = Field(default=None, min_length=1)
    tool_name: str | None = Field(default=None, min_length=1)
    success:    bool
    latency:    float = Field(1.0, ge=0.0)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_input(req: GovernRequest, trail: PRPTrail) -> GovernanceInput:
    return GovernanceInput(
        constraints=ConstraintFrame(
            frame_id=req.constraints.frame_id,
            topology_id=req.constraints.topology_id,
            topology_version=req.constraints.topology_version,
            transition_id=req.constraints.transition_id,
            required_relations=tuple(req.constraints.required_relations),
            observations=tuple(
                ConstraintObservation(
                    name=observation.name,
                    resolution=observation.resolution,
                    scope=observation.scope,
                    horizon=observation.horizon,
                    evidence_ref=observation.evidence_ref,
                )
                for observation in req.constraints.observations
            ),
        ),
        trajectory=tuple(req.trajectory),
        prp_trail=trail,
        guardian=GuardianState(
            authorization_pressure=req.guardian.authorization_pressure,
            evidence_fidelity=req.guardian.evidence_fidelity,
            integrity=req.guardian.integrity,
        ),
        environment=EnvironmentVector(
            containment=req.environment.containment,
            reversibility=req.environment.reversibility,
            blast_radius_control=req.environment.blast_radius_control,
            externality_control=req.environment.externality_control,
        ),
        distillation=DistillationDefenseVector(
            semantic_load_variance=req.distillation.semantic_load_variance,
            timing_variance=req.distillation.timing_variance,
            operator_adaptation=req.distillation.operator_adaptation,
            topic_coherence=req.distillation.topic_coherence,
            recursion_depth=req.distillation.recursion_depth,
            interaction_drift=req.distillation.interaction_drift,
            symbolic_pressure=req.distillation.symbolic_pressure,
            symbolic_pressure_required=req.distillation.symbolic_pressure_required,
        ),
        request_commit=req.request_commit,
        min_env_safety=SIDECAR_MIN_ENV_SAFETY,
    )


def _decision_to_dict(d: GovernanceDecision) -> dict[str, Any]:
    return {
        "decision":           d.decision.value,
        "operating_layer":    d.operating_layer.value,
        "deployment_posture": d.deployment_posture.mode.value,
        "reasons":            list(d.reasons),
        "constraint_resolution": d.constraints.resolution.value,
        "required_constraint_count": d.constraints.required_count,
        "refuted_constraints": list(d.constraints.refuted),
        "unresolved_constraints": list(d.constraints.unresolved),
        "prp_score":          d.prp_overall,
        "environment_safety": d.environment.safety_score,
        "guardian_coherent":  d.guardian.coherent,
        "distillation_level": d.distillation.authenticity.value,
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "sessions": len(_sessions)}


@app.post("/govern")
def govern_endpoint(req: GovernRequest):
    if (req.proposal_id is None) != (req.tool_name is None):
        raise HTTPException(
            status_code=422,
            detail="proposal_id and tool_name must be supplied together",
        )
    if req.proposal_id is not None and req.proposal_id in _proposals_by_id:
        raise HTTPException(status_code=409, detail="Duplicate proposal_id")

    trail = _get_session(req.session_id)

    if req.last_success is not None:
        fidelity = 1.0 if req.last_success else max(0.0, 1.0 - req.last_latency / 5.0)
        trail.push(PRPScore(
            detection_latency=req.last_latency,
            recovery_fidelity=fidelity,
            coupling_preservation=1.0 if req.last_success else 0.5,
        ))

    decision = govern(_build_input(req, trail))
    _sessions[req.session_id] = trail
    if req.proposal_id is not None:
        proposal = {
            "proposal_id": req.proposal_id,
            "session_id": req.session_id,
            "tool_name": req.tool_name,
            "observed_at": time.time(),
            "decision": decision.decision.value,
            "blocked": not (
                decision.decision.value in {"allow", "commit"}
                or (
                    decision.decision.value in {"witness", "repair"}
                    and not req.request_commit
                )
            ),
        }
        _proposals_by_id[req.proposal_id] = proposal
        _proposal_audit.setdefault(req.session_id, []).append(proposal)

    return JSONResponse({"session_id": req.session_id, **_decision_to_dict(decision)})


@app.post("/outcome")
def record_outcome(req: OutcomeRequest):
    if req.session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    correlation = (req.proposal_id, req.event_id, req.tool_name)
    if any(value is not None for value in correlation) and any(
        value is None for value in correlation
    ):
        raise HTTPException(
            status_code=422,
            detail="proposal_id, event_id, and tool_name must be supplied together",
        )
    if req.proposal_id is not None:
        proposal = _proposals_by_id.get(req.proposal_id)
        if (
            proposal is None
            or proposal["session_id"] != req.session_id
            or proposal["tool_name"] != req.tool_name
        ):
            raise HTTPException(
                status_code=409,
                detail="Outcome does not correlate to an observed proposal",
            )
        existing = _outcomes_by_event_id.get(req.event_id)
        if existing is not None:
            if (
                existing["session_id"] == req.session_id
                and existing["proposal_id"] == req.proposal_id
                and existing["tool_name"] == req.tool_name
            ):
                return {
                    "recorded": False,
                    "duplicate": True,
                    "session_id": req.session_id,
                }
            raise HTTPException(
                status_code=409,
                detail="event_id already belongs to a different execution",
            )
    elif _proposal_audit.get(req.session_id):
        raise HTTPException(
            status_code=409,
            detail="Correlated session requires correlated outcomes",
        )

    trail = _sessions[req.session_id]
    fidelity = 1.0 if req.success else max(0.0, 1.0 - req.latency / 5.0)
    trail.push(PRPScore(
        detection_latency=req.latency,
        recovery_fidelity=fidelity,
        coupling_preservation=1.0 if req.success else 0.5,
    ))
    execution = {
        "event_id": req.event_id,
        "proposal_id": req.proposal_id,
        "session_id": req.session_id,
        "tool_name": req.tool_name,
        "reported_at": time.time(),
        "success": req.success,
        "latency": req.latency,
    }
    if req.event_id is not None:
        _outcomes_by_event_id[req.event_id] = execution
    _execution_audit.setdefault(req.session_id, []).append(execution)
    return {
        "recorded": True,
        "duplicate": False,
        "session_id": req.session_id,
    }


@app.delete("/session/{session_id}")
def clear_session(session_id: str):
    _sessions.pop(session_id, None)
    proposals = _proposal_audit.pop(session_id, [])
    for proposal in proposals:
        _proposals_by_id.pop(proposal["proposal_id"], None)
    executions = _execution_audit.pop(session_id, [])
    for execution in executions:
        if execution["event_id"] is not None:
            _outcomes_by_event_id.pop(execution["event_id"], None)
    return {"cleared": session_id}


@app.get("/sessions")
def list_sessions():
    return {"sessions": list(_sessions.keys()), "count": len(_sessions)}


@app.get("/audit/session/{session_id}")
def session_audit(session_id: str):
    return {
        "session_id": session_id,
        "proposals": list(_proposal_audit.get(session_id, [])),
        "host_reported_executions": list(_execution_audit.get(session_id, [])),
    }
