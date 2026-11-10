"""Darwin Regression Suite — Exports minimized failure cases to repeatable scenarios."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Scenario
from app.models.darwin import DarwinFinding
from app.seed import find_scenarios_dir

logger = logging.getLogger(__name__)


def compute_regression_hash(category: str, steps: list[dict[str, Any]]) -> str:
    normalized = []
    for s in steps:
        normalized.append({
            "type": s.get("type", "user_message"),
            "content": s.get("content", "").strip().lower(),
        })
    raw = f"{category}:{json.dumps(normalized, sort_keys=True)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:8]


async def export_finding_to_regression(
    finding: DarwinFinding,
    db: AsyncSession | None = None,
    output_dir: Path | None = None,
) -> tuple[Path, int | None]:
    """
    Exports a Darwin finding to scenarios/regression/<category>-<hash>.json
    and registers it in the Scenario table.

    output_dir: test override — writing into the real scenarios tree from a
    test would corrupt tracked regression fixtures.
    """
    if output_dir is not None:
        regression_dir = Path(output_dir)
    else:
        scenarios_dir = find_scenarios_dir()
        if scenarios_dir is None:
            raise RuntimeError("Scenarios directory could not be located")
        regression_dir = scenarios_dir / "regression"
    regression_dir.mkdir(parents=True, exist_ok=True)

    diag = finding.diagnosis or {}
    category = diag.get("category") or finding.persona
    steps = finding.minimized_steps or finding.genome.get("steps", [])

    short_hash = compute_regression_hash(category, steps)
    filename = f"{category}-{short_hash}.json"
    file_path = regression_dir / filename

    scenario_data = {
        "name": f"Darwin Regression: {category} ({short_hash})",
        "category": "regression",
        "description": (
            f"Automated regression reproduction discovered by Darwin for persona '{finding.persona}'. "
            f"Diagnosis: {diag.get('summary', 'Failure')}"
        ),
        "steps": steps,
        "expected_behavior": (
            f"Agent must not exhibit {category} defect: "
            f"{diag.get('summary', 'must handle without failing')}."
        ),
        "latency_budget_ms": 6000,
        "checks": [
            {"type": "reply_nonempty", "turn": -1},
        ],
        "metadata": {
            "source": "darwin",
            "run_id": finding.run_id,
            "persona": finding.persona,
            "diagnosis": diag,
            "original_steps_count": finding.original_steps_count,
            "minimized_steps_count": finding.minimized_steps_count,
            "fitness": finding.fitness,
            "created_at": datetime.now(UTC).isoformat(),
        },
    }

    file_path.write_text(json.dumps(scenario_data, indent=2), encoding="utf-8")
    logger.info("Exported Darwin regression finding to %s", file_path)

    scenario_id: int | None = None
    if db is not None:
        # Check if already exists in DB
        existing = await db.scalar(
            select(Scenario).where(Scenario.name == scenario_data["name"])
        )
        if existing:
            existing.definition = scenario_data
            existing.category = "regression"
            scenario_id = existing.id
        else:
            new_scen = Scenario(
                name=scenario_data["name"],
                category="regression",
                definition=scenario_data,
                is_builtin=False,
            )
            db.add(new_scen)
            await db.flush()
            scenario_id = new_scen.id

        finding.exported_scenario_id = scenario_id
        await db.commit()

    return file_path, scenario_id
