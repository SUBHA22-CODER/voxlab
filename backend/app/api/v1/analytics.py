"""VoxLab 2.5 analytics APIs: robustness heatmap (Phase 5) and model drift
detection over fixed benchmark datasets (Phase 6).

Every number comes from stored evaluation results (AudioFinding,
AudioDriftSnapshot). Empty data produces empty buckets — no fabricated
activity.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import get_settings
from app.darwin_audio.artifacts import ArtifactError
from app.models import User
from app.models.analytics_models import AudioDriftSnapshot
from app.models.darwin_audio import AudioFinding
from app.speech.audio import load_audio, prepare_engine_audio
from app.speech.base import AudioData
from app.speech.drift import compare_snapshots
from app.speech.exceptions import SpeechError
from app.speech.metrics import NormalizationConfig, compute_transcript_metrics
from app.speech.runtime import get_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics-v1"])


def _param_value(chain: list[dict], operator: str, key: str) -> float | None:
    """First matching parameter value from a stored transform chain."""
    for spec in chain or []:
        if spec.get("operator") == operator:
            value = (spec.get("params") or {}).get(key)
            if isinstance(value, (int, float)):
                return float(value)
    return None


def _bucket(value: float, edges: list[tuple[float, str]]) -> str:
    for limit, label in edges:
        if value < limit:
            return label
    return edges[-1][1]


@router.get("/robustness")
async def robustness_heatmap(
    engine: str | None = None,
    model_version: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Robustness aggregation over the user's real Darwin audio findings.

    Condition buckets are derived from the actual transform parameters of
    each finding's chain (noise SNR, tape-speed rate, candidate duration) —
    conditions that were never tested simply have no bucket.
    """
    query = select(AudioFinding).where(
        AudioFinding.run.has(user_id=user.id)
    )
    rows = (await db.scalars(query)).all()

    filtered: list[AudioFinding] = []
    for row in rows:
        repro = row.reproduction or {}
        if engine and repro.get("engine") != engine:
            continue
        if model_version and (repro.get("model") or "") != model_version:
            continue
        created = row.created_at
        if date_from:
            try:
                if created < datetime.fromisoformat(date_from).replace(tzinfo=UTC):
                    continue
            except ValueError:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Invalid date_from: {date_from}",
                ) from None
        if date_to:
            try:
                if created > datetime.fromisoformat(date_to).replace(tzinfo=UTC):
                    continue
            except ValueError:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Invalid date_to: {date_to}",
                ) from None
        filtered.append(row)

    def _agg(items: list[AudioFinding]) -> dict | None:
        wers = [
            (r.metrics or {}).get("ground_truth", {}).get("wer")
            for r in items
        ]
        wers = [w for w in wers if isinstance(w, (int, float))]
        if not items:
            return None
        return {
            "count": len(items),
            "evaluated": len(wers),
            "mean_wer": round(sum(wers) / len(wers), 4) if wers else None,
            "max_wer": round(max(wers), 4) if wers else None,
        }

    by_persona: dict[str, dict] = {}
    noise_buckets: dict[str, dict] = {}
    speed_buckets: dict[str, dict] = {}
    duration_buckets: dict[str, dict] = {}

    NOISE_EDGES = [(10.0, "loud_noise"), (20.0, "moderate_noise"), (float("inf"), "quiet_noise")]
    SPEED_EDGES = [(1.0, "slow"), (1.2, "normal_speed"), (float("inf"), "fast")]
    DURATION_EDGES = [(5.0, "short"), (15.0, "medium"), (float("inf"), "long")]

    for row in filtered:
        chain = (row.genome or {}).get("transform_chain", [])
        gt = (row.metrics or {}).get("ground_truth", {})

        persona = by_persona.setdefault(row.persona_id, {"count": 0, "wer_sum": 0.0, "wer_n": 0})
        persona["count"] += 1
        wer = gt.get("wer")
        if isinstance(wer, (int, float)):
            persona["wer_sum"] += wer
            persona["wer_n"] += 1

        snr = _param_value(chain, "add_background_noise", "snr_db")
        if snr is not None:
            bucket = noise_buckets.setdefault(_bucket(snr, NOISE_EDGES), {"count": 0, "wer_sum": 0.0, "wer_n": 0})
            bucket["count"] += 1
            if isinstance(wer, (int, float)):
                bucket["wer_sum"] += wer
                bucket["wer_n"] += 1

        rate = _param_value(chain, "tape_speed_change", "rate")
        if rate is not None:
            bucket = speed_buckets.setdefault(_bucket(rate, SPEED_EDGES), {"count": 0, "wer_sum": 0.0, "wer_n": 0})
            bucket["count"] += 1
            if isinstance(wer, (int, float)):
                bucket["wer_sum"] += wer
                bucket["wer_n"] += 1

        duration = (row.metrics or {}).get("ground_truth", {}).get("processing_latency_seconds")
        if duration is not None:
            bucket = duration_buckets.setdefault(
                _bucket(duration, DURATION_EDGES), {"count": 0, "wer_sum": 0.0, "wer_n": 0}
            )
            bucket["count"] += 1
            if isinstance(wer, (int, float)):
                bucket["wer_sum"] += wer
                bucket["wer_n"] += 1

    def _finalize(bucket_map: dict[str, dict]) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for label, data in bucket_map.items():
            out[label] = {
                "count": data["count"],
                "mean_wer": round(data["wer_sum"] / data["wer_n"], 4) if data["wer_n"] else None,
            }
        return out

    return {
        "total_findings": len(filtered),
        "filters": {
            "engine": engine,
            "model_version": model_version,
            "date_from": date_from,
            "date_to": date_to,
        },
        "by_persona": {
            pid: {
                "count": d["count"],
                "mean_wer": round(d["wer_sum"] / d["wer_n"], 4) if d["wer_n"] else None,
            }
            for pid, d in by_persona.items()
        },
        "by_noise_level": _finalize(noise_buckets),
        "by_speaking_speed": _finalize(speed_buckets),
        "by_duration": _finalize(duration_buckets),
        "note": "aggregated from stored Darwin audio findings; absent buckets mean the condition was never tested",
    }


