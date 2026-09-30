"""Tests for CrewAI agent least-privilege configuration."""

from secure_enterprise_ai_assistant.agents.factory import (
    DEMO_SAFE_FALLBACK_REASON,
    AgentFactory,
    CrewOrchestrator,
    TaskOutput,
    language_guardrail,
    sanitize_model_output,
    validate_compliance_output,
    validate_decision_brief,
    validate_financial_output,
)
from secure_enterprise_ai_assistant.agents.model_router import ModelRouter
from secure_enterprise_ai_assistant.core.settings import Settings
from secure_enterprise_ai_assistant.flows.router import IntentRouter


def test_agents_disable_delegation_and_code_execution() -> None:
    settings = Settings(
        ollama_fast_model="test-model",
        ollama_base_url="http://127.0.0.1:11434",
    )
    factory = AgentFactory(settings)
    route = IntentRouter().classify("Zeige CASE-00001.")
    llm = factory.create_llm(ModelRouter(settings).select(route))

    tool_agents = (
        factory.case_agent(llm),
        factory.knowledge_agent(llm),
        factory.financial_agent(llm),
        factory.compliance_agent(llm),
    )
    for agent in tool_agents:
        assert agent.allow_delegation is False
        assert agent.__dict__["allow_code_execution"] is False
        assert len(agent.mcps or []) == 1
    assert factory.reviewer_agent(llm).mcps == []


def test_reviewer_guardrail_rejects_truncated_output() -> None:
    output = TaskOutput(
        description="review",
        expected_output="brief",
        raw="# Decision\n## 1.",
        agent="reviewer",
    )

    valid, feedback = validate_decision_brief(output)

    assert valid is False
    assert "1000 characters" in feedback


def test_reviewer_guardrail_accepts_substantive_sourced_output() -> None:
    body = " ".join(
        [
            "Decision recommendation for CASE-00031 references NB-CRD-001 and RULE-005.",
            "The monthly payment is EUR 570.64 and post-loan DTI is 44.95%.",
            "Evidence remains structured and reviewer-checked. " * 20,
            "END OF VERIFIED REPORT",
        ]
    )
    output = TaskOutput(description="review", expected_output="brief", raw=body, agent="reviewer")

    assert validate_decision_brief(output) == (True, body.strip())


def test_full_assessment_crew_builds_with_reviewer_guardrail(tmp_path) -> None:
    settings = Settings(
        ollama_fast_model="fast-test-model",
        ollama_complex_model="complex-test-model",
        ollama_base_url="http://127.0.0.1:11434",
        runtime_dir=tmp_path,
    )
    route = IntentRouter().classify(
        "Prüfe CASE-00031 vollständig und erstelle eine Entscheidungsvorlage."
    )

    crew = CrewOrchestrator(AgentFactory(settings)).build("demo", route)

    assert len(crew.tasks) == 3
    assert crew.tasks[-1].guardrail.__wrapped__ is validate_decision_brief
    assert all(agent.llm.model == "complex-test-model" for agent in crew.agents)
    assert all(agent.llm.provider == "ollama" for agent in crew.agents)
    assert len({id(agent.llm) for agent in crew.agents}) == 1
    assert all(
        "Never introduce a general financial or regulatory threshold" in task.description
        for task in crew.tasks
    )


def test_german_financial_task_enforces_german_user_facing_output(tmp_path) -> None:
    settings = Settings(
        ollama_fast_model="fast-test-model",
        ollama_base_url="http://127.0.0.1:11434",
        runtime_dir=tmp_path,
    )
    query = "Berechne die finanzielle Belastung für CASE-00031."
    route = IntentRouter().classify(query)

    crew = CrewOrchestrator(AgentFactory(settings)).build(query, route)
    task = crew.tasks[0]

    assert "Ausgabesprache für diese Anfrage: Deutsch" in task.description
    assert "Finanzielle Kennzahlen" in task.expected_output
    assert "Gesamtrückzahlung" in task.expected_output
    assert "Monthly Payment" not in task.expected_output
    assert all("For German requests" in agent.backstory for agent in crew.agents)
    assert all("For German requests" in agent.goal for agent in crew.agents)


def test_german_language_guardrail_rejects_english_response_labels() -> None:
    output = TaskOutput(
        description="analysis",
        expected_output="result",
        raw=(
            "# NovaBank Case Metrics\n"
            "CASE-00031\n"
            "Monthly Payment: EUR 570.64\n"
            "DTI vorher 28.41%, DTI danach 44.95%.\n"
            "Gesamtzins EUR 5,488.40; Gesamtrückzahlung EUR 34,238.40.\n"
            "Die Werte stammen aus dem MCP-Werkzeug analyze_financial_case. " * 5
        ),
        agent="analyst",
    )

    valid, feedback = language_guardrail(
        "Berechne die finanzielle Belastung für CASE-00031.",
        validate_financial_output,
    )(output)

    assert valid is False
    assert "NovaBank Case Metrics" in feedback
    assert "Monthly Payment" in feedback
    assert "vollständige Antwort auf Deutsch" in feedback


def test_intermediate_guardrails_reject_missing_evidence() -> None:
    output = TaskOutput(
        description="analysis",
        expected_output="result",
        raw="CASE-00031 looks fine.",
        agent="analyst",
    )

    assert validate_financial_output(output)[0] is False
    assert validate_compliance_output(output)[0] is False


