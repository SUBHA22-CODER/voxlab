# test_analytics.py
# VoxLab 2.5 Phases 5+6: robustness aggregation and drift detection.
# Offline: stub engine for snapshot runs; deterministic statistics tests.

from __future__ import annotations

import io
import json
import wave
from pathlib import Path

import numpy as np
import pytest

from app.speech.drift import MIN_PAIRS, compare_snapshots


def _finding_metrics(wer: float) -> dict:
    return {"ground_truth": {"wer": wer}}


def _chain(*specs: tuple[str, dict]) -> list[dict]:
    return [{"operator": op, "params": params, "seed": 1} for op, params in specs]


class TestRobustnessAggregation:
    @pytest.mark.asyncio
    async def test_buckets_come_from_real_chain_params(self, client, auth_headers, db_session, user):
        from app.darwin_audio.artifacts import AudioArtifactStore  # noqa: F401
        from app.models.darwin_audio import AudioFinding, DarwinAudioRun

        run = DarwinAudioRun(user_id=user.id, status="completed", config={}, stats={}, progress=100)
        db_session.add(run)
        await db_session.flush()

        rows = [
            # loud noise + fast speech finding
            AudioFinding(
                run_id=run.id, persona_id="noisy_environment_speaker",
                genome={"transform_chain": _chain(
                    ("add_background_noise", {"snr_db": 6.0}),
                    ("tape_speed_change", {"rate": 1.4}),
                )},
                genome_hash="a1", fitness=0.5,
                metrics=_finding_metrics(0.6), reproduction={"engine": "whisper_local", "model": "tiny"},
            ),
            # quiet noise finding
            AudioFinding(
                run_id=run.id, persona_id="low_volume_speaker",
                genome={"transform_chain": _chain(("add_background_noise", {"snr_db": 25.0}))},
                genome_hash="a2", fitness=0.3,
                metrics=_finding_metrics(0.2), reproduction={"engine": "whisper_local", "model": "tiny"},
            ),
        ]
        db_session.add_all(rows)
        await db_session.commit()

        response = await client.get("/api/v1/analytics/robustness", headers=auth_headers)
        assert response.status_code == 200
        body = response.json()
        assert body["total_findings"] == 2
        # noise buckets from the actual snr_db parameters
        assert body["by_noise_level"]["loud_noise"]["mean_wer"] == 0.6
        assert body["by_noise_level"]["quiet_noise"]["mean_wer"] == 0.2
        # speed bucket from the actual rate parameter
        assert body["by_speaking_speed"]["fast"]["count"] == 1
        # persona aggregation
        assert body["by_persona"]["noisy_environment_speaker"]["mean_wer"] == 0.6
        # untested conditions are absent, never fabricated
        assert "long" not in body.get("by_duration", {}) or body["by_duration"].get("long") is None

    @pytest.mark.asyncio
    async def test_engine_filter(self, client, auth_headers, db_session, user):
        from app.models.darwin_audio import AudioFinding, DarwinAudioRun

        run = DarwinAudioRun(user_id=user.id, status="completed", config={}, stats={}, progress=100)
        db_session.add(run)
        await db_session.flush()
        db_session.add(
            AudioFinding(
                run_id=run.id, persona_id="x", genome={"transform_chain": []},
                genome_hash="b1", fitness=0.1,
                metrics=_finding_metrics(0.9), reproduction={"engine": "vosk", "model": "small"},
            )
        )
        await db_session.commit()

        response = await client.get(
            "/api/v1/analytics/robustness?engine=whisper_local", headers=auth_headers
        )
        assert response.json()["total_findings"] == 0
        response2 = await client.get("/api/v1/analytics/robustness?engine=vosk", headers=auth_headers)
        assert response2.json()["total_findings"] == 1


