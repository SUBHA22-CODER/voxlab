# Darwin Audio Engine

> VoxLab 2.0 · Evolutionary adversarial testing for speech recognition

Darwin Audio extends the text-mode Darwin engine with **real audio**: it
mutates a seed recording, transcribes every mutant through a real speech
engine, scores the transcription against a reference, evolves the strongest
failures, and minimizes each discovery to the smallest reproducible
transformation chain.

## The loop

```
SEED AUDIO + REFERENCE TRANSCRIPT
  → per-persona genome population (presets + content mutations)
  → materialize (TTS re-synthesis or seeded audio transforms)
  → transcribe (real engine via the registry)
  → compare vs effective reference (WER/CER/number/entity metrics)
  → failure scoring with validity gates
  → select strongest failures → mutate / crossover
  → ddmin minimization of the transform chain
  → AudioFindings (the regression corpus)
```

Budget: every transcription is a session; the hard cap is
`DARWIN_MAX_SESSIONS` (default 60, single-sourced in `app/core/limits.py`).
`population × generations` is clamped before the run starts. No database
transaction is held across a transcription call.

## Attack surfaces

**Audio transformations** (`app/speech/transforms.py`, 14 operators): noise
(white/pink), typing clicks, fan hum, volume, clipping, silence insertion,
dropouts, tape-speed, pitch shift, telephony bandpass, muffle, echo, edge
fades, volume pumping. Every operator: bounded params, deterministic per
seed, source array never mutated, recorded for exact replay.

**Personas** (`app/darwin_audio/personas.py`, 10): six audio presets
(Noisy Environment, Fast Technical, Low-Volume, Interrupted, Domain-on-Harsh-
Channel, Mumbling) and four content personas (Multilingual, Self-Correcting,
Ambiguous Number, Homophone) that rewrite the transcript and re-synthesize
via offline TTS (Windows SAPI; a default synthetic voice — never a real-
person clone). Content personas degrade honestly to audio-only stress when
TTS is unavailable.

## Fitness (documented, normalized)

```
failure_score = 0.45·min(WER,1) + 0.15·min(CER,1) + 0.15·(1−number_acc)
              + 0.10·(1−entity_acc) + 0.15·(1−semantic_overlap)
```

All components live in [0,1]. Higher = the engine performed worse = a
stronger adversarial candidate. **Validity gates** prevent rewarding noise:
a candidate must remain audible (RMS ≥ −48 dBFS) and duration-preserving
(0.4×–3.0× of seed); invalid candidates are never selected.

The effective reference is honest: self-correction insertions resolve to
their replacement in the reference (the correction words exist only in the
audio); code-switched words appear in both audio and reference.

## Minimization (ddmin over chains)

When a finding is created, `app/darwin_audio/minimizer.py` shrinks the
transform chain (subset removal, granularity doubling) while the failure
still reproduces through the **real engine**. A minimized case is accepted
only when the failure was actually reproduced — never assumed. The finding
stores original + minimized chains, per-step seeds/params, and replay
instructions.

## Proven end-to-end

`backend/scripts/audio_darwin_demo.py` (whisper-tiny, CPU, SAPI seed):

- Reference: "Schedule the kubernetes deployment for order forty two on Friday"
- Engine heard: "Schedule the comparison to boyless 440Q on Friday."
- WER 0.60 · CER 0.53 · technical vocab 0.0 · number "forty two" → "440Q"
- Chain minimized 4 → 3 transforms (tape-speed 1.35× + telephony bandpass +
  echo), failure reproduced after minimization.

## API

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/darwin/audio/personas` | Persona catalog (content vs audio) |
| `GET /api/v1/darwin/audio/transforms` | Operator catalog with bounds |
| `POST /api/v1/darwin/audio/evolve` | 202; seed upload + config, background run |
| `GET /api/v1/darwin/audio/runs[/{id}]` | Run status, live progress, stats |
| `POST /api/v1/darwin/audio/runs/{id}/cancel` | Cancel |
| `GET /api/v1/darwin/audio/runs/{id}/findings` | Discovered failures |

Runs are user-scoped; seed and candidate WAVs live under `AUDIO_STORAGE_DIR`
(gitignored), addressed by validated hex ids (path-traversal safe).
