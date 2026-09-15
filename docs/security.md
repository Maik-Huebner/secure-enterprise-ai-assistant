# Security model

This is a portfolio-grade synthetic demo, not a production banking system.

Implemented controls:

- strict Pydantic domain and MCP response schemas;
- four-tool allowlist with per-agent least-privilege MCP filters;
- no arbitrary SQL, shell, code execution, URL fetching, or filesystem tool;
- case-ID, query-length, metadata-filter, and path-containment validation;
- explicit prompt-override, prompt-exfiltration, and shell-request blocking;
- retrieved documents treated as untrusted evidence in every agent prompt;
- source metadata retained from ingestion through retrieval output and surfaced as document,
  version, and section citations;
- UI errors sanitized before display;
- CrewAI telemetry and tracing disabled by secure default;
- `.env` and runtime databases excluded from version control;
- all customers, cases, policies, and decision labels are synthetic;
- UI binds to loopback and Gradio sharing is disabled;
- Task and report guardrails reject missing evidence and unsupported source categories;
- failed complex model runs fall back through a fresh real MCP-stdio session rather than a
  direct Python-service bypass;
- final lending responsibility remains with an authorized human reviewer.

Prompt-injection handling is deliberately narrow and testable: user requests containing prompt
override, prompt-exfiltration, or shell-execution patterns are blocked before routing. Retrieved
document text is treated as untrusted evidence and cannot expand the four-tool allowlist or grant
shell, SQL, URL-fetching, or arbitrary filesystem capabilities.

Known production gaps include authentication, authorization, encrypted persistence, audit-log
shipping, model-supply-chain controls, malicious-file sandboxing, and formal regulatory review.
