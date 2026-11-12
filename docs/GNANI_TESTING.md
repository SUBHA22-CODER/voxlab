# Gnani AI Testing & Verification Suite

## 1. Overview
The Gnani AI integration is protected by two distinct layers of automated testing:
1. **Mock & Unit Test Layer**: Fast, deterministic, hermetic tests that validate client retry logic, error handling, normalization, and Darwin personas without making external network calls.
2. **Live API Integration Layer**: End-to-end tests marked with `@pytest.mark.live_api` that execute real HTTP requests against `https://api.vachana.ai`.

---

## 2. Running Unit & Mock Tests
To execute all offline Gnani tests without requiring API credentials or external network access:
```bash
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_gnani_client.py tests/test_indic_normalization.py tests/test_darwin_indic_personas.py tests/test_indic_api.py -v
```

### Coverage:
- `test_gnani_client.py`: 7 tests covering request construction, retry exponential backoff, rate limiting (HTTP 429), auth rejection (HTTP 401), and log redaction.
- `test_indic_normalization.py`: 5 tests covering Devanagari numeral normalization (`५,०००` -> `5000`), Danda stripping, Unicode NFC unification, and code-switch ratio calculation.
- `test_darwin_indic_personas.py`: 4 tests validating Hinglish switcher, Benglish speaker, noise injector, and fast/slow speech personas.
- `test_indic_api.py`: 4 tests asserting route contracts for `/languages`, `/benchmarks`, `/evaluate`, and `/voices`.

---

## 3. Running Live API Integration Tests
Live tests require `GNANI_ENABLED=true` and a valid `GNANI_API_KEY` set in `backend/.env`.

Command:
```bash
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_gnani_live.py -v -m live_api -s
```

### Verified Live Output:
```text
tests/test_gnani_live.py::test_live_gnani_health_and_connectivity PASSED
tests/test_gnani_live.py::test_live_timbre_speech_synthesis 
[LIVE TEST] Timbre TTS generation latency: 2.648s for 97324 bytes
PASSED
tests/test_gnani_live.py::test_live_prisma_speech_transcription 
[LIVE TEST] Prisma Reference: नमस्ते यह वॉक्सलैब का परीक्षण है
[LIVE TEST] Prisma Hypothesis: नमस्ते यह वॉक्स लैब का परीक्षण है
[LIVE TEST] Live Indic WER: 0.3333, CER: 0.0312
PASSED

============================== 3 passed in 8.77s ==============================
```

