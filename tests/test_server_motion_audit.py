from fastapi.testclient import TestClient

from seraph.server import app


client = TestClient(app)


def _govern(session_id: str, proposal_id: str, tool_name: str = "read_file"):
    return client.post(
        "/govern",
        json={
            "session_id": session_id,
            "proposal_id": proposal_id,
            "tool_name": tool_name,
            "trajectory": ["observe", "observe"],
        },
    )


def test_proposal_and_execution_are_correlated_but_separate():
    session_id = "motion-audit-separated"
    client.delete(f"/session/{session_id}")

    response = _govern(session_id, "proposal-1")
    assert response.status_code == 200

    audit = client.get(f"/audit/session/{session_id}").json()
    assert [item["proposal_id"] for item in audit["proposals"]] == ["proposal-1"]
    assert audit["host_reported_executions"] == []

    response = client.post(
        "/outcome",
        json={
            "session_id": session_id,
            "proposal_id": "proposal-1",
            "event_id": "execution-proposal-1",
            "tool_name": "read_file",
            "success": True,
            "latency": 0.25,
        },
    )
    assert response.status_code == 200
    assert response.json()["recorded"] is True

    audit = client.get(f"/audit/session/{session_id}").json()
    assert len(audit["proposals"]) == 1
    assert len(audit["host_reported_executions"]) == 1
    assert audit["host_reported_executions"][0]["proposal_id"] == "proposal-1"


def test_duplicate_execution_event_is_idempotent():
    session_id = "motion-audit-duplicate"
    client.delete(f"/session/{session_id}")
    assert _govern(session_id, "duplicate-proposal-1").status_code == 200

    outcome = {
        "session_id": session_id,
        "proposal_id": "duplicate-proposal-1",
        "event_id": "execution-duplicate-proposal-1",
        "tool_name": "read_file",
        "success": False,
        "latency": 2.0,
    }
    assert client.post("/outcome", json=outcome).json()["recorded"] is True
    duplicate = client.post("/outcome", json=outcome)
    assert duplicate.status_code == 200
    assert duplicate.json()["duplicate"] is True

    audit = client.get(f"/audit/session/{session_id}").json()
    assert len(audit["host_reported_executions"]) == 1


def test_unmatched_correlated_outcome_is_rejected():
    session_id = "motion-audit-unmatched"
    client.delete(f"/session/{session_id}")
    assert _govern(session_id, "unmatched-proposal-1").status_code == 200

    response = client.post(
        "/outcome",
        json={
            "session_id": session_id,
            "proposal_id": "unknown-proposal",
            "event_id": "unknown-execution",
            "tool_name": "read_file",
            "success": True,
            "latency": 0.1,
        },
    )
    assert response.status_code == 409
    assert client.get(f"/audit/session/{session_id}").json()[
        "host_reported_executions"
    ] == []


def test_legacy_outcome_contract_remains_supported():
    session_id = "motion-audit-legacy"
    client.delete(f"/session/{session_id}")
    assert client.post("/govern", json={"session_id": session_id}).status_code == 200

    response = client.post(
        "/outcome",
        json={"session_id": session_id, "success": True, "latency": 0.1},
    )
    assert response.status_code == 200
    assert response.json()["recorded"] is True


def test_correlated_session_cannot_silently_downgrade_to_legacy_outcome():
    session_id = "motion-audit-no-downgrade"
    client.delete(f"/session/{session_id}")
    assert _govern(session_id, "no-downgrade-proposal-1").status_code == 200

    response = client.post(
        "/outcome",
        json={"session_id": session_id, "success": True, "latency": 0.1},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Correlated session requires correlated outcomes"
    )
