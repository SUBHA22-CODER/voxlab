# genome.py
# AudioGenome: the evolvable unit of the Darwin audio engine — a persona, a
# reference to seed audio, a reference transcript, an optional chain of
# content-level text mutations (re-synthesized via offline TTS), and a
# reproducible chain of audio transformations.
#
# Reproducibility contract: genome_id is a content hash of every factor that
# affects the produced audio, so a stored artifact can be replayed exactly.
#
# Honesty contract: materialize() returns the EFFECTIVE reference transcript
# (what a perfect system would output for the produced audio). Self-correction
# insertions resolve to their replacement in the reference; the correction
# words exist only in the audio. Nothing is ever fabricated — when TTS is not
# available, content personas degrade to pure audio stress on the seed audio
# and the reference stays unchanged.

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

from app.speech.transforms import (
    TransformSpec,
    apply_chain,
    list_transforms,
)

from .personas import AudioPersona, persona_preset_for

# --- content-level mutation operators (text -> text, deterministic) ---------------

HOMOPHONES: dict[str, str] = {
    "their": "there", "there": "their",
    "to": "too", "too": "to",
    "your": "you're",
    "its": "it's",
    "write": "right", "right": "write",
    "hear": "here", "here": "hear",
    "know": "no",
    "brake": "break", "break": "brake",
    "peace": "piece", "piece": "peace",
    "weak": "week", "week": "weak",
}

# Confusable number pairs (spoken-stress classics: teens vs tens).
NUMBER_CONFUSABLES: dict[str, str] = {
    "15": "50", "50": "15",
    "16": "60", "60": "16",
    "17": "70", "70": "17",
    "18": "80", "80": "18",
    "13": "30", "30": "13",
    "19": "90", "90": "19",
}

HINGLISH_INSERTS = ("yaar", "bhai", "theek hai", "kya", "matlab")

SELF_CORRECTION_MARKERS = ("no wait", "scratch that", "sorry I meant")


def _substitute_homophones(text: str, rng: random.Random) -> tuple[str, dict]:
    tokens = text.split()
    candidates = [i for i, t in enumerate(tokens) if t.lower() in HOMOPHONES]
    if not candidates:
        return text, {"applied": False}
    idx = rng.choice(candidates)
    original = tokens[idx]
    tokens[idx] = HOMOPHONES[original.lower()]
    return " ".join(tokens), {"applied": True, "operator": "homophone_swap", "from": original, "to": tokens[idx]}


def _substitute_number(text: str, rng: random.Random) -> tuple[str, dict]:
    matches = [m for m in NUMBER_CONFUSABLES if m in text]
    if not matches:
        return text, {"applied": False}
    original = rng.choice(matches)
    replacement = NUMBER_CONFUSABLES[original]
    return text.replace(original, replacement, 1), {
        "applied": True, "operator": "number_substitution",
        "from": original, "to": replacement,
    }


def _insert_self_correction(text: str, rng: random.Random) -> tuple[str, dict]:
    """Insert 'X, no wait, Y' where the audio says a correction; the effective
    reference resolves to Y (a correct dictation system outputs Y)."""
    tokens = text.split()
    if len(tokens) < 3:
        return text, {"applied": False}
    idx = rng.randint(1, len(tokens) - 2)
    original = tokens[idx]
    marker = rng.choice(SELF_CORRECTION_MARKERS)
    replacement = original + ("s" if not original.endswith("s") else "")
    tokens[idx] = f"{original}, {marker}, {replacement}"
    audio_text = " ".join(tokens)
    # Effective reference: the corrected sentence only.
    reference = text.replace(f" {original} ", f" {replacement} ", 1) \
        if f" {original} " in f" {text} " else text
    if reference == text:
        reference = replacement.join(text.split(original, 1)) if original in text else text
    return audio_text, {
        "applied": True, "operator": "self_correction_insert",
        "marker": marker, "original": original, "resolved": replacement,
        "effective_reference": reference,
    }


def _insert_code_switch(text: str, rng: random.Random) -> tuple[str, dict]:
    words = HINGLISH_INSERTS
    insert_word = rng.choice(words)
    tokens = text.split()
    if not tokens:
        return insert_word, {"applied": True, "operator": "code_switch_insert", "inserted": insert_word, "effective_reference": insert_word}
    idx = rng.randint(0, len(tokens) - 1)
    tokens.insert(idx, insert_word)
    return " ".join(tokens), {
        "applied": True, "operator": "code_switch_insert",
        "inserted": insert_word,
        "effective_reference": " ".join(tokens),
    }


CONTENT_OPERATORS = {
    "homophone_swap": _substitute_homophones,
    "number_substitution": _substitute_number,
    "self_correction_insert": _insert_self_correction,
    "code_switch_insert": _insert_code_switch,
}


