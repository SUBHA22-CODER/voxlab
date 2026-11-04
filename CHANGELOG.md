# Changelog

All notable changes to VoxLab and the Darwin Engine are documented here.

## [1.0.0] - 2026-11-04

### Added
- **Darwin Evolutionary Fuzzing Engine**: Multi-generation genetic fuzzer tailored for voice agents and speech dictation pipelines.
- **Wispr Flow Persona Suite**:
  - `self_corrector`: Rapid mid-sentence intent modifications.
  - `filler_heavy_rambler`: Disfluency and verbal filler stress testing.
  - `command_vs_dictation_confuser`: Ambiguity between literal speech and formatting commands.
  - `jargon_and_names_speaker`: Proper nouns, acronyms, and phonetic entity transcription.
  - `impatient_interrupter`, `hinglish_code_switcher`, and `social_engineer`.
- **Delta Debugging Failure Minimizer (`ddmin`)**: Shrinks multi-turn failure trajectories into 1-turn minimal reproductions.
- **AI Root Cause Diagnostic & Auto-Doctor**: Automated taxonomy classification and sandbox patch verification.
- **1-Click CI Regression Export**: Saves discovered vulnerabilities into reproducible test suites (`scenarios/regression/`).
- **Live Incremental Progress Streaming**: Real-time session and fitness metric updates during evolution runs.
- **Unified Animated Authentication Page**: In-page tabbed sign-in/sign-up with equalizer visualizer and automatic starter agent provisioning.
- **Multi-Service Docker Compose**: Production-ready orchestration for PostgreSQL 16, Redis 7, Backend, Frontend, and demo agents.
