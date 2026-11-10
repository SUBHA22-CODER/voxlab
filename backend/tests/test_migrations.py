# test_migrations.py
# VoxLab 2.5 Phase 7: Alembic migration integrity. Runs the real migration
# chain against a throwaway SQLite database and verifies the round trip.

from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
EXPECTED_TABLES = [
    "users",
    "agents",
    "scenarios",
    "test_runs",
    "sessions",
    "events",
    "traces",
    "evaluations",
    "reports",
    "darwin_runs",
    "darwin_generations",
    "darwin_findings",
    "darwin_audio_runs",
    "darwin_audio_generations",
    "darwin_audio_findings",
    "audio_regression_cases",
    "audio_benchmarks",
    "audio_drift_snapshots",
    "revoked_tokens",
    "audit_events",
]


def _alembic(db_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    import os

    env = dict(os.environ)
    env["ALEMBIC_URL"] = f"sqlite+aiosqlite:///{db_path.as_posix()}"
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def _tables(db_path: Path) -> list[str]:
    conn = sqlite3.connect(db_path)
    try:
        return [
            r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            if not r[0].startswith("sqlite")
        ]
    finally:
        conn.close()


@pytest.fixture
def mig_db(tmp_path: Path) -> Path:
    return tmp_path / "mig.db"


class TestMigrations:
    def test_upgrade_creates_full_schema(self, mig_db: Path):
        result = _alembic(mig_db, "upgrade", "head")
        assert result.returncode == 0, result.stderr
        tables = _tables(mig_db)
        missing = [t for t in EXPECTED_TABLES if t not in tables]
        assert not missing, f"migration is missing tables: {missing}"

    def test_downgrade_rolls_back_user_tables(self, mig_db: Path):
        assert _alembic(mig_db, "upgrade", "head").returncode == 0
        result = _alembic(mig_db, "downgrade", "base")
        assert result.returncode == 0, result.stderr
        tables = _tables(mig_db)
        # alembic_version legitimately persists; every user table must go
        leftovers = [t for t in tables if t != "alembic_version"]
        assert not leftovers, f"downgrade left user tables behind: {leftovers}"

    def test_upgrade_is_idempotent_at_head(self, mig_db: Path):
        assert _alembic(mig_db, "upgrade", "head").returncode == 0
        result = _alembic(mig_db, "upgrade", "head")
        assert result.returncode == 0, result.stderr

    def test_migration_models_match_create_all(self, mig_db: Path):
        """The migration must not drift from the ORM models: tables created
        by alembic must equal tables created by create_all."""
        assert _alembic(mig_db, "upgrade", "head").returncode == 0
        migrated = set(_tables(mig_db))

        import asyncio

        from app.core.database import Base
        import app.models  # noqa: F401

        async def _create():
            from sqlalchemy.ext.asyncio import create_async_engine

            engine = create_async_engine(f"sqlite+aiosqlite:///{mig_db.with_suffix('.orm.db')}")
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            await engine.dispose()

        asyncio.run(_create())
        orm_tables = set(_tables(mig_db.with_suffix(".orm.db")))
        missing_in_migration = orm_tables - migrated - {"alembic_version"}
        assert not missing_in_migration, (
            f"ORM tables missing from migrations (run `alembic revision "
            f"--autogenerate`): {missing_in_migration}"
        )
