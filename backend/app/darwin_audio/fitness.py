# fitness.py
# Audio-candidate fitness for the Darwin audio engine.
#
# Definitions (documented per the product rule — no hidden metric mixing):
#
#   failure_score = 0.45 * min(WER, 1)            # word errors (saturating)
#                 + 0.15 * min(CER, 1)            # character errors
#                 + 0.15 * (1 - number_accuracy)  # N/A counts as no signal (0)
#                 + 0.10 * (1 - entity_accuracy)  # N/A counts as no signal (0)
#                 + 0.15 * (1 - semantic_overlap) # heuristic proxy component
#
#   All components live in [0, 1]; failure_score therefore lies in [0, 1].
#   Higher failure_score = the engine performed WORSE = stronger adversarial
#   candidate (mirrors the text-Darwin fitness convention).
#
# Validity gates (anti-noise-reward — a candidate is only rewarded when it is
# still a legitimate test, not meaningless destruction):
#   audible:            RMS >= 0.004 (~ -48 dBFS)
#   duration_preserved: candidate duration within [0.4x, 3.0x] of the seed
#   Invalid candidates get rewarded_score = 0.0 and are never selected.

from __future__ import annotations

from dataclasses import dataclass, field

AUDIO_FITNESS_WEIGHTS: dict[str, float] = {
    "wer": 0.45,
    "cer": 0.15,
    "number": 0.15,
    "entity": 0.10,
    "semantic": 0.15,
}

MIN_AUDIBLE_RMS = 0.004
MIN_DURATION_RATIO = 0.4
MAX_DURATION_RATIO = 3.0


@dataclass
class AudioFitness:
    failure_score: float
    rewarded_score: float
    valid: bool
    gates: dict[str, bool] = field(default_factory=dict)
    components: dict[str, float] = field(default_factory=dict)


def compute_audio_fitness(
    *,
    wer: float,
    cer: float,
    number_accuracy: float | None,
    entity_accuracy: float | None,
    semantic_overlap: float,
    audio_rms: float,
    seed_duration: float,
    candidate_duration: float,
) -> AudioFitness:
    """Score one evaluated candidate. Pure function — trivially testable."""
    audible = audio_rms >= MIN_AUDIBLE_RMS
    ratio = (candidate_duration / seed_duration) if seed_duration > 0 else 0.0
    duration_preserved = MIN_DURATION_RATIO <= ratio <= MAX_DURATION_RATIO

    wer_norm = min(max(wer, 0.0), 1.0)
    cer_norm = min(max(cer, 0.0), 1.0)
    number_fail = 0.0 if number_accuracy is None else 1.0 - min(max(number_accuracy, 0.0), 1.0)
    entity_fail = 0.0 if entity_accuracy is None else 1.0 - min(max(entity_accuracy, 0.0), 1.0)
    semantic_fail = 1.0 - min(max(semantic_overlap, 0.0), 1.0)

    failure_score = (
        AUDIO_FITNESS_WEIGHTS["wer"] * wer_norm
        + AUDIO_FITNESS_WEIGHTS["cer"] * cer_norm
        + AUDIO_FITNESS_WEIGHTS["number"] * number_fail
        + AUDIO_FITNESS_WEIGHTS["entity"] * entity_fail
        + AUDIO_FITNESS_WEIGHTS["semantic"] * semantic_fail
    )

    valid = audible and duration_preserved
    return AudioFitness(
        failure_score=round(failure_score, 6),
        rewarded_score=round(failure_score, 6) if valid else 0.0,
        valid=valid,
        gates={"audible": audible, "duration_preserved": duration_preserved},
        components={
            "wer_normalized": wer_norm,
            "cer_normalized": cer_norm,
            "number_failure": round(number_fail, 6),
            "entity_failure": round(entity_fail, 6),
            "semantic_failure": round(semantic_fail, 6),
            "duration_ratio": round(ratio, 4),
            "audio_rms": round(audio_rms, 6),
        },
    )
