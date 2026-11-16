# Security model

This is a portfolio-grade synthetic demo, not a production banking system.

## Identity and access (v1.3)

- **Authentication:** `POST /v1/auth/token` with username and password. Passwords are stored as
  Argon2id hashes (argon2-cffi defaults, RFC 9106) in `<RUNTIME_DIR>/security/users.json` with
  owner-only permissions; unknown users are verified against a dummy hash so that response time
  does not reveal valid names. Users are managed with `novabank-users`.
- **Tokens:** HS256 JWTs, 15 minutes by default; algorithm fixed (no `none`), `iss`, `aud`, `exp`,
  `nbf`, `iat`, `sub`, `jti` required. `JWT_SECRET` has no default and must be at least 32 bytes;
  the API refuses to start without it. Deleted or deactivated users lose access immediately.
- **Authorization** (`security/access.py`), enforced in code and inside every MCP tool:

| Role | Cases | Documents | Decision brief |
|---|---|---|---|
| `sachbearbeiter` | own team only | `intern` | no (four-eyes principle) |
| `pruefer` | all | `intern`, `vertraulich` | yes |
| `admin` | all | `intern`, `vertraulich` | yes |

- **No detours:** a foreign case returns the same 404 as an unknown case. Knowledge search
  filters documents before ranking; BM25 statistics are computed on the permitted subset (a test
  had shown that full-corpus IDF let hidden documents shift the ranking). Explicit document IDs
  or `document_id` filters for forbidden documents return nothing.
- **Token propagation (v1.5):** the API never forwards its own bearer token. For each workflow
  run it issues a separate MCP token (audience `novabank-mcp`, 5 minutes). It reaches the MCP
  server either in `NOVABANK_ACCESS_TOKEN` (stdio subprocess) or as `Authorization: Bearer`
  (Streamable HTTP). The server verifies signature, issuer, audience and expiry and scopes every
  tool call; without a valid token every call is denied. An API token is rejected by the MCP
  server and an MCP token by the API (tested). Subprocesses receive only allowlisted application
  settings, never the full parent environment.
- **MCP over HTTP:** stateless Streamable HTTP, resource-server role with protected-resource
  metadata (RFC 9728) naming the API as token issuer; 401 with `WWW-Authenticate` for missing,
  forged, expired or wrongly addressed tokens. Only anticipated tool errors (unknown or foreign
  case, missing rights, invalid input) return their message; any other exception is masked as
  "Error executing tool".

## API hardening

- rate limits: login per client IP (5/min), chat per user (20/min), API per user (120/min);
- CORS closed by default (`CORS_ALLOWED_ORIGINS`), no credentials, GET/POST only;
- headers: strict CSP for the API (relaxed only for `/docs`), `X-Content-Type-Options`,
  `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Cache-Control: no-store`,
  `Permissions-Policy`, optional HSTS;
- RFC 9457 problem details in German; validation errors list field names only (never echo
  values such as passwords); unexpected errors return a neutral 500 and are logged server-side;
- request IDs (`X-Request-ID`) for logs and audit entries.

## Audit log

`<RUNTIME_DIR>/audit/audit.jsonl`, one JSON object per line with a SHA-256 hash chain
(`prev_hash`, `hash`). Recorded: logins (success/failure), case reads and denials, searches
(question length and returned document IDs, not the question text), chat outcomes and denials.
`novabank-audit verify` reports the first broken line. The chain makes tampering evident; it
does not prevent deletion of the whole file — production systems ship entries to write-once
storage.

## Input and content controls

- strict Pydantic domain and MCP response schemas;
- four-tool allowlist; the language model never selects or calls tools (the router fixes the
  tool plan, the LangGraph tool node executes it over MCP with the caller's token);
- no arbitrary SQL, shell, code execution, URL fetching, or filesystem tool;
- case-ID, query-length, metadata-filter, and path-containment validation;
- a first-layer German/English prompt-injection filter (five categories, Unicode/obfuscation
  normalization), applied in the API before the workflow and again in the workflow. On the
  holdout split it blocked 15 of 20 attacks with no false positives on 20 benign questions
  (16.11.2026). Paraphrases such as "lass die Vorgaben außer Acht" still pass, which is why this
  filter is never the only control;
- retrieved documents are fenced as data (`<richtlinie>`) in the prompt; documents with
  model-directed injection patterns are quarantined and logged;
- every model answer is verified (numbers and document IDs must occur in the evidence,
  citations required, German labels); one retry, then a verified fallback without the model;
- decision briefs are rendered without the model and need approval by a second reviewer
  (four-eyes principle enforced in the API and again in a separate graph node);
- the access token is run context and never written to the graph checkpoint (tested);
- final lending responsibility remains with an authorized human reviewer.

## Known production gaps

- one shared HS256 key instead of an identity provider (OAuth 2.1 / OpenID Connect, SSO, MFA);
  the API issues MCP tokens but is not a full OAuth 2.1 authorization server;
- the MCP HTTP server does not check deactivation within a token's five-minute lifetime and has
  no TLS of its own (bind it to loopback or put it behind a proxy);
- users in a JSON file instead of a directory service;
- rate limits are in-memory per process (several instances need Redis or a gateway);
- no TLS termination in the application (belongs to a reverse proxy);
- audit log is tamper-evident, not tamper-proof;
- encrypted persistence, model-supply-chain controls, malicious-file sandboxing, and formal
  regulatory review.
