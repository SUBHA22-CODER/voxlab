# VoxLab Baseline Audit — Wispr Flow & Core Platform Protection

**Document Version:** 1.0.0  
**Baseline Date:** 2026-11-12  
**Baseline Commit SHA:** `9e054e3effd820e06f5bdbc21500bb6dfbe51a81`  
**Git Tag:** `wispr-flow-baseline`  
**Feature Branch:** `feature/gnani-integration`  
**Primary Architect:** Principal AI Infrastructure & Speech ML Engineer

---

## 1. Executive Summary

This document records the exact, verified state of **VoxLab** before initiating the **Gnani AI Integration & Indic Speech Lab** upgrade. Under strict preservation rules, no existing Wispr Flow workflows, Darwin evolutionary fuzzing mechanisms, speech engine adapters, or UI capabilities will be modified or removed.

---

## 2. Existing Wispr Flow Capabilities

VoxLab currently provides tailored dictation and voice agent reliability testing for Wispr Flow:

1. **Wispr Flow Cleaner Agent (`agent-examples/dictation-agent` on Port 8200):**
   - Cleans real-time spoken transcripts by resolving conversational disfluencies, self-corrections, fillers, and punctuation.
   - Evaluated continuously against acoustic and conversational stress scenarios.
2. **Human-in-the-Loop Capture (`/api/v1/audio/score`):**
   - Ingests text directly from Wispr Flow dictation sessions.
   - Computes deterministic Ground-Truth metrics: Word Error Rate (WER), Character Error Rate (CER), Number Accuracy (number-to-word canonical matching), Entity Accuracy, and Technical Vocabulary retention.
   - Word-level alignment labeling operations (`correct`, `substitution`, `insertion`, `deletion`) with severity categorization (`major` for content tokens vs `minor` for function words).
   - Deterministic semantic error detection: numbers, dates, negations, entities, instructions, and intent changes.
3. **Dedicated Dictation Test Scenarios (`scenarios/`):**
   - Self-correction handling (*"Schedule meeting for Tuesday, wait no, Wednesday at 4pm"*).
   - Filler word pruning (*"um, uh, like, actually"*).
   - Homophone disambiguation (*"two"* vs *"to"*, *"accept"* vs *"except"*).
   - Punctuation & casing compliance under conversational velocity.

---

## 3. Existing Provider & Speech Engine Architecture

The platform architecture (`backend/app/speech/`) is strictly modular and engine-agnostic:

* **Engine Registry (`backend/app/speech/registry.py`):**
  - Lazy discovery without hard crashes if dependencies are absent.
  - Truthful capability reporting: languages, timestamps, language detection, streaming modes.
* **Registered Speech Engines:**
  1. `whisper_local`: OpenAI Whisper (Encoder-Decoder Autoregressive Transformer via `whisper-local`, MIT).
  2. `vosk`: Kaldi HMM-DNN Hybrid WFST Decoder with offline acoustic models.
  3. `wav2vec2`: Meta Wav2Vec2-base-960h (Self-Supervised Acoustic Representation with CTC head, via Hugging Face).
* **Agent Adapters (`backend/app/adapters/`):**
  - `HTTPAdapter`: REST endpoints with turn-by-turn latency measurement.
  - `WebSocketAdapter`: Real-time streaming conversation over WebSockets.
  - Provider credential encryption via AES-GCM.

---

## 4. Existing Darwin Engine Functionality

VoxLab's flagship adversarial fuzzing engine (`backend/app/darwin/`):

1. **Adversarial Personas (Conversational & Dictation):**
   - `SelfCorrectorPersona`
   - `HomophoneConfuserPersona`
   - `FillerRamblerPersona`
   - `BargeInInterrupterPersona`
   - `ContextSwitcherPersona`
2. **Audio Fuzzing Transforms (`backend/app/darwin_audio/`):**
   - 14 deterministic acoustic operators: background noise injection, SNR variations, time-stretch (fast/slow pacing), pitch shifting, clipping, bandpass filtering, packet loss simulation.
3. **Genetic Algorithm & Evolutionary Loop:**
   - Population initialization, fitness evaluation, elite selection, stochastic mutation across generations.
   - Hard budget cap (`DARWIN_MAX_SESSIONS = 60`) strictly enforced.
4. **Delta Debugging Minimizer (`ddmin`):**
   - Algorithmic pruning of multi-turn failing conversations into the minimal 1-turn reproduction.
5. **Root-Cause Diagnoser & Patcher:**
   - Classification of failure taxonomy (`SELF_CORRECTION_MISSED`, `HALLUCINATION`, `TOOL_CALL_MISMATCH`).
   - Generation of verified system prompt patches.
6. **Regression Lock-In:**
   - 1-click export to version-controlled JSON regression test cases in `scenarios/regression/`.

---

## 5. Existing Baseline Test Suite Results

* **PyTest Command:**
  ```bash
  backend\.venv\Scripts\python.exe -m pytest backend/tests -q -m "not speech"
  ```
* **Execution Status:** **100% Passed**
* **Summary:**
  - **240 passed**
  - **19 deselected** (speech-marked real integration tests that run in dedicated speech environments)
  - **3 deprecation warnings** (Starlette / pytest-asyncio upstream notices)
  - **Total execution time:** 159.54s (02:39)
  - **Known Failures:** `0`

---

## 6. Frontend Build Status

* **Command:** `npm run build` (in `frontend/`)
* **Framework:** Next.js 16.4.3 (Turbopack, App Router), React 19, TypeScript
* **Result:** **Compiled cleanly with 0 type errors and 0 lint warnings**.
* **All App Routes Verified:**
  - `/` (Home landing)
  - `/register` & `/login` (Unified auth)
  - `/dashboard` (Executive metrics & active runs)
  - `/playground` (Interactive voice agent testing)
  - `/audio` (Audio Lab with transcript scoring)
  - `/audio/darwin` (Acoustic adversarial evolution)
  - `/benchmarks` (Engine comparison leaderboard)
  - `/analytics` (Robustness heatmaps & drift detection)
  - `/agents` & `/agents/new` (Agent registry)
  - `/scenarios` (Scenario runner)
  - `/runs` & `/runs/[id]` (Execution history)
  - `/darwin` & `/darwin/[id]` (Darwin campaign tracking)
  - `/regressions` (CI regression corpus)

---

## 7. Baseline Protection Commitment

1. The baseline Git tag `wispr-flow-baseline` points to `9e054e3effd820e06f5bdbc21500bb6dfbe51a81`.
2. All subsequent work for Gnani AI integration will be developed on `feature/gnani-integration`.
3. Every existing Wispr Flow scenario and test must continue to pass before any merge.

