# Demo scenarios

## 1 — Hybrid RAG

Prompt: `Welche Unterlagen benötigt NovaBank für einen Konsumentenkredit?`

Expected route: knowledge using `qwen3.5:9b` / `fast_local` and
`search_internal_knowledge`. Expected top source: `NB-DOC-001` v1.6, section 3.1.

## 2 — Structured customer data

Prompt: `Zeige CASE-00001.`

Expected route: customer case. This is the clearly positive synthetic case.

## 3 — Deterministic financial analysis

Prompt: `Berechne die Kreditbelastung für CASE-00001.`

Expected model: `qwen3.5:9b` / `fast_local`. Expected monthly payment: EUR 419.46.
No model arithmetic is accepted.

## 4 — Compliance problem

Prompt: `Welche Compliance-Probleme hat CASE-00017?`

Expected failed rule: `RULE-003`, missing income statement.

## 5 — Full agentic assessment

Prompt: `Prüfe CASE-00031 vollständig und erstelle eine Entscheidungsvorlage einschließlich
finanzieller Kennzahlen, Policy-Abgleich, Compliance-Risiken und Quellen.`

Expected route: full assessment using `mistral-small3.2:24b` / `complex_agentic` with
financial, compliance, knowledge, and reviewer stages. Expected warning: `RULE-005`, post-loan
DTI 44.95% above the structured 40% NovaBank review threshold; recommendation `MANUAL REVIEW`.
If the native crew fails its strict content guardrail, the transparent
`deterministic_mcp_fallback` must open a fresh MCP-stdio session and produce the verified report.

For an unequivocally problematic comparison, use `CASE-00007` (post-loan DTI above 50%) or
`CASE-00008` (rejected KYC and risk class E).