# --- Phase 6: fixed benchmark datasets + drift snapshots -----------------------


# Committed datasets shipped with the repo (available on fresh installs/CI
# where the gitignored data/ directory does not exist).
COMMITTED_DATASETS_DIR = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "datasets"


def _dataset_dir(name: str) -> Path:
    if not name.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Dataset name must be alphanumeric (dashes/underscores allowed).",
        )
    storage_dir = Path(get_settings().audio_storage_dir) / "benchmarks" / name
    if storage_dir.exists():
        return storage_dir
    committed = COMMITTED_DATASETS_DIR / name
    if committed.exists():
        return committed
    return storage_dir  # caller reports the honest 404


@router.get("/datasets")
async def list_datasets(user: User = Depends(get_current_user)):
    """Fixed benchmark datasets available (storage dir first, then the
    committed fixtures shipped with the repo)."""
    roots = [Path(get_settings().audio_storage_dir) / "benchmarks", COMMITTED_DATASETS_DIR]
    datasets: list[dict] = []
    seen: set[str] = set()
    for base in roots:
        if not base.exists():
            continue
        for manifest_path in sorted(base.glob("*/manifest.json")):
            name = manifest_path.parent.name
            if name in seen:
                continue
            seen.add(name)
            try:
                import json

                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                datasets.append(
                    {
                        "name": name,
                        "case_count": len(manifest.get("cases", [])),
                        "description": manifest.get("description", ""),
                    }
                )
            except (OSError, ValueError):
                continue
    return datasets


async def _run_dataset(
    db: AsyncSession,
    user: User,
    dataset_name: str,
    engine_id: str,
) -> AudioDriftSnapshot:
    directory = _dataset_dir(dataset_name)
    manifest_path = directory / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Dataset '{dataset_name}' not found (build it with scripts/build_benchmark_dataset.py).",
        )
    import json

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cases = manifest.get("cases") or []
    if not cases:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Dataset has no cases.")

    engine = await get_engine(engine_id)
    results: list[dict] = []
    for case in cases:
        wav_path = directory / str(case.get("wav", ""))
        entry: dict = {"case_id": case.get("id")}
        try:
            blob = wav_path.read_bytes()
            loaded = load_audio(blob, filename=str(case.get("wav", "case.wav")))
            samples, _prep = prepare_engine_audio(loaded)
            result = await engine.transcribe(
                AudioData(samples=samples, sample_rate=16000),
                language=case.get("language", "en"),
            )
            report = compute_transcript_metrics(
                str(case.get("text", "")),
                result.text,
                hypothesis_language=result.language,
                processing_time_seconds=result.processing_time_seconds,
                audio_duration_seconds=result.duration_seconds,
                normalization=NormalizationConfig(expand_numbers=True),
            ).to_dict()
            gt = report["ground_truth"]
            entry.update(
                {
                    "wer": gt["wer"],
                    "cer": gt["cer"],
                    "rtf": gt["realtime_factor"],
                    "hypothesis": result.text,
                    "error": None,
                }
            )
        except (OSError, SpeechError, ArtifactError) as exc:
            entry.update({"wer": None, "cer": None, "rtf": None, "hypothesis": "", "error": str(exc)[:200]})
        results.append(entry)

    wers = [r["wer"] for r in results if isinstance(r["wer"], (int, float))]
    cers = [r["cer"] for r in results if isinstance(r["cer"], (int, float))]
    rtfs = [r["rtf"] for r in results if isinstance(r["rtf"], (int, float))]
    snapshot = AudioDriftSnapshot(
        user_id=user.id,
        dataset_name=dataset_name,
        engine=engine.engine_id(),
        model_version=str(engine.get_metadata().model or ""),
        case_count=len(results),
        mean_wer=round(sum(wers) / len(wers), 4) if wers else 0.0,
        mean_cer=round(sum(cers) / len(cers), 4) if cers else 0.0,
        mean_rtf=round(sum(rtfs) / len(rtfs), 4) if rtfs else 0.0,
        results=results,
    )
    db.add(snapshot)
    await db.commit()
    return snapshot


