# Security policy

## Scope

This repository is a portfolio reference system built with synthetic data. It demonstrates
security-oriented design controls, but it is not a certified security product or a production
banking system.

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability that could expose a secret or enable
abuse. Use GitHub's private vulnerability reporting for this repository when available. Include
the affected revision, reproduction steps, impact, and any suggested mitigation. Do not include
real customer, financial, identity, or authentication data in a report.

## Supported versions

Only the current default branch is considered for security fixes. Historical tags remain
immutable portfolio releases and may contain limitations documented at the time of release.

## Security boundaries

The supported offline path uses synthetic cases and policies, four allowlisted MCP tools, and no
external provider. Authentication, role-based authorization, encrypted persistence, malware
sandboxing, production audit-log shipping, and formal penetration testing are outside the current
scope. See [docs/security.md](docs/security.md) and [RESPONSIBLE_USE.md](RESPONSIBLE_USE.md).
