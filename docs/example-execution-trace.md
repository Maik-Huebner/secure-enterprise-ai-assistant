# Verified dual-model execution traces

These traces were re-verified locally on 15 September 2026 with CrewAI 1.15.20, the real
NovaBank stdio MCP server, and both configured Ollama models.

## Qwen financial analysis

Request: `Berechne die finanzielle Belastung für CASE-00031.`

```text
request_received: Request received
intent_classified: financial_analysis
model_selected: qwen3.5:9b
model_profile: fast_local
model_reason: simple financial-analysis workflow
tools_selected: get_customer_case, analyze_financial_case
execution_mode: crewai
workflow_completed: Workflow completed
```

Native MCP discovery and both tool calls completed. Qwen returned the exact deterministic
metrics: monthly payment EUR 570.64, total interest EUR 5,488.40, total repayment EUR
34,238.40, DTI before 28.41%, and DTI after 44.95%. The evidence-boundary guardrail passed;
the final answer contained no unqueried compliance or RAG evidence section.

## Mistral full assessment

Request: `Prüfe CASE-00031 vollständig und erstelle eine Entscheidungsvorlage einschließlich
finanzieller Kennzahlen, Policy-Abgleich, Compliance-Risiken und Quellen.`

```text
request_received: Request received
intent_classified: full_assessment
model_selected: mistral-small3.2:24b
model_profile: complex_agentic
model_reason: full multi-agent assessment requires robust tool calling
tools_selected: get_customer_case, analyze_financial_case, check_compliance,
                search_internal_knowledge
fallback_reason: Task failed guardrail validation after 2 retries ...
                 Validation issues: DTI label and monthly payment are missing;
                 out-of-scope policy/compliance language was present.
execution_mode: deterministic_mcp_fallback
workflow_completed: Workflow completed
```

The native Mistral crew made real MCP calls, but the first financial task omitted required
financial fields and introduced policy/compliance language outside that agent's two-tool
evidence boundary after the configured guardrail retries. The task therefore failed before the
compliance and reviewer agents could complete. This was not a routing or MCP transport failure.

The existing fail-safe then opened a fresh stdio MCP session and called all four structured
tools. Its decision brief passed every completeness invariant:

- case: `CASE-00031`;
- monthly payment: EUR 570.64;
- post-loan DTI: 44.95%;
- failed rule: `RULE-005` with the structured NovaBank maximum of 40.0%;
- recommendation: manual review;
- policy IDs included `NB-CRD-001`, `NB-CRD-002`, `NB-GDE-001`, `NB-RSK-001`, and
  `NB-RSK-002`;
- terminal marker: `END OF VERIFIED REPORT`;
- no unsupported general 36–40% regulatory-threshold statement.

This is intentional fail-safe behavior. The trace records both the model originally selected
and the exact technical guardrail reason, then states `deterministic_mcp_fallback`; it never
presents deterministic output as a successful native model review.
