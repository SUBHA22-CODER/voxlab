# VoxLab Technical Documentation

Welcome to the VoxLab engineering documentation. VoxLab is an automated reliability, evolutionary fuzzing ("Darwin"), and crash-testing platform tailored for voice agents and speech-to-text dictation pipelines (such as Wispr Flow).

---

## Documentation Directory

### Architecture & System Design
- [Product Requirements Document (PRD)](PRD.md)
- [Vision & North Star](VISION.md)
- [System Architecture](architecture.md)
- [System Design & Component Lifecycle](SYSTEM_DESIGN.md)
- [Data Model & Database Schema](DATA_MODEL.md)
- [API Reference](api-reference.md)
- [Configuration & Environment Variables](CONFIGURATION.md)
- [Observability, Tracing & Metrics](OBSERVABILITY.md)
- [Evaluation Methodology](evaluation-methodology.md)

### Darwin Evolutionary Fuzzing Engine
- [Darwin Overview & Lifecycle](darwin/DARWIN_OVERVIEW.md)
- [Evolution Engine & Population Dynamics](darwin/EVOLUTION_ENGINE.md)
- [Genome Representation & Mutation Operators](darwin/GENOME_AND_MUTATION.md)
- [Fitness Evaluation & Voice Scoring](darwin/FITNESS_EVALUATION.md)
- [Delta Debugging (ddmin) Failure Minimization](darwin/FAILURE_MINIMIZATION.md)
- [AI Root-Cause Diagnosis](darwin/ROOT_CAUSE_DIAGNOSIS.md)
- [Automated Regression Suite Integration](darwin/REGRESSION_LIBRARY.md)

### Security & Safety
- [Threat Model & Attack Surface](security/THREAT_MODEL.md)
- [Security Controls & Defense in Depth](security/SECURITY_CONTROLS.md)
- [Secrets & Credential Management](security/SECRETS_MANAGEMENT.md)
- [Repository Security Audit](security/REPOSITORY_SECURITY_AUDIT.md)

### Testing & Quality Assurance
- [Testing Strategy & Philosophy](TESTING_STRATEGY.md)
- [Test Plan](testing/TEST_PLAN.md)
- [Test Coverage Report](testing/TEST_COVERAGE.md)
- [End-to-End Testing Guide](testing/E2E_TESTING.md)

### Architectural Decisions
- [Architecture Decision Record (ADR) Template](decisions/ADR_TEMPLATE.md)