def test_financial_guardrail_rejects_unqueried_evidence_categories() -> None:
    output = TaskOutput(
        description="analysis",
        expected_output="result",
        raw=(
            "CASE-00031 monthly payment EUR 570.64; DTI before 28.41%; DTI after 44.95%; "
            "total interest EUR 5,488.40; total repayment EUR 34,238.40. "
            "Deterministic metrics are repeated here without calculation. "
            * 3
            + "RAG Policy Evidence: no threshold was available."
        ),
        agent="analyst",
    )

    valid, feedback = validate_financial_output(output)

    assert valid is False
    assert "did not query" in feedback


def test_financial_guardrail_rejects_unsupported_domain_claims() -> None:
    metrics = (
        "CASE-00031 monthly payment EUR 570.64; DTI before 28.41%; DTI after 44.95%; "
        "total interest EUR 5,488.40; total repayment EUR 34,238.40. "
        "Deterministic MCP metrics are repeated without model calculation. " * 3
    )
    forbidden_claims = (
        "Therefore, compliance conclusions can be drawn from these metrics.",
        "Ein typischer regulatorischer DTI-Schwellenwert liegt bei 36–40 %.",
    )

    for claim in forbidden_claims:
        output = TaskOutput(
            description="analysis",
            expected_output="result",
            raw=metrics + claim,
            agent="analyst",
        )

        valid, feedback = validate_financial_output(output)

        assert valid is False
        assert "outside the financial agent's MCP evidence" in feedback


def test_model_output_sanitizes_host_paths_and_path_derived_mcp_aliases() -> None:
    local_path_fixture = "/" + "Users/example/Developer/private/tool.py"
    raw = (
        f"Called users_example_developer_secure_enterprise_1234abcd and read {local_path_fixture}."
    )

    sanitized = sanitize_model_output(raw)

    assert sanitized == "Called NovaBank_MCP_tool and read [local path redacted]"


def test_full_assessment_retains_transparent_mcp_fallback(monkeypatch) -> None:
    class FailingCrew:
        @staticmethod
        def kickoff() -> None:
            raise RuntimeError("Task failed guardrail validation after 2 retries")

    settings = Settings(
        ollama_fast_model="fast-test-model",
        ollama_complex_model="complex-test-model",
        full_assessment_mode="agentic",
    )
    orchestrator = CrewOrchestrator(AgentFactory(settings))
    route = IntentRouter().classify(
        "Prüfe CASE-00031 vollständig und erstelle eine Entscheidungsvorlage."
    )
    monkeypatch.setattr(orchestrator, "build", lambda *_args: FailingCrew())
    monkeypatch.setattr(
        "secure_enterprise_ai_assistant.agents.factory.VerifiedMCPReportBuilder.build",
        lambda _self, _query, _route: "verified MCP fallback",
    )

    result = orchestrator.run("demo", route)

    assert result == "verified MCP fallback"
    assert orchestrator.execution_mode == "deterministic_mcp_fallback"
    assert orchestrator.fallback_reason == "Task failed guardrail validation after 2 retries"


def test_default_full_assessment_uses_verified_mcp_without_llm(monkeypatch) -> None:
    settings = Settings(
        ollama_fast_model="fast-test-model",
        ollama_complex_model="complex-test-model",
    )
    factory = AgentFactory(settings)
    orchestrator = CrewOrchestrator(factory)
    route = IntentRouter().classify(
        "Prüfe CASE-00031 vollständig und erstelle eine Entscheidungsvorlage."
    )

    def fail_if_called(*_args) -> None:
        raise AssertionError("Demo-Safe mode must not construct a Crew or LLM")

    monkeypatch.setattr(orchestrator, "build", fail_if_called)
    monkeypatch.setattr(factory, "create_llm", fail_if_called)
    monkeypatch.setattr(
        "secure_enterprise_ai_assistant.agents.factory.VerifiedMCPReportBuilder.build",
        lambda _self, _query, _route: "verified MCP report",
    )

    result = orchestrator.run("demo", route)

    assert result == "verified MCP report"
    assert settings.full_assessment_mode == "verified_mcp"
    assert orchestrator.execution_mode == "deterministic_mcp_fallback"
    assert orchestrator.fallback_reason == DEMO_SAFE_FALLBACK_REASON


def test_agentic_full_assessment_mode_remains_configurable(monkeypatch) -> None:
    class SuccessfulCrew:
        @staticmethod
        def kickoff() -> str:
            return "native agentic output"

    settings = Settings(full_assessment_mode="agentic")
    orchestrator = CrewOrchestrator(AgentFactory(settings))
    route = IntentRouter().classify(
        "Prüfe CASE-00031 vollständig und erstelle eine Entscheidungsvorlage."
    )
    monkeypatch.setattr(orchestrator, "build", lambda *_args: SuccessfulCrew())
    monkeypatch.setattr(
        "secure_enterprise_ai_assistant.agents.factory.is_complete_decision_brief",
        lambda _output: True,
    )

    assert orchestrator.run("demo", route) == "native agentic output"
    assert orchestrator.execution_mode == "crewai"
    assert orchestrator.fallback_reason is None
