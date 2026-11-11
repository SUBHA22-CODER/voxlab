# build_human_voice_benchmark.py
# Real human-voice benchmark (public-domain LibriVox recordings).
#
# Design: every LibriVox audiobook opens with the SAME standard disclaimer
# sentence, read by a different human narrator per book. That gives a
# controlled benchmark: identical reference text, genuinely different human
# voices, accents, and rooms. The recordings are public domain
# (librivox.org); short 16-second fixtures are committed for reproducibility
# with attribution — no private recordings are ever used (product rule).
#
# Usage (from backend/):
#   .venv/Scripts/python.exe scripts/build_human_voice_benchmark.py
#
# Outputs:
#   tests/fixtures/human_voices/<case_id>.wav  (16 kHz mono fixtures)
#   tests/fixtures/human_voices/ATTRIBUTION.md
#   data/audio/benchmarks/human-voices-v1/     (manifest for the drift layer)
#   stdout: per-engine results table

from __future__ import annotations

import io
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import av  # (PyAV ships with faster-whisper)
import numpy as np

from app.core.config import get_settings

# (case_id, archive.org item, file, attribution)
CLIPS: list[tuple[str, str, str, str]] = [
    (
        "expressman-male-us",
        "expressman_and_detective_1103_librivox",
        "theexpressmanandthedetective_00_pinkerton_64kb.mp3",
        "The Expressman and the Detective by Allan Pinkerton, read by a male US narrator",
    ),
    (
        "janeeyre-female-uk",
        "jane_eyre_ver03_0809_librivox",
        "janeeyre_01_bronte_64kb.mp3",
        "Jane Eyre by Charlotte Brontë, read by a female UK narrator",
    ),
    (
        "tomsawyer-male-us-2",
        "adventures_of_tom_sawyer_1402_librivox",
        "adventuresoftomsawyer_00_twain_64kb.mp3",
        "The Adventures of Tom Sawyer by Mark Twain, read by a male US narrator",
    ),
    (
        "prideprejudice-female-uk-2",
        "prideandprejudice_1107_librivox",
        "prideandprejudice_01_austen_64kb.mp3",
        "Pride and Prejudice by Jane Austen, read by a female UK narrator",
    ),
]

# The standard LibriVox opening, identical (modulo the site address) across
# all four narrators. Reference text for every case.
REFERENCE_TEXT = (
    "This is a LibriVox recording. All LibriVox recordings are in the "
    "public domain. For more information or to volunteer, please visit "
    "librivox.org."
)

TRIM_SECONDS = 16.0


def download_clip(item: str, file: str) -> bytes:
    import httpx

    url = f"https://archive.org/download/{item}/{file}"
    with httpx.Client(follow_redirects=True, timeout=300.0) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.content


def decode_trim_mono16k(blob: bytes, seconds: float) -> np.ndarray:
    """Decode any container via PyAV, take the first `seconds`, downmix to
    mono, and resample to 16 kHz float32 using the platform's own pipeline."""
    container = av.open(io.BytesIO(blob))
    resampler = av.AudioResampler(format="s16", layout="mono", rate=16_000)
    chunks: list[bytes] = []
    accumulated = 0.0
    for packet in container.demux(audio=0):
        for frame in packet.decode():
            resampled = resampler.resample(frame)
            for out in resampled:
                chunks.append(bytes(out.planes[0]))
                accumulated += out.samples / 16_000.0
            if accumulated >= seconds:
                break
        if accumulated >= seconds:
            break
    pcm = b"".join(chunks)
    samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0
    return samples[: int(seconds * 16_000)]


def wav_bytes(samples: np.ndarray) -> bytes:
    import wave

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16_000)
        wav.writeframes((np.clip(samples, -1.0, 1.0) * 32767.0).astype("<i2").tobytes())
    return buf.getvalue()


def main() -> None:
    fixtures_dir = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "human_voices"
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    cases: list[dict[str, str]] = []
    for case_id, item, file, _attribution in CLIPS:
        wav_path = fixtures_dir / f"{case_id}.wav"
        if not wav_path.exists():
            print(f"[human] downloading {case_id} from archive.org …")
            blob = download_clip(item, file)
            samples = decode_trim_mono16k(blob, TRIM_SECONDS)
            wav_path.write_bytes(wav_bytes(samples))
        else:
            samples = decode_trim_mono16k(wav_path.read_bytes(), TRIM_SECONDS)
        loaded = load_audio(wav_path.read_bytes(), filename=f"{case_id}.wav")
        prepared, prep = prepare_engine_audio(loaded)
        duration = prep["duration_seconds"]
        rms = float(np.sqrt(np.mean(np.square(prepared, dtype=np.float64))))
        print(f"[human] {case_id}: {duration:.2f}s, rms {rms:.4f}")
        cases.append({"id": case_id, "wav": wav_path.name, "duration_seconds": duration})

    attribution = "\n\n".join(
        f"- **{cid}.wav** — {attr}. Source: LibriVox (public domain), "
        f"https://archive.org/details/{item} — 16-second opening disclaimer, "
        "resampled to 16 kHz mono."
        for cid, _item, _file, attr in CLIPS
    )
    (fixtures_dir / "ATTRIBUTION.md").write_text(
        "# Human-voice fixture attribution\n\n"
        "All clips are openings of LibriVox public-domain audiobook recordings "
        "(standard LibriVox disclaimer, different human narrator per clip). "
        "No private recordings.\n\n" + attribution + "\n",
        encoding="utf-8",
    )

    # Drift-layer manifest so the platform can snapshot this dataset.
    dataset_dir = Path(get_settings().audio_storage_dir) / "benchmarks" / "human-voices-v1"
    dataset_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "name": "human-voices-v1",
        "description": "Real human voices (public-domain LibriVox narrators, "
        "4 clips): identical disclaimer reference text, different voices, "
        "accents, and rooms.",
        "created_at": datetime.now(UTC).isoformat(),
        "generator": "scripts/build_human_voice_benchmark.py",
        "cases": [
            {"id": c["id"], "text": REFERENCE_TEXT, "wav": c["wav"], "language": "en"}
            for c in cases
        ],
    }
    (dataset_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    for case in cases:
        (dataset_dir / case["wav"]).write_bytes((fixtures_dir / case["wav"]).read_bytes())
    print(f"[human] manifest: {dataset_dir / 'manifest.json'} ({len(cases)} cases)")
    print(f"[human] fixtures: {fixtures_dir}")


if __name__ == "__main__":
    main()