@router.post("/datasets/{name}/snapshot", status_code=status.HTTP_201_CREATED)
async def create_snapshot(
    name: str,
    engine_id: str = "whisper_local",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Evaluate the fixed dataset with the current engine/model and store an
    immutable snapshot for drift tracking."""
    return _snapshot_out(await _run_dataset(db, user, name, engine_id))


def _snapshot_out(snapshot: AudioDriftSnapshot) -> dict:
    return {
        "id": snapshot.id,
        "dataset_name": snapshot.dataset_name,
        "engine": snapshot.engine,
        "model_version": snapshot.model_version,
        "case_count": snapshot.case_count,
        "mean_wer": snapshot.mean_wer,
        "mean_cer": snapshot.mean_cer,
        "mean_rtf": snapshot.mean_rtf,
        "created_at": snapshot.created_at.isoformat(),
    }


@router.get("/datasets/{name}/snapshots")
async def list_snapshots(
    name: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.scalars(
            select(AudioDriftSnapshot)
            .where(AudioDriftSnapshot.user_id == user.id)
            .where(AudioDriftSnapshot.dataset_name == name)
            .order_by(AudioDriftSnapshot.id.desc())
        )
    ).all()
    return [_snapshot_out(r) for r in rows]


@router.get("/datasets/{name}/compare")
async def compare_drift(
    name: str,
    baseline_id: int,
    current_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Statistically careful drift comparison between two snapshots."""
    baseline = await db.get(AudioDriftSnapshot, baseline_id)
    current = await db.get(AudioDriftSnapshot, current_id)
    if (
        baseline is None
        or current is None
        or baseline.user_id != user.id
        or current.user_id != user.id
        or baseline.dataset_name != name
        or current.dataset_name != name
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Snapshots not found for this dataset")
    comparison = compare_snapshots(
        baseline.results or [],
        current.results or [],
        baseline_id=baseline.id,
        current_id=current.id,
    )
    return {
        "dataset": name,
        "baseline": _snapshot_out(baseline),
        "current": _snapshot_out(current),
        **comparison.to_dict(),
    }


@router.post("/quality-gate")
async def quality_gate(
    name: str,
    engine_id: str = "whisper_local",
    max_mean_wer: float | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """CI quality gate (VoxLab 2.6 wedge): evaluate the fixed dataset with the
    current engine/model, compare against the LATEST previous snapshot, and
    return an explicit pass/fail verdict suitable for pipeline blocking.

    Fail conditions (any one):
      - absolute: mean WER > max_mean_wer (when provided)
      - relative: paired-bootstrap regression vs the previous snapshot
        (CI lower bound > 0; snapshots with < MIN_PAIRS comparable cases
        never fail on the relative rule)
    Exit-code semantics: 200 = pass, 422 = gate failed (pipeline blocker).
    """
    previous = (
        await db.scalars(
            select(AudioDriftSnapshot)
            .where(AudioDriftSnapshot.user_id == user.id)
            .where(AudioDriftSnapshot.dataset_name == name)
            .order_by(AudioDriftSnapshot.id.desc())
            .limit(1)
        )
    ).first()

    snapshot = await _run_dataset(db, user, name, engine_id)

    verdict: dict[str, object] = {
        "dataset": name,
        "engine": snapshot.engine,
        "model_version": snapshot.model_version,
        "mean_wer": snapshot.mean_wer,
        "mean_cer": snapshot.mean_cer,
        "mean_rtf": snapshot.mean_rtf,
        "snapshot_id": snapshot.id,
        "checked_at": datetime.now(UTC).isoformat(),
    }

    failed = False
    reasons: list[str] = []

    if max_mean_wer is not None and snapshot.mean_wer > max_mean_wer:
        failed = True
        reasons.append(
            f"absolute: mean WER {snapshot.mean_wer:.4f} exceeds gate "
            f"{max_mean_wer:.4f}"
        )

    if previous is not None:
        comparison = compare_snapshots(
            previous.results or [],
            snapshot.results or [],
            baseline_id=previous.id,
            current_id=snapshot.id,
        )
        verdict["comparison"] = comparison.to_dict()
        if comparison.regression_detected:
            failed = True
            reasons.append(
                f"relative: paired-bootstrap regression vs snapshot "
                f"#{previous.id} (WER delta {comparison.mean_wer_delta}, "
                f"CI low {comparison.wer_ci_low})"
            )
        verdict["gate_rule_relative"] = "fail only when CI lower bound > 0"
    else:
        verdict["comparison"] = None
        verdict["note"] = "no previous snapshot: absolute rule only"

    verdict["passed"] = not failed
    verdict["reasons"] = reasons
    if failed:
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=422, content=verdict)
    return verdict
