# Verified dual-model execution traces

The Qwen trace was verified locally on 15 September 2026. The demo-safe full-assessment trace
was re-verified on 17 September 2026 with the real NovaBank stdio MCP server.

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

## Demo-safe full assessment

Request: `Prüfe CASE-00031 vollständig und erstelle eine Entscheidungsvorlage einschließlich
finanzieller Kennzahlen, Policy-Abgleich, Compliance-Risiken und Quellen.`

```text
request_received: Request received
intent_classified: full_assessment
configured_complex_model: mistral-small3.2:24b
model_profile: complex_agentic
model_reason: full multi-agent assessment requires robust tool calling
full_assessment_mode: verified_mcp
tools_selected: get_customer_case, analyze_financial_case, check_compliance,
                search_internal_knowledge
fallback_reason: Demo-Safe-Modus – verifizierter MCP-Pfad für reproduzierbare lokale Ausführung
execution_mode: deterministic_mcp_fallback
workflow_completed: Workflow completed
```

With the demo default `FULL_ASSESSMENT_MODE=verified_mcp`, the configured Mistral model was not
started. The UI request completed in 1.034 seconds end to end. The verified builder opened one
fresh stdio MCP session and called all four structured tools. Its German decision brief passed
every completeness invariant:

- case: `CASE-00031`;
- monthly payment: EUR 570.64;
- post-loan DTI: 44.95%;
- failed rule: `RULE-005` with the structured NovaBank maximum of 40.0%;
- recommendation: manual review;
- policy IDs included `NB-CRD-001`, `NB-CRD-002`, `NB-GDE-001`, `NB-RSK-001`, and
  `NB-RSK-002`;
- terminal marker: `END OF VERIFIED REPORT`;
- no unsupported general 36–40% regulatory-threshold statement.

This is intentional demo-safe behavior. The trace records Mistral only as the configured model,
states why the verified path was chosen, and reports `deterministic_mcp_fallback`; it never
presents deterministic output as a successful native model review. The former native path
remains available with `FULL_ASSESSMENT_MODE=agentic` for experimental testing and retains the
same verified MCP fail-safe after terminal or completeness failure.
