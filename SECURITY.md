# Security Policy

## Supported Versions

We release patches and security fixes for the latest stable minor version of VoxLab.

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| < 0.1   | :x:                |

---

## Reporting a Vulnerability

The VoxLab team takes software security seriously. If you discover a vulnerability or security defect, please do **NOT** open a public issue.

Instead, please report vulnerabilities by contacting the maintainers through a Private Vulnerability Report on GitHub:
1. Navigate to the VoxLab repository security tab: `https://github.com/SUBHA22-CODER/voxlab/security`
2. Click **"Report a vulnerability"** to open an advisory draft.
3. Include:
   - Type of vulnerability (e.g. SSRF, Auth Bypass, SQLi, Prompt Injection)
   - Detailed step-by-step reproduction instructions
   - Proof of concept payload or scenario file
   - Impact assessment on voice sessions or agent credentials

### Response Timeline
- **Initial acknowledgment:** Within 48 hours.
- **Triage & validation:** Within 5 business days.
- **Remediation release:** Published within 14 business days depending on severity.

---

## Security Practices & Boundaries

- **Secret Handling:** API keys and provider tokens are encrypted at rest using AES-GCM and never logged in plain text or emitted over WebSockets.
- **Target Boundaries:** Darwin evolutionary fuzzing operates strictly against user-configured HTTP/WebSocket voice endpoints within local or approved VPC networks. Darwin contains a hard session budget cap (60 sessions) to prevent denial of service.
- **Deterministic Fallbacks:** The platform maintains local deterministic heuristic evaluators that function without transmitting agent transcript data to third-party cloud LLMs unless explicitly configured.