class TestDriftStatistics:
    def _results(self, wers: list[float | None]) -> list[dict]:
        return [
            {"case_id": f"case-{i:02d}", "wer": w, "cer": (w or 0) * 0.8,
             "rtf": 0.5, "hypothesis": "x", "error": None}
            for i, w in enumerate(wers)
        ]

    def test_no_regression_on_identical_snapshots(self):
        results = self._results([0.2] * 12)
        comparison = compare_snapshots(results, results, baseline_id=1, current_id=2)
        assert comparison.mean_wer_delta == 0.0
        assert comparison.regression_detected is False
        assert comparison.significant is False

    def test_insufficient_samples_claim_nothing(self):
        baseline = self._results([0.1] * (MIN_PAIRS - 1))
        current = self._results([0.5] * (MIN_PAIRS - 1))
        comparison = compare_snapshots(baseline, current, baseline_id=1, current_id=2)
        assert comparison.significant is None
        assert comparison.regression_detected is False
        assert "insufficient" in comparison.note

    def test_real_regression_detected_with_ci(self):
        baseline = self._results([0.15] * 12)
        # consistent degradation on every case: CI lower bound will be > 0
        current = self._results([0.45] * 12)
        comparison = compare_snapshots(baseline, current, baseline_id=1, current_id=2)
        assert comparison.mean_wer_delta == pytest.approx(0.3, abs=1e-6)
        assert comparison.significant is True
        assert comparison.regression_detected is True
        assert comparison.wer_ci_low is not None and comparison.wer_ci_low > 0

    def test_noisy_small_change_not_flagged(self):
        rng = np.random.default_rng(7)
        baseline = self._results(list(rng.normal(0.2, 0.08, 20).clip(0, 1)))
        # +0.01 mean shift well inside noise: CI should straddle zero
        current = self._results(list((rng.normal(0.2, 0.08, 20) + 0.01).clip(0, 1)))
        comparison = compare_snapshots(baseline, current, baseline_id=1, current_id=2)
        assert comparison.regression_detected is False

    def test_errored_cases_are_excluded_from_pairs(self):
        baseline = self._results([0.1] * 12)
        baseline[0]["error"] = "decode failure"
        current = self._results([0.1] * 12)
        comparison = compare_snapshots(baseline, current, baseline_id=1, current_id=2)
        assert comparison.paired_cases == 11  # 12 cases minus the errored one

    def test_comparison_is_deterministic(self):
        rng = np.random.default_rng(3)
        baseline = self._results(list(rng.normal(0.2, 0.05, 15).clip(0, 1)))
        current = self._results(list((rng.normal(0.26, 0.05, 15)).clip(0, 1)))
        c1 = compare_snapshots(baseline, current, baseline_id=1, current_id=2)
        c2 = compare_snapshots(baseline, current, baseline_id=1, current_id=2)
        assert c1.wer_ci_low == c2.wer_ci_low  # fixed bootstrap seed


