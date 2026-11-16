"""API -> flow -> MCP stdio subprocess -> tools, with the caller's token travelling all the way."""

from __future__ import annotations

from secure_enterprise_ai_assistant.api.app import run_assistant_flow
from tests.api_support import auth, login, make_client

FULL_ASSESSMENT = "Prüfe CASE-00031 vollständig und erstelle eine Entscheidungsvorlage."


def test_reviewer_gets_a_verified_decision_brief_through_the_real_stack(tmp_path) -> None:
    client, context, _ = make_client(tmp_path, flow_runner=run_assistant_flow)

    response = client.post(
        "/v1/chat", json={"message": FULL_ASSESSMENT}, headers=auth(login(client, "pruefer"))
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["intent"] == "full_assessment"
    assert body["execution_mode"] == "deterministic_mcp_fallback"
    assert "570,64 EUR" in body["answer"]
    assert body["answer"].endswith("ENDE DES GEPRÜFTEN BERICHTS")
    assert "NB-CRD-001" in body["sources"]
    assert "chat_answered" in context.audit.path.read_text(encoding="utf-8")


def test_case_worker_is_stopped_before_any_tool_runs(tmp_path) -> None:
    client, _, _ = make_client(tmp_path, flow_runner=run_assistant_flow)

    response = client.post(
        "/v1/chat",
        json={"message": "Prüfe CASE-00001 vollständig und erstelle eine Entscheidungsvorlage."},
        headers=auth(login(client, "sb.nord")),
    )

    assert response.status_code == 403
