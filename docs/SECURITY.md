# Security Policy & Safeguards

> **Assumptions:**
> - Zero trust networking: Agent endpoints must be strictly validated.
> - Secrets are never logged or stored in plain text.

---

## 1. Credential Encryption at Rest
- **Mechanism:** Symmetric encryption using `cryptography.fernet.Fernet`.
- **Implementation (`app/core/security.py`):**
  - Any agent authentication headers or API keys provided by users are encrypted before saving to `agents.auth_config_encrypted`.
  - When communicating with target agents, credentials are decrypted in-memory and injected into request headers.
  - The database NEVER stores plain-text API secrets.

---

## 2. Server-Side Request Forgery (SSRF) Prevention
- Registered agent URLs pass through `app/services/endpoint_guard.py`.
- In production (`ALLOW_LOCAL_ENDPOINTS=false`):
  - DNS resolution is performed on the endpoint domain.
  - If the resolved IP belongs to `127.0.0.0/8`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `169.254.0.0/16`, or IPv6 loopback `::1`, the request is immediately rejected with HTTP 400.

---

## 3. Authentication & JWT Security
- Passwords are encrypted using salted `bcrypt`.
- Authentication relies on short-lived JWT Bearer tokens signed with `HS256` using the application `SECRET_KEY`.
- Rate limiting middleware restricts login and registration attempts to prevent brute-force attacks.