@pytest.mark.asyncio
class TestDriftAPI:
    async def _seed_dataset(self, user_id: int) -> Path:
        from app.core.config import get_settings

        directory = Path(get_settings().audio_storage_dir) / "benchmarks" / "test-ds"
        directory.mkdir(parents=True, exist_ok=True)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            t = np.arange(3200) / 16000
            w.writeframes((0.3 * np.sin(2 * np.pi * 300 * t) * 32767).astype("<i2").tobytes())
        (directory / "case-01.wav").write_bytes(buf.getvalue())
        manifest = {
            "name": "test-ds",
            "cases": [{"id": "case-01", "text": "hello world", "wav": "case-01.wav", "language": "en"}],
        }
        (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return directory

    async def test_snapshot_and_compare_flow(self, client, auth_headers, monkeypatch):
        await self._seed_dataset(1)

        from tests.test_api_v1_audio import StubAPIEngine

        async def fake_get_engine(engine_id: str = "whisper_local"):
            return StubAPIEngine()

        import app.api.v1.analytics as analytics_mod

        monkeypatch.setattr(analytics_mod, "get_engine", fake_get_engine)

        created = await client.post(
            "/api/v1/analytics/datasets/test-ds/snapshot?engine_id=stub", headers=auth_headers
        )
        assert created.status_code == 201
        body = created.json()
        assert body["case_count"] == 1
        assert body["model_version"] == "stub-model"

        listed = await client.get("/api/v1/analytics/datasets/test-ds/snapshots", headers=auth_headers)
        assert listed.status_code == 200
        snapshots = listed.json()
        assert len(snapshots) == 1

        compare = await client.get(
            f"/api/v1/analytics/datasets/test-ds/compare?baseline_id={snapshots[0]['id']}&current_id={snapshots[0]['id']}",
            headers=auth_headers,
        )
        assert compare.status_code == 200
        assert compare.json()["regression_detected"] is False

    async def test_missing_dataset_404(self, client, auth_headers):
        response = await client.post(
            "/api/v1/analytics/datasets/never-built/snapshot", headers=auth_headers
        )
        assert response.status_code == 404


@pytest.mark.asyncio
class TestQualityGate:
    @staticmethod
    def _tone_wav(seconds: float = 0.5) -> bytes:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            t = np.arange(int(seconds * 16000)) / 16000
            w.writeframes((0.3 * np.sin(2 * np.pi * 300 * t) * 32767).astype("<i2").tobytes())
        return buf.getvalue()

    async def _seed_and_snapshot(self, client, auth_headers, monkeypatch, wers: list[float]):
        from tests.test_api_v1_audio import StubAPIEngine

        async def fake_get_engine(engine_id: str = "whisper_local"):
            engine = StubAPIEngine()
            engine._qa_wers = wers
            return engine

        import app.api.v1.analytics as analytics_mod
        monkeypatch.setattr(analytics_mod, "get_engine", fake_get_engine)

        # stub transcribe returns fixed text; override metrics by seeding results
        response = await client.post(
            "/api/v1/analytics/datasets/human-voices-v1/snapshot?engine_id=stub",
            headers=auth_headers,
        )
        return response

    async def test_gate_passes_when_no_regression(self, client, auth_headers, monkeypatch):
        await self._seed_and_snapshot(client, auth_headers, monkeypatch, [0.1] * 4)
        response = await client.post(
            "/api/v1/analytics/quality-gate?name=human-voices-v1&engine_id=stub",
            headers=auth_headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["passed"] is True
        # setup snapshot exists -> comparison present with zero delta
        assert body["comparison"]["deltas"]["wer"] == 0.0

    async def test_gate_fails_absolute_threshold(self, client, auth_headers, monkeypatch):
        await self._seed_and_snapshot(client, auth_headers, monkeypatch, [0.1] * 4)
        response = await client.post(
            "/api/v1/analytics/quality-gate?name=human-voices-v1&engine_id=stub&max_mean_wer=0.05",
            headers=auth_headers,
        )
        assert response.status_code == 422  # pipeline-blocker semantics
        body = response.json()
        assert body["passed"] is False
        assert any("absolute" in r for r in body["reasons"])

    async def test_first_snapshot_never_fails_relative_rule(self, client, auth_headers, monkeypatch):
        # fresh dataset with no previous snapshot: absolute rule only
        from app.core.config import get_settings
        import json as _json
        directory = Path(get_settings().audio_storage_dir) / "benchmarks" / "gate-ds"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "case-01.wav").write_bytes(self._tone_wav(0.5))
        (directory / "manifest.json").write_text(_json.dumps(
            {"name": "gate-ds", "cases": [{"id": "c1", "text": "hello world", "wav": "case-01.wav"}]}
        ), encoding="utf-8")

        from tests.test_api_v1_audio import StubAPIEngine

        async def fake_get_engine(engine_id: str = "whisper_local"):
            return StubAPIEngine()

        import app.api.v1.analytics as analytics_mod
        monkeypatch.setattr(analytics_mod, "get_engine", fake_get_engine)

        response = await client.post(
            "/api/v1/analytics/quality-gate?name=gate-ds&engine_id=stub&max_mean_wer=0.9",
            headers=auth_headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["comparison"] is None
        assert body["passed"] is True
