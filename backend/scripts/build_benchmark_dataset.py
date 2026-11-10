# build_benchmark_dataset.py
# Builds a FIXED benchmark dataset for drift detection (VoxLab 2.5 Phase 6).
#
# The utterance texts are committed constants in this script so the dataset
# is reproducible: the same command always produces the same manifest with
# the same reference texts. Audio is synthesized offline via Windows SAPI
# (a default synthetic voice). Models/audio live under AUDIO_STORAGE_DIR
# (gitignored); only this script and the docs carry the dataset definition.
#
# Usage (from backend/):
#   .venv/Scripts/python.exe scripts/build_benchmark_dataset.py --name core-en-v1

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.speech.audio import load_audio, prepare_engine_audio
from app.speech.tts import is_available as tts_available
from app.speech.tts import synthesize_to_wav

# Fixed utterances: numbers, dates, entities, technical vocabulary,
# negation, a question, and code-switching — the axes the drift tracker
# must watch.
DATASET_TEXTS: list[dict[str, str]] = [
    {"id": "case-01-numbers", "text": "Deploy version forty two to production today"},
    {"id": "case-02-date", "text": "Schedule the review meeting for Thursday morning"},
    {"id": "case-03-entity", "text": "Send the VoxLab report to Sarah by email"},
    {"id": "case-04-technical", "text": "The kubernetes cluster runs the staging deployment"},
    {"id": "case-05-negation", "text": "Do not restart the database server tonight"},
    {"id": "case-06-question", "text": "What is the current status of order fifty five?"},
    {"id": "case-07-mixed", "text": "Fifteen percent of the traffic goes to the canary deployment"},
    {"id": "case-08-instruction", "text": "Create a backup before you update the configuration"},
    {"id": "case-09-long", "text": "The engineering team will review the new speech recognition pipeline and publish a full reliability report next month"},
    {"id": "case-10-numbers-2", "text": "Order sixty sixteen was cancelled but order seventy seventeen shipped"},
]


async def build(name: str) -> None:
    if not tts_available():
        raise SystemExit("Offline TTS requires Windows SAPI; run this on Windows.")
    directory = Path(get_settings().audio_storage_dir) / "benchmarks" / name
    directory.mkdir(parents=True, exist_ok=True)

    cases: list[dict[str, str]] = []
    for spec in DATASET_TEXTS:
        wav_name = f"{spec['id']}.wav"
        wav_path = directory / wav_name
        await synthesize_to_wav(spec["text"], wav_path)
        loaded = load_audio(wav_path.read_bytes(), filename=wav_name)
        _samples, prep = prepare_engine_audio(loaded)
        cases.append(
            {
                "id": spec["id"],
                "text": spec["text"],
                "wav": wav_name,
                "duration_seconds": prep["duration_seconds"],
                "language": "en",
            }
        )
        print(f"[dataset] {wav_name}: {prep['duration_seconds']:.2f}s")

    manifest = {
        "name": name,
        "description": "Fixed benchmark dataset for model drift detection "
        "(VoxLab 2.5): numbers, dates, entities, technical vocabulary, "
        "negation, question intent, and length coverage.",
        "created_at": str(__import__("datetime").datetime.now(__import__("datetime").UTC).isoformat()),
        "generator": "scripts/build_benchmark_dataset.py",
        "cases": cases,
    }
    (directory / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(f"[dataset] manifest written: {directory / 'manifest.json'} ({len(cases)} cases)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", default="core-en-v1")
    args = parser.parse_args()
    asyncio.run(build(args.name))
