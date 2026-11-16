"""API -> LangGraph -> MCP stdio subprocess -> tools, with the caller's token all the way."""

from __future__ import annotations

from secure_enterprise_ai_assistant.mcp.client import McpEvidenceClient
from tests.api_support import auth, login, make_client

FULL_ASSESSMENT = "Prüfe CASE-00031 vollständig und erstelle eine Entscheidungsvorlage."


def test_decision_brief_needs_a_second_reviewer_through_the_real_stack(tmp_path) -> None:
    client, context, _ = make_client(tmp_path, collector=McpEvidenceClient)
    requester = auth(login(client, "pruefer"))

    draft = client.post("/v1/chat", json={"message": FULL_ASSESSMENT}, headers=requester)
    assert draft.status_code == 200, draft.text
    body = draft.json()
    assert body["status"] == "awaiting_approval"
    assert body["execution_mode"] == "verified_mcp"
    assert "570,64 EUR" in body["answer"]

    self_approval = client.post(
        f"/v1/reviews/{body['thread_id']}", json={"decision": "approve"}, headers=requester
    )
    assert self_approval.status_code == 403

    second = auth(login(client, "admin"))
    assert [item["thread_id"] for item in client.get("/v1/reviews", headers=second).json()] == [
        body["thread_id"]
    ]
    final = client.post(
        f"/v1/reviews/{body['thread_id']}",
        json={"decision": "approve", "comment": "Budgetprüfung dokumentiert."},
        headers=second,
    )
    assert final.status_code == 200, final.text
    assert final.json()["status"] == "approved"
    assert "Freigegeben** von admin" in final.json()["answer"]
    assert "Budgetprüfung dokumentiert." in final.json()["answer"]
    audit = context.audit.path.read_text(encoding="utf-8")
    assert "decision_brief_requested" in audit and "decision_brief_approved" in audit
    assert client.get("/v1/reviews", headers=second).json() == []


def test_case_worker_is_stopped_before_any_tool_runs(tmp_path) -> None:
    client, _, _ = make_client(tmp_path, collector=McpEvidenceClient)

    response = client.post(
        "/v1/chat",
        json={"message": "Prüfe CASE-00001 vollständig und erstelle eine Entscheidungsvorlage."},
        headers=auth(login(client, "sb.nord")),
    )

    assert response.status_code == 403


def test_knowledge_answer_through_mcp_with_a_grounded_model(tmp_path) -> None:
    client, _, _ = make_client(tmp_path, collector=McpEvidenceClient)

    response = client.post(
        "/v1/chat",
        json={"message": "Welche Unterlagen benötigt NovaBank für einen Konsumentenkredit?"},
        headers=auth(login(client, "sb.nord")),
    )

    assert response.status_code == 200, response.text
    assert response.json()["execution_mode"] == "llm_grounded"
    assert "NB-DOC-001" in response.json()["sources"]
