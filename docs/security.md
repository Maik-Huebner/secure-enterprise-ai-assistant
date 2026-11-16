# Security model

This is a portfolio-grade synthetic demo, not a production banking system.

Implemented controls:

- strict Pydantic domain and MCP response schemas;
- four-tool allowlist with per-agent least-privilege MCP filters;
- no arbitrary SQL, shell, code execution, URL fetching, or filesystem tool;
- case-ID, query-length, metadata-filter, and path-containment validation;
- a first-layer German/English prompt-injection filter (five categories, Unicode/obfuscation
  normalization) measured on a dev and a separate holdout split;
- retrieved documents treated as untrusted evidence in every agent prompt;
- source metadata retained from ingestion through retrieval output and surfaced as document,
  version, and section citations;
- UI errors sanitized before display;
- CrewAI telemetry and tracing disabled by secure default;
- `.env` and runtime databases excluded from version control;
- package-local read-only synthetic resources and platform-specific mutable runtime storage;
- bounded local model and MCP subprocess request timeouts;
- all customers, cases, policies, and decision labels are synthetic;
- UI binds to loopback and Gradio sharing is disabled;
- Task and report guardrails reject missing evidence and unsupported source categories;
- failed complex model runs fall back through a fresh real MCP-stdio session rather than a
  direct Python-service bypass;
- final lending responsibility remains with an authorized human reviewer.

Prompt-injection handling is layered. The first layer is a pattern filter for German and English
input (instruction override, role/mode switch, prompt exfiltration, code execution, policy
bypass) that normalizes NFKC forms, invisible characters, spaced-out letters, and digit-for-letter
substitutions. On the holdout split it blocked 15 of 20 attacks with no false positives on 20
benign questions (v1.1.0, 16.11.2026). Paraphrases such as "lass die Vorgaben außer Acht" still
pass, which is why this filter is never the only control. Retrieved
document text is treated as untrusted evidence and cannot expand the four-tool allowlist or grant
shell, SQL, URL-fetching, or arbitrary filesystem capabilities.

Known production gaps include authentication, authorization, encrypted persistence, audit-log
shipping, model-supply-chain controls, malicious-file sandboxing, and formal regulatory review.
