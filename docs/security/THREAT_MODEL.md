# VoxLab Threat Model

## Threat Landscape

| Threat | Attack Surface | Impact | Implemented Mitigation | Recommended Future Control |
| :--- | :--- | :--- | :--- | :--- |
| **Server-Side Request Forgery (SSRF)** | Agent endpoint registration (`POST /api/agents`) | Attacker registers internal cloud metadata IP (e.g. `169.254.169.254`). | Local development allows localhost; production requires VPC whitelist. | Implement IP blocklist validator forbidding AWS/GCP metadata ranges. |
| **Denial of Service via Darwin Fuzzing** | In-process background evolution runs | Attacker starts 1,000 generations, exhausting target agent or server CPU. | Hard session cap: $pop \times gen \le 60$. User JWT scoping. | Global per-tenant concurrent campaign rate limit (e.g. Redis semaphore). |
| **Transcript & PII Leakage** | Evaluation traces & transcript logs | Sensitive customer voice transcripts exposed to unauthorized users. | Scoped tenant isolation (`user_id` enforced on all ORM queries). | Automated PII masking before saving transcript records. |
| **Credential / API Key Exposure** | Voice provider tokens & LLM API keys | Leaked keys lead to unauthorized cloud API usage. | Encrypted via AES-GCM at rest; excluded from API output schemas. | Hardware Security Module (HSM) or HashiCorp Vault backend. |
| **Prompt Injection via Attack Personas** | Darwin persona utterances sent to target agent | Attacker crafts persona that exfiltrates system prompt. | Agent responses evaluated against forbidden output patterns. | System prompt boundary delimiters and guardrail filters. |
