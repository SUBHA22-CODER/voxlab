# VoxLab Security & Vulnerability Audit

**Scope:** Authentication, Authorization, Multi-Tenancy, SSRF, Injection, Secrets, and Rate Limiting.  
**Auditor:** Security Engineer & Site Reliability Engineer  
**Audit Status:** **PASS (Zero Critical / High Vulnerabilities)**

---

## 1. Vulnerability Findings & Verification Matrix

| Category | Test Probe | Result | Remediation / Defense In Depth |
| :--- | :--- | :---: | :--- |
| **Authentication Bypass** | Unauthenticated requests to `/api/agents`, `/api/test-runs`, `/api/darwin` | **PASS (401)** | JWT Bearer authentication enforced across all protected routes. |
| **Multi-Tenant Isolation** | User B querying User A's agents, runs, sessions, traces, or reports | **PASS (404/403)** | Database queries filter strictly on `user_id == current_user.id`. Ownership checked before returning detail. |
| **SSRF (Server-Side Request Forgery)** | Registering `ftp://`, `file:///`, or cloud metadata `169.254.169.254` | **PASS (400)** | `validate_endpoint` enforces allowed schemes (`http`, `https`, `ws`, `wss`) and blocks loopback/private/metadata ranges in production mode. |
| **SQL Injection** | SQL syntax payload injection (`1' OR '1'='1`) in queries | **PASS** | Strict SQLAlchemy 2.0 ORM parameter binding with zero raw string SQL interpolation. |
| **Stored XSS** | Registering agent with `<script>alert('XSS')</script>` in name/description | **PASS** | HTML content escaped on input and safely escaped by React JSX DOM rendering. |
| **Secret Storage & Leakage** | Storing agent bearer tokens and API keys | **PASS** | Encrypted at rest via Fernet symmetric cryptography (`auth_config_encrypted`). Omitted from all serialization schemas (`AgentOut`). |
| **Brute Force & DoS** | High-frequency credential stuffing against `/api/auth/login` | **PASS (429)** | In-memory sliding-window rate limiter limits clients to 15 auth requests/minute. |
| **Runaway Evolution Compute** | Darwin runs requesting 500+ sessions | **PASS** | Hard budget cap clamped at 60 sessions (`DARWIN_MAX_SESSIONS`), enforced at API submission and loop dispatch. |

---

## 2. Darwin Engine Specific Security Guardrails
1. **Target Authorization:** Darwin runs can only be launched against agents owned by the authenticated caller.
2. **Safe Genome Compilation:** Generated attack genomes compile to standard scenario JSON data structures. Genomes never execute shell commands or access filesystem paths.
3. **Sandbox Patching Safety:** The Patcher generates candidate configuration diffs and validates them in an in-memory sandbox. It never automatically modifies production agent definitions without explicit user review.

