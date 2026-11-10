# semantic_llm.py
# VoxLab 2.5 Phase 3 — the LLM-BASED semantic judgment layer.
#
# Hard contract (master spec): an LLM judgment is NEVER ground truth. Every
# judgment object records its full provenance:
#   - model identifier (from the configured LLMService)
#   - prompt version (SEMANTIC_JUDGE_PROMPT_VERSION)
#   - evaluation timestamp (UTC)
#   - the exact input (reference + hypothesis) and raw model output
#   - confidence when the model provides one; otherwise null (never guessed)
#   - reproducibility info (temperature=0, JSON mode, prompt hash)
#
# The judge runs ONLY when an LLM key is configured; without one it reports
# available=False and callers must rely on the deterministic layer.

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.services.llm import LLMService

logger = logging.getLogger(__name__)

SEMANTIC_JUDGE_PROMPT_VERSION = "v1"

SEMANTIC_JUDGE_PROMPT = """You are a strict speech-transcription reviewer.
Compare the REFERENCE transcript (ground truth) with the RECOGNIZED
transcript produced by a speech engine. Identify only meaning-relevant
differences: changed quantities, changed dates, negations flips, entity or
terminology substitutions, missing or added instructions, and intent changes.
Do NOT penalize punctuation, casing, filler words, or harmless morphology.

REFERENCE:
{reference}

RECOGNIZED:
{hypothesis}

Reply with STRICT JSON only:
{{
  "meaning_preserved": true|false,
  "confidence": <0.0-1.0 or null if unsure>,
  "errors": [
    {{"type": "number_error|date_error|negation_error|entity_error|terminology_error|missing_instruction|intent_change|other",
       "description": "<one sentence>",
       "reference_text": "<fragment or null>",
       "hypothesis_text": "<fragment or null>"}}
  ]
}}"""


@dataclass
class LLMSemanticJudgment:
    """One LLM semantic verdict with complete provenance. `layer` is always
    "llm" so it can never be confused with the deterministic layer."""

    available: bool
    meaning_preserved: bool | None = None
    confidence: float | None = None
    errors: list[dict[str, Any]] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "layer": "llm",
            "available": self.available,
            "meaning_preserved": self.meaning_preserved,
            "confidence": self.confidence,
            "errors": self.errors,
            "provenance": self.provenance,
        }


async def judge_semantics_with_llm(
    llm: LLMService,
    reference: str,
    hypothesis: str,
) -> LLMSemanticJudgment:
    """One judgment call. Deterministic settings (temperature 0); the raw
    output is preserved verbatim for reproducibility."""
    if not llm.available:
        return LLMSemanticJudgment(available=False, provenance={"reason": "no_llm_key"})

    prompt = SEMANTIC_JUDGE_PROMPT.format(reference=reference, hypothesis=hypothesis)
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]
    started = datetime.now(UTC).isoformat()

    raw = await llm.complete(
        [
            {"role": "system", "content": "You output only valid JSON. Never add commentary."},
            {"role": "user", "content": prompt},
        ],
        json_mode=True,
        temperature=0.0,  # deterministic settings for reproducibility
        max_tokens=700,
    )
    finished = datetime.now(UTC).isoformat()

    provenance: dict[str, Any] = {
        "model": llm.model if hasattr(llm, "model") else None,
        "prompt_version": SEMANTIC_JUDGE_PROMPT_VERSION,
        "prompt_hash": prompt_hash,
        "temperature": 0.0,
        "evaluated_at": started,
        "completed_at": finished,
        "input_reference": reference,
        "input_hypothesis": hypothesis,
        "raw_output": raw,
        "note": "LLM judgment is advisory; the deterministic layer is ground truth",
    }

    if raw is None:
        provenance["parse_status"] = "model_unavailable_or_invalid_json"
        return LLMSemanticJudgment(available=True, provenance=provenance)

    # complete_json may return a dict already or a JSON-looking string.
    try:
        data = raw if isinstance(raw, dict) else json.loads(str(raw))
    except json.JSONDecodeError:
        provenance["parse_status"] = "invalid_json"
        return LLMSemanticJudgment(available=True, provenance=provenance)

    provenance["parse_status"] = "ok"
    confidence = data.get("confidence")
    if isinstance(confidence, (int, float)) and 0.0 <= float(confidence) <= 1.0:
        confidence_value: float | None = float(confidence)
    else:
        confidence_value = None  # absent/out-of-range: null, never guessed

    return LLMSemanticJudgment(
        available=True,
        meaning_preserved=bool(data.get("meaning_preserved", False)),
        confidence=confidence_value,
        errors=list(data.get("errors") or []),
        provenance=provenance,
    )
