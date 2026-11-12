# VoxLab — Gnani AI Integration & Indic Speech Lab Implementation Plan

**Document Version:** 1.0.0  
**Date:** 2026-11-12  
**Target Milestone:** Dual-Provider Production Architecture (Wispr Flow + Gnani AI)  
**Baseline SHA:** `9e054e3effd820e06f5bdbc21500bb6dfbe51a81`  
**Git Branch:** `feature/gnani-integration`  
**Author:** Principal Software Architect & Speech ML Engineer

---

## 1. Executive Summary & Core Objectives

VoxLab is evolving from a single-engine dictation reliability tool into a **provider-independent voice AI reliability infrastructure platform**. 

### Dual-Provider Mandate:
1. **Wispr Flow Protection:** Maintain 100% backward compatibility with all existing Wispr Flow workflows, cleaner agents, transcription scoring (`/api/v1/audio/score`), and conversational stress benchmarks.
2. **Gnani AI Integration:** Integrate official Gnani AI APIs (Prisma v2.5 / v3.0 STT, Timbre v2.5 / v3.0 TTS) to launch the **Indic Speech Testing Lab** covering 10+ Indian languages (Hindi, Bengali, Tamil, Telugu, Kannada, Marathi, Gujarati, etc.) and code-switching dialects (Hinglish, Benglish, Tanglish).
3. **Darwin Indic Upgrades:** Augment Darwin's genetic mutation engine with code-switching and Indic phonetic stress operators.

---

## 2. Current vs. Proposed Architecture

### 2.1 Current Architecture
```text
Client (Web UI / CI CLI)
    │
FastAPI Layer (REST + WebSockets)
    │
├── App Core (DB, Auth, Rate Limits, AES-GCM Encryptor)
├── Speech Engine Abstraction (SpeechEngine)
│     ├── whisper_local (Autoregressive Transformer)
│     ├── vosk (Kaldi HMM-DNN Hybrid)
│     └── wav2vec2 (Self-Supervised CTC)
├── Darwin Audio Engine (14 transforms, 10 personas, ddmin)
├── Evaluation Engine (WER, CER, Numbers, Entities, Semantics)
└── Scenario / Agent Runner (HTTP, WebSocket)
```

### 2.2 Proposed Provider-Independent Architecture
```text
Client (Next.js 16 Web UI / CI CLI)
    │
FastAPI Control Plane (/api/v1/...)
    │
├── Provider Registry (Unified capability & health negotiation)
│     ├── Provider: Wispr Flow (Dictation & conversational cleaner)
│     └── Provider: Gnani AI (Indic Multilingual Voice AI)
│           ├── Prisma STT Adapter (v2.5 & v3.0, Indic ASR)
│           └── Timbre TTS Adapter (v2.5 & v3.0, Indic Speech Synthesis)
│
├── Speech Engine Layer (Local & Cloud Hybrid)
│     ├── Whisper / Vosk / Wav2Vec2 (Local On-Prem Engines)
│     └── Gnani Prisma STT (Cloud REST & Stream Engine)
│
├── Indic Speech Lab
│     ├── Indic Language Registry (hi-IN, bn-IN, ta-IN, te-IN, kn-IN, mr-IN, gu-IN, etc.)
│     ├── Code-Switching Suites (Hinglish, Benglish, Tanglish)
│     └── Indic Evaluation Engine (Script normalization, Devanagari numerals, Unicode normalization)
│
├── Upgraded Darwin Engine
│     ├── Original Personas & Acoustic Transforms (Preserved)
│     └── 12 New Indic Personas & Mutators (HinglishSwitcher, ProperNounConfuser, etc.)
│
└── Provider Comparison & CI Quality Gate
```

---

## 3. Existing Files to Reuse

| Existing File | Reusable Functionality |
| :--- | :--- |
| `backend/app/speech/base.py` | `SpeechEngine`, `AudioData`, `TranscriptionResult`, `EngineCapabilities` |
| `backend/app/speech/registry.py` | Engine registration, capability reporting, install hints |
| `backend/app/speech/metrics.py` | Exact Levenshtein WER, CER, Token Accuracy, Number Canonicalization |
| `backend/app/speech/alignment.py` | Word-level alignment, operation labeling, timing assignment |
| `backend/app/speech/semantic.py` | Deterministic semantic error detection |
| `backend/app/core/config.py` | Pydantic BaseSettings management |
| `backend/app/core/security.py` | AES-GCM encryption for provider credentials |
| `backend/app/darwin_audio/` | Genome representation, acoustic mutators, delta debugging (`ddmin`) |
| `frontend/src/components/ui/` | Design system (buttons, cards, badges, tabs, metrics) |

---

## 4. New Files to Create

### Backend (`backend/app/`)
* **Gnani Provider Package (`backend/app/providers/gnani/`):**
  * `__init__.py`: Package exports.
  * `client.py`: Async, resilient Gnani HTTP client (`api.vachana.ai`) with retries, exponential backoff, credential redaction, and timeout handling.
  * `schemas.py`: Strictly-typed Pydantic request/response schemas for Prisma STT and Timbre TTS.
  * `prisma_adapter.py`: SpeechEngine-compliant adapter for Prisma STT (v2.5 / v3.0).
  * `timbre_adapter.py`: Dedicated adapter for Timbre TTS (audio synthesis, timing, playback buffer).
  * `languages.py`: Indic language registry with ISO codes, regional scripts, and supported voices.
