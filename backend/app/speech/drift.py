# drift.py
# VoxLab 2.5 Phase 6: model drift statistics.
#
# Statistical honesty contract:
# - Deltas are per-case paired differences between two snapshots over the
#   SAME fixed dataset.
# - Significance uses a paired bootstrap confidence interval on the mean
#   delta (deterministic seed for reproducibility).
# - A regression is flagged only when the CI's LOWER bound is > 0 (i.e. even
#   the optimistic end of the interval shows degradation).
# - Below MIN_PAIRS samples, significance is null with an explicit
#   "insufficient samples" note — no false regression alerts from tiny
#   differences.

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

MIN_PAIRS = 8
BOOTSTRAP_ROUNDS = 2000
BOOTSTRAP_SEED = 42
CI_LEVEL = 0.95


@dataclass
class DriftComparison:
    baseline_id: int
    current_id: int
    paired_cases: int
    mean_wer_delta: float | None
    mean_cer_delta: float | None
    mean_rtf_delta: float | None
    wer_ci_low: float | None
    wer_ci_high: float | None
    significant: bool | None  # None = insufficient samples
    regression_detected: bool
    note: str
    per_case: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_id": self.baseline_id,
            "current_id": self.current_id,
            "paired_cases": self.paired_cases,
            "deltas": {
                "wer": self.mean_wer_delta,
                "cer": self.mean_cer_delta,
                "rtf": self.mean_rtf_delta,
            },
            "wer_ci_95": [self.wer_ci_low, self.wer_ci_high],
            "significant": self.significant,
            "regression_detected": self.regression_detected,
            "note": self.note,
            "per_case": self.per_case,
        }


def compare_snapshots(
    baseline_results: list[dict[str, Any]],
    current_results: list[dict[str, Any]],
    *,
    baseline_id: int,
    current_id: int,
) -> DriftComparison:
    """Paired comparison over cases present in BOTH snapshots."""
    base_by_case = {r.get("case_id"): r for r in baseline_results}
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for current in current_results:
        case_id = current.get("case_id")
        baseline = base_by_case.get(case_id)
        if baseline is None:
            continue
        # Skip cases that errored on either side (missing metric is honest).
        if baseline.get("error") or current.get("error"):
            continue
        if baseline.get("wer") is None or current.get("wer") is None:
            continue
        pairs.append((baseline, current))

    per_case = [
        {
            "case_id": c["case_id"],
            "wer_baseline": b["wer"],
            "wer_current": c["wer"],
            "wer_delta": round(float(c["wer"]) - float(b["wer"]), 4),
            "rtf_delta": round(
                float(c.get("rtf") or 0.0) - float(b.get("rtf") or 0.0), 4
            ),
        }
        for b, c in pairs
    ]

    if not pairs:
        return DriftComparison(
            baseline_id=baseline_id,
            current_id=current_id,
            paired_cases=0,
            mean_wer_delta=None,
            mean_cer_delta=None,
            mean_rtf_delta=None,
            wer_ci_low=None,
            wer_ci_high=None,
            significant=None,
            regression_detected=False,
            note="no comparable cases between the two snapshots",
        )

    wer_base = np.array([float(b["wer"]) for b, _ in pairs], dtype=np.float64)
    wer_curr = np.array([float(c["wer"]) for _, c in pairs], dtype=np.float64)
    deltas = wer_curr - wer_base
    mean_delta = float(deltas.mean())

    cer_delta = float(
        np.mean(
            [float(c.get("cer") or 0.0) - float(b.get("cer") or 0.0) for b, c in pairs]
        )
    )
    rtf_delta = float(
        np.mean(
            [float(c.get("rtf") or 0.0) - float(b.get("rtf") or 0.0) for b, c in pairs]
        )
    )

    if len(pairs) < MIN_PAIRS:
        return DriftComparison(
            baseline_id=baseline_id,
            current_id=current_id,
            paired_cases=len(pairs),
            mean_wer_delta=round(mean_delta, 4),
            mean_cer_delta=round(cer_delta, 4),
            mean_rtf_delta=round(rtf_delta, 4),
            wer_ci_low=None,
            wer_ci_high=None,
            significant=None,
            regression_detected=False,
            note=(
                f"insufficient samples ({len(pairs)} < {MIN_PAIRS}): deltas are "
                "reported but no significance claim is made"
            ),
            per_case=per_case,
        )

    rng = np.random.default_rng(BOOTSTRAP_SEED)
    n = len(deltas)
    boot_means = np.empty(BOOTSTRAP_ROUNDS, dtype=np.float64)
    for i in range(BOOTSTRAP_ROUNDS):
        sample = deltas[rng.integers(0, n, size=n)]
        boot_means[i] = sample.mean()
    alpha = (1.0 - CI_LEVEL) / 2.0
    ci_low = float(np.quantile(boot_means, alpha))
    ci_high = float(np.quantile(boot_means, 1.0 - alpha))

    significant = bool(ci_low > 0.0 or ci_high < 0.0)
    regression = bool(ci_low > 0.0)  # degradation even at the optimistic end
    return DriftComparison(
        baseline_id=baseline_id,
        current_id=current_id,
        paired_cases=len(pairs),
        mean_wer_delta=round(mean_delta, 4),
        mean_cer_delta=round(cer_delta, 4),
        mean_rtf_delta=round(rtf_delta, 4),
        wer_ci_low=round(ci_low, 4),
        wer_ci_high=round(ci_high, 4),
        significant=significant,
        regression_detected=regression,
        note=(
            f"paired bootstrap ({BOOTSTRAP_ROUNDS} rounds, seed "
            f"{BOOTSTRAP_SEED}) {int(CI_LEVEL * 100)}% CI on mean WER delta"
        ),
        per_case=per_case,
    )
