# audio_darwin_demo.py
# End-to-end demonstration: real audio + real speech engine + Darwin audio
# evolution discovering REAL transcription failures, minimized and persisted.
#
# Usage (from backend/):
#   .venv/Scripts/python.exe scripts/audio_darwin_demo.py \
#       --text "Schedule the kubernetes deployment for order forty two" \
#       --population 4 --generations 2 --model tiny
#
# Uses a throwaway SQLite DB and artifact dir under the system temp by default
# so the demo never pollutes development data. Findings are printed as JSON.

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.core.database import Base  # noqa: E402
from app.darwin_audio.artifacts import AudioArtifactStore  # noqa: E402
from app.darwin_audio.evolution import DarwinAudioEngine  # noqa: E402
from app.models import User  # noqa: E402
from app.models.darwin_audio import AudioFinding, DarwinAudioRun  # noqa: E402
from app.speech.audio import load_audio, prepare_engine_audio  # noqa: E402
from app.speech.registry import engine_registry  # noqa: E402
from app.speech.tts import synthesize_to_wav  # noqa: E402


async def main() -> None:
    parser = argparse.ArgumentParser(description="VoxLab audio Darwin demo")
    parser.add_argument(
        "--text",
        default="Schedule the kubernetes deployment for order forty two on Friday",
    )
    parser.add_argument("--population", type=int, default=4)
    parser.add_argument("--generations", type=int, default=2)
    parser.add_argument("--model", default="tiny")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    tmp = Path(tempfile.mkdtemp(prefix="voxlab-darwin-demo-"))
    print(f"[demo] workspace: {tmp}")

    # 1. Seed audio: offline SAPI synthesis of the reference sentence.
    seed_ref_dir = tmp / "seed"
    seed_wav = await synthesize_to_wav(args.text, seed_ref_dir / "seed.wav")
    loaded = load_audio(seed_wav.read_bytes(), filename="seed.wav")
    samples, prep = prepare_engine_audio(loaded)
    print(f"[demo] seed audio: {prep['duration_seconds']:.2f}s @ 16kHz mono")

    # 2. Throwaway DB + run row.
    engine_db = create_async_engine(f"sqlite+aiosqlite:///{tmp / 'demo.db'}")
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine_db, expire_on_commit=False)

    async with factory() as db:
        user = User(email="demo@voxlab.dev", password_hash="demo")
        db.add(user)
        await db.flush()
        run = DarwinAudioRun(
            user_id=user.id,
            status="queued",
            config={
                "personas": None,  # default set (audio + content personas)
                "population_size": args.population,
                "generations": args.generations,
                "top_k": 2,
                "seed": args.seed,
                "failure_threshold": 0.35,
                "reference_transcript": args.text,
                "seed_audio_ref": "",
                "language": "en",
                "engine_id": "whisper_local",
                "technical_vocab": ["kubernetes", "deployment"],
                "entities": ["kubernetes"],
            },
            stats={},
            progress=0,
        )
        db.add(run)
        await db.commit()
        run_id = run.id

    # 3. Engine config: tiny model for a cheap demo.
    from app.speech.whisper_local.adapter import WhisperLocalEngine
    from app.speech.whisper_local.config import WhisperLocalConfig

    engine_registry.register(WhisperLocalEngine)
    original_cfg = WhisperLocalConfig(model_key=args.model, device="cpu", compute_type="int8")
    engine = engine_registry.get_engine("whisper_local")
    engine.config = original_cfg  # demo override (production uses settings)

    store = AudioArtifactStore(tmp / "artifacts")
    darwin = DarwinAudioEngine(factory, store, engine_registry)

    print(f"[demo] evolving: pop={args.population} gens={args.generations} "
          f"model={args.model} budget-capped by DARWIN_MAX_SESSIONS")
    await darwin._execute(run_id, seed_audio_override=samples)

    # 4. Report findings.
    from sqlalchemy import select

    async with factory() as db:
        run = await db.get(DarwinAudioRun, run_id)
        print(f"[demo] run status: {run.status}  progress: {run.progress}%")
        print(f"[demo] stats: {json.dumps(run.stats, indent=2)}")
        findings = (
            await db.scalars(select(AudioFinding).where(AudioFinding.run_id == run_id))
        ).all()
        print(f"\n[demo] === {len(findings)} REAL TRANSCRIPTION FAILURES DISCOVERED ===")
        for finding in findings:
            gt = finding.metrics.get("ground_truth", {})
            print(json.dumps({
                "persona": finding.persona_id,
                "failure_score": finding.fitness,
                "wer": gt.get("wer"),
                "cer": gt.get("cer"),
                "number_accuracy": gt.get("number_accuracy"),
                "technical_vocab_accuracy": gt.get("technical_vocab_accuracy"),
                "reference": finding.reference_transcript,
                "failed_transcription": finding.failed_transcript,
                "original_chain_length": finding.original_chain_length,
                "minimized_chain_length": finding.minimized_chain_length,
                "minimized_chain": (finding.reproduction or {}).get("minimized_chain"),
                "artifact": finding.audio_artifact_ref,
            }, indent=2, ensure_ascii=False))

    await engine_db.dispose()
    print(f"[demo] artifacts preserved at: {tmp}")


if __name__ == "__main__":
    asyncio.run(main())