* **Indic Speech Lab (`backend/app/indic/`):**
  * `__init__.py`
  * `normalization.py`: Indic-specific text normalization (Unicode NFC, chandrabindu, virama, numeral mapping).
  * `benchmarks.py`: Indic benchmark suite definitions (Hindi, Tamil, Telugu, Hinglish, code-switching).
* **Darwin Indic Mutators (`backend/app/darwin/indic_mutators.py`):**
  * 12 specialized Indic personas and acoustic/conversational mutators.
* **API Endpoints (`backend/app/api/v1/`):**
  * `indic.py`: Endpoints for Indic Speech Lab, Timbre TTS synthesis, and Prisma transcription.
  * `providers.py`: Provider health, connection checks, capability querying.

### Backend Tests (`backend/tests/`):
* `test_gnani_client.py`: Mocked HTTP unit tests for client resilience, retries, headers, and credential redaction.
* `test_prisma_adapter.py`: Mocked unit & integration tests for Prisma STT.
* `test_timbre_adapter.py`: Mocked unit & integration tests for Timbre TTS.
* `test_indic_normalization.py`: Unit tests for Indic script normalization and numeral expansion.
* `test_darwin_indic_mutators.py`: Unit tests for the 12 new Indic personas and code-switch mutators.
* `test_wispr_flow_protection.py`: Regression assertions verifying Wispr Flow endpoints remain 100% operational.
* `test_gnani_live.py`: Operator-controlled real API test suite (inactive until API key provided).

### Frontend (`frontend/src/`):
* `frontend/src/app/(app)/indic/page.tsx`: Indic Speech Lab & Code-Switching Dashboard.
* `frontend/src/app/(app)/tts/page.tsx`: Timbre TTS interactive speech synthesis lab.
* `frontend/src/app/(app)/providers/page.tsx`: Unified Provider settings & connection validator.
* `frontend/src/components/indic/`: Indic test components, audio recorder, and comparison radar.

---

## 5. Files to Modify

* `backend/app/core/config.py`: Add `gnani_enabled`, `gnani_api_key`, `gnani_base_url`, `gnani_stt_model`, `gnani_tts_model`.
* `backend/app/api/v1/__init__.py`: Include `indic.py` and `providers.py` in API v1 router.
* `backend/app/speech/registry.py`: Register Gnani Prisma STT into default registry when enabled.
* `backend/.env.example`: Document Gnani configuration variables.
* `frontend/src/lib/api.ts`: Add typed API methods for Gnani, Indic benchmarks, and TTS.
* `frontend/src/app/(app)/layout.tsx`: Add navigation links for Indic Lab, TTS Lab, and Providers.
* `README.md`: Document dual-provider architecture, Indic Speech Lab, and setup instructions.

---

## 6. Official Gnani API Specifications (Verified)

### 6.1 Base URL
```text
https://api.vachana.ai
```

### 6.2 Prisma Speech-to-Text (v2.5 / v3.0)
* **Endpoint:** `POST /stt/v3`
* **Authentication:** Header `X-API-Key-ID: <api_key>`
* **Content-Type:** `multipart/form-data`
* **Parameters:**
  * `audio_file`: Binary audio (`wav`, `mp3`, `flac`, `ogg`)
  * `model`: `prisma-v2.5` or `prisma-v3.0`
  * `language_code`: `hi-IN`, `bn-IN`, `ta-IN`, `te-IN`, `kn-IN`, `mr-IN`, `gu-IN`, `en-IN`, `indic-auto`
* **Response Schema:**
  ```json
  {
    "success": true,
    "request_id": "string",
    "transcript": "string",
    "model": "string",
    "detected_language_code": "string",
    "processing_time": 0.58,
    "end_to_end_latency": 0.66
  }
  ```

### 6.3 Timbre Text-to-Speech (v2.5 / v3.0)
* **Endpoint:** `POST /api/v1/tts/inference`
* **Authentication:** Header `X-API-Key-ID: <api_key>`
* **Content-Type:** `application/json`
* **Parameters:**
  ```json
  {
    "text": "string",
    "voice": "string",
    "model": "timbre-v2.5",
    "language": "hi-IN",
    "speed": 1.0,
    "audio_config": {
      "encoding": "linear_pcm",
      "container": "wav",
      "num_channels": 1,
      "sample_rate": 16000,
      "sample_width": 2
    }
  }
  ```
* **Response:** Binary audio stream / WAV payload with `Content-Type: audio/wav`.

---

## 7. Security & Isolation Architecture

1. **Zero Frontend Exposure:** `GNANI_API_KEY` is exclusively read by backend services. The frontend never receives, stores, or handles the raw API key.
2. **Encrypted Storage:** Provider credentials configured via UI are encrypted using AES-GCM prior to persistence in `agents.config`.
3. **Log Sanitization:** `client.py` strictly redacts headers matching `*key*`, `*token*`, or `*secret*`.
4. **Graceful Fallbacks:** If `GNANI_ENABLED=false` or credentials are unset, the platform operates normally with local engines (Whisper, Vosk, Wav2Vec2) and Wispr Flow workflows without error cascades.

---

## 8. Testing & Acceptance Criteria

1. **Wispr Flow Protection:** All 240 baseline tests must continue to pass with 0 regressions.
2. **Mocked Unit Test Suite:** High-coverage tests for Gnani client, request builders, retry loops, and error parsing.
3. **Indic Evaluation Suite:** Automated tests for Indic normalization, numeral mapping, and code-switching metrics.
4. **Clean Builds:** `npm run build` in `frontend` and `pytest backend/tests` in `backend` must execute with 0 failures.
5. **Live Readiness:** Operator-controlled test command `test:gnani-live` prepared for execution when the user provides credentials.

