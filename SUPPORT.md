# Support Policy

Thank you for building with **VoxLab**.

## Getting Help

### 1. Documentation
Before asking for help, please consult the official documentation:
- [Architecture & System Design](docs/architecture.md)
- [Darwin Evolutionary Fuzzing Engine](docs/darwin-engine.md)
- [API Reference](docs/api-reference.md)
- [Evaluation Methodology](docs/evaluation-methodology.md)

### 2. GitHub Issues
- **Bug Reports:** If you find a defect or reproducible failure in the engine, UI, or evaluation pipeline, please submit a bug report via [GitHub Issues](https://github.com/SUBHA22-CODER/voxlab/issues) using the Bug Report template.
- **Feature Proposals:** If you want to propose a new adversarial persona, mutation operator, or voice provider adapter, open a Feature Request issue.

### 3. Community Discussions
For general questions, troubleshooting agent connectivity, or sharing custom Darwin persona genomes, join the [GitHub Discussions](https://github.com/SUBHA22-CODER/voxlab/discussions).

---

## Known Common Issues

| Issue | Resolution |
| :--- | :--- |
| **Agent connection refused** | Ensure demo agent processes are started on ports 8100/8200 (`python -m uvicorn main:app --port 8100`). |
| **Darwin shows 100% flat fitness** | Agent endpoint is offline or returning 500 errors. Verify agent health before launching campaign. |
| **Database is locked** | Avoid concurrent write operations or running external blocking calls inside SQLite transactions. |

