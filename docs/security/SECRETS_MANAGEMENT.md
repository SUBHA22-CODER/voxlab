# Secrets & Credential Management Policy

## Principles
1. **Never commit actual secrets:** `.gitignore` excludes `.env`, `*.env`, `backend/.env`, and `frontend/.env.local`.
2. **Deterministic Fallbacks:** The platform functions fully in offline / local development mode without requiring paid API keys.
3. **Environment Injection:** Secrets must always be injected at runtime via process environment variables or container secrets.

## Secrets Lifecycle

```mermaid
sequenceDiagram
    participant Dev as Engineer / CI
    participant Env as Environment Variables
    participant Core as app/core/config.py
    participant Crypt as AES-GCM Encryptor
    participant DB as SQLite / PostgreSQL

    Dev->>Env: Set GROQ_API_KEY, JWT_SECRET, ENCRYPTION_KEY
    Env->>Core: Ingest on startup
    Dev->>Core: Register Agent with API credentials
    Core->>Crypt: Encrypt credential with ENCRYPTION_KEY
    Crypt->>DB: Store encrypted ciphertext only
```