def apply_content_mutation(text: str, mutation: dict) -> tuple[str, str | None, dict]:
    """Apply one content mutation. Returns (audio_text, effective_reference,
    record). effective_reference None = unchanged text."""
    operator = str(mutation.get("operator", ""))
    fn = CONTENT_OPERATORS.get(operator)
    if fn is None:
        return text, None, {"applied": False, "error": f"unknown operator {operator}"}
    rng = random.Random(int(mutation.get("seed", 0)))
    audio_text, record = fn(text, rng)
    if not record.get("applied"):
        return text, None, record
    return audio_text, record.get("effective_reference"), record


# --- the genome ---------------------------------------------------------------------


def _genome_hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]


@dataclass
class MaterializedGenome:
    samples: np.ndarray
    sample_rate: int
    effective_reference: str
    source: str  # "seed_audio" | "tts"
    applied_chain: list[TransformSpec]
    content_records: list[dict] = field(default_factory=list)


@dataclass
class AudioGenome:
    persona_id: str
    seed_audio_ref: str
    seed_transcript: str
    seed_language: str
    transform_chain: list[TransformSpec]
    content_mutations: list[dict]
    generation: int
    parent_ids: list[str]
    seed: int
    genome_id: str = ""

    def __post_init__(self) -> None:
        if not self.genome_id:
            self.genome_id = _genome_hash(self._hash_payload())

    def _hash_payload(self) -> dict:
        return {
            "persona": self.persona_id,
            "seed_audio_ref": self.seed_audio_ref,
            "chain": [s.to_dict() for s in self.transform_chain],
            "mutations": self.content_mutations,
            "generation": self.generation,
            "seed": self.seed,
        }

    def to_dict(self) -> dict:
        return {
            "persona_id": self.persona_id,
            "seed_audio_ref": self.seed_audio_ref,
            "seed_transcript": self.seed_transcript,
            "seed_language": self.seed_language,
            "transform_chain": [s.to_dict() for s in self.transform_chain],
            "content_mutations": self.content_mutations,
            "generation": self.generation,
            "parent_ids": self.parent_ids,
            "seed": self.seed,
            "genome_id": self.genome_id,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> AudioGenome:
        return cls(
            persona_id=payload["persona_id"],
            seed_audio_ref=payload["seed_audio_ref"],
            seed_transcript=payload.get("seed_transcript", ""),
            seed_language=payload.get("seed_language", "en"),
            transform_chain=[TransformSpec.from_dict(s) for s in payload.get("transform_chain", [])],
            content_mutations=list(payload.get("content_mutations", [])),
            generation=int(payload.get("generation", 0)),
            parent_ids=list(payload.get("parent_ids", [])),
            seed=int(payload.get("seed", 0)),
            genome_id=payload.get("genome_id", ""),
        )

    # -- materialization ---------------------------------------------------

    async def materialize(
        self,
        seed_audio: np.ndarray | None,
        sample_rate: int,
        tts_synth: Callable[[str], object] | None = None,
    ) -> MaterializedGenome:
        """Produce the actual candidate audio.

        tts_synth: async callable (text) -> np.ndarray float32 mono @
        sample_rate. When None (or the persona has no content mutations), the
        seed audio is transformed directly and the reference is unchanged.
        """
        audio = seed_audio
        reference = self.seed_transcript
        content_records: list[dict] = []
        source = "seed_audio"

        if self.content_mutations and self.seed_transcript and tts_synth is not None:
            mutated_text = self.seed_transcript
            for mutation in self.content_mutations:
                mutated_text, _effective_ref, record = apply_content_mutation(mutated_text, mutation)
                content_records.append(record)
            try:
                audio = await tts_synth(mutated_text)
                if audio is not None and len(audio) > 0:
                    source = "tts"
                    for record in content_records:
                        if record.get("effective_reference"):
                            reference = record["effective_reference"]
            except Exception:  # noqa: BLE001 - degrade to seed-audio stress
                # TTS failure degrades honestly to seed-audio stress; the
                # records keep the failure visible for diagnosis.
                content_records.append({"applied": False, "error": "tts_synth_failed"})

        if audio is None or audio.size == 0:
            raise ValueError("materialize() requires seed audio when TTS is unavailable.")

        samples = apply_chain(np.asarray(audio, dtype=np.float32), sample_rate, self.transform_chain)
        return MaterializedGenome(
            samples=samples.astype(np.float32),
            sample_rate=sample_rate,
            effective_reference=reference,
            source=source,
            applied_chain=list(self.transform_chain),
            content_records=content_records,
        )


# --- construction / evolution helpers -------------------------------------------------


_RANDOM_POOL = ("add_background_noise", "add_typing_clicks", "dropout_spans",
                "add_echo", "fade_edges", "volume_pump")


def build_random_genome(
    *,
    persona: AudioPersona,
    seed_audio_ref: str,
    reference_text: str,
    seed: int,
    generation: int,
    language: str = "en",
) -> AudioGenome:
    """Deterministic genome from (persona, seed). Same inputs -> same genome."""
    rng = random.Random(seed)
    chain = persona_preset_for(persona, seed)

    if not persona.is_content_persona and rng.random() < 0.35:
        # Diversify: occasionally add one extra stressor from the pool.
        operator = rng.choice(_RANDOM_POOL)
        extra_seed = rng.randint(0, 2**31 - 1)
        chain.append(_default_spec(operator, extra_seed))

    content_mutations: list[dict] = []
    if persona.is_content_persona:
        operator = {
            "multilingual_speaker": "code_switch_insert",
            "self_correcting_speaker": "self_correction_insert",
            "ambiguous_number_speaker": "number_substitution",
            "homophone_speaker": "homophone_swap",
        }.get(persona.id, "homophone_swap")
        content_mutations.append({"operator": operator, "seed": rng.randint(0, 2**31 - 1)})

    return AudioGenome(
        persona_id=persona.id,
        seed_audio_ref=seed_audio_ref,
        seed_transcript=reference_text,
        seed_language=language,
        transform_chain=chain,
        content_mutations=content_mutations,
        generation=generation,
        parent_ids=[],
        seed=seed,
    )


def _default_spec(operator: str, seed: int) -> TransformSpec:
    """Neutral-magnitude spec for pooled operators (within registry bounds)."""
    defaults: dict[str, dict[str, float | int | str]] = {
        "add_background_noise": {"snr_db": 14.0, "noise_type": "pink"},
        "add_typing_clicks": {"click_count": 6, "snr_db": 12.0},
        "dropout_spans": {"count": 1, "duration_ms": 120.0},
        "add_echo": {"delay_ms": 120.0, "decay": 0.2},
        "fade_edges": {"fade_ms": 100.0},
        "volume_pump": {"rate_hz": 3.0, "depth": 0.3},
    }
    return TransformSpec(operator=operator, params=dict(defaults[operator]), seed=seed)


def mutate_genome(parent: AudioGenome, mutation_seed: int) -> AudioGenome:
    """Create a child by one random mutation, fully reproducible."""
    rng = random.Random(mutation_seed)
    chain = [TransformSpec(operator=s.operator, params=dict(s.params), seed=s.seed)
             for s in parent.transform_chain]
    mutations = [dict(m) for m in parent.content_mutations]

    strategy = rng.choice(["append", "perturb", "reseed", "remove", "reroll_content"])
    if strategy == "append" or not chain:
        chain.append(_default_spec(rng.choice(_RANDOM_POOL), rng.randint(0, 2**31 - 1)))
    elif strategy == "perturb" and chain:
        idx = rng.randrange(len(chain))
        spec = chain[idx]
        params = dict(spec.params)
        numeric = [k for k, v in params.items() if isinstance(v, (int, float)) and not isinstance(v, bool)]
        if numeric:
            key = rng.choice(numeric)
            factor = rng.uniform(0.7, 1.4)
            params[key] = type(params[key])(max(0.05, float(params[key]) * factor))
        chain[idx] = TransformSpec(operator=spec.operator, params=params, seed=spec.seed)
    elif strategy == "reseed" and chain:
        idx = rng.randrange(len(chain))
        spec = chain[idx]
        chain[idx] = TransformSpec(operator=spec.operator, params=dict(spec.params),
                                   seed=rng.randint(0, 2**31 - 1))
    elif strategy == "remove" and len(chain) > 1:
        chain.pop(rng.randrange(len(chain)))
    elif mutations:
        rng.shuffle(mutations)
        for m in mutations:
            m["seed"] = rng.randint(0, 2**31 - 1)

    return AudioGenome(
        persona_id=parent.persona_id,
        seed_audio_ref=parent.seed_audio_ref,
        seed_transcript=parent.seed_transcript,
        seed_language=parent.seed_language,
        transform_chain=chain,
        content_mutations=mutations,
        generation=parent.generation + 1,
        parent_ids=[parent.genome_id],
        seed=mutation_seed,
    )


def crossover_genomes(parent_a: AudioGenome, parent_b: AudioGenome, seed: int) -> AudioGenome:
    """Splice A's leading chain with B's trailing chain (text-Darwin style)."""
    rng = random.Random(seed)
    cut_a = rng.randint(0, len(parent_a.transform_chain))
    cut_b = rng.randint(0, len(parent_b.transform_chain))
    chain = parent_a.transform_chain[:cut_a] + parent_b.transform_chain[cut_b:]
    persona = parent_a.persona_id if cut_a >= cut_b else parent_b.persona_id
    return AudioGenome(
        persona_id=persona,
        seed_audio_ref=parent_a.seed_audio_ref,
        seed_transcript=parent_a.seed_transcript,
        seed_language=parent_a.seed_language,
        transform_chain=chain,
        content_mutations=list(parent_a.content_mutations or parent_b.content_mutations),
        generation=max(parent_a.generation, parent_b.generation) + 1,
        parent_ids=[parent_a.genome_id, parent_b.genome_id],
        seed=seed,
    )


def transform_catalog() -> list[dict[str, object]]:
    """Expose the registry catalog (re-exported for the API layer)."""
    return list_transforms()
