# Gnani AI Integration Guide

## 1. Executive Summary
VoxLab seamlessly integrates official **Gnani AI** speech services alongside **Wispr Flow** dictation workflows without architectural collision. This turns VoxLab into a multi-provider platform capable of testing global conversational voice systems, dictation pipelines, and Indic vernacular voice infrastructure.

Official Gnani APIs Integrated:
- **Prisma v2.5 / v3.0 Speech-to-Text (STT)**: Utterance-level transcription covering 12+ Indian languages and code-switching dialects.
- **Timbre v2.5 / v3.0 Text-to-Speech (TTS)**: Expressive neural voice generation across regional Indian accents and dialects.

Documentation Reference: [https://docs.gnani.ai/](https://docs.gnani.ai/)

---

## 2. API Endpoints & Contracts

### 2.1 Prisma Speech-to-Text
- **Endpoint**: `POST https://api.vachana.ai/stt/v3`
- **Authentication**: `X-API-Key-ID: <GNANI_API_KEY>`
- **Payload**: `multipart/form-data`
  - `audio_file`: Binary audio stream (`audio/wav`, 16kHz mono recommended).
  - `model`: `prisma-v2.5` (default) or `prisma-v3.0`.
  - `language_code`: BCP-47 language tag (e.g., `hi-IN`, `ta-IN`, `indic-auto`).
- **Response Schema**:
  ```json
  {
    "success": true,
    "transcript": "नमस्ते यह वॉक्स लैब का परीक्षण है",
    "detected_language_code": "hi-IN",
    "processing_time": 1.42,
    "request_id": "req-98f12a"
  }
  ```

### 2.2 Timbre Text-to-Speech
- **Endpoint**: `POST https://api.vachana.ai/api/v1/tts/inference`
- **Authentication**: `X-API-Key-ID: <GNANI_API_KEY>`
- **Content-Type**: `application/json`
- **Payload**:
  ```json
  {
    "text": "नमस्ते, वॉक्सलैब में आपका स्वागत है।",
    "voice": "Nalini",
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
- **Response**: Binary WAV audio stream (`audio/wav`).

---

## 3. Configuration & Security

### 3.1 Environment Variables
Add to your environment or root `.env` and `backend/.env`:
```env
GNANI_ENABLED=true
GNANI_API_KEY=your_gnani_vachana_key_here
GNANI_BASE_URL=https://api.vachana.ai
GNANI_STT_MODEL=prisma-v2.5
GNANI_TTS_MODEL=timbre-v2.5
```

### 3.2 Security Posture
- **Backend-Only Storage**: `GNANI_API_KEY` is loaded exclusively into the backend runtime via Pydantic `Settings`.
- **Zero Frontend Leakage**: The Next.js frontend calls VoxLab proxy routes (`/api/v1/indic/*`), never Gnani directly.
- **Log Credential Redaction**: All request/response logging redacts `X-API-Key-ID` to `REDACTED`.
- **Git Protection**: Verified untracked in Git; explicit entries exist in `.gitignore`.

---

## 4. Architecture Diagram
```
                     +---------------------------------------+
                     |           VoxLab Dashboard            |
                     |  (Indic Speech Lab, Timbre TTS Lab)   |
                     +-------------------+-------------------+
                                         |
                                         | Next.js API Client
                                         v
                     +---------------------------------------+
                     |            FastAPI Backend            |
                     |          (/api/v1/indic/*)            |
                     +-------------------+-------------------+
                                         |
           +-----------------------------+-----------------------------+
           |                                                           |
           v                                                           v
+----------------------+                                   +-----------------------+
|  Wispr Flow Adapter  |                                   |   Gnani AI Provider   |
| (Dictation Pipeline, |                                   | (Prisma STT & Timbre) |
|   Darwin Mutator)    |                                   +-----------+-----------+
+----------------------+                                               |
                                           +---------------------------+---------------------------+
                                           |                                                       |
                                           v                                                       v
                               +-----------------------+                               +-----------------------+
                               |   POST /stt/v3        |                               | POST /tts/inference   |
                               | (Prisma Conformer ASR)|                               |  (Timbre Multi-Voice) |
                               +-----------------------+                               +-----------------------+
```

