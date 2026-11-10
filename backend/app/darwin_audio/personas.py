# personas.py
# Audio attack personas for the Darwin audio engine. Each persona bundles a
# preset chain of seeded audio transformations; "content" personas additionally
# mutate the seed transcript and re-synthesize audio when offline TTS is
# available (Windows SAPI — a default synthetic voice, never a real-person
# clone). Existing text-Darwin personas are untouched: these are additive.

from __future__ import annotations

from dataclasses import dataclass

from app.speech.transforms import TransformSpec

# Deterministic per-genome offsets are added to every preset seed by the
# evolution engine, so two genomes from the same persona never collide.


@dataclass(frozen=True)
class AudioPersona:
    id: str
    name: str
    description: str
    # audio transformation presets; param factories receive the genome seed
    preset: tuple[TransformSpec, ...] = ()
    # content personas rewrite the transcript and re-synthesize (TTS needed)
    is_content_persona: bool = False
    is_dictation_focused: bool = False


def _spec(operator: str, seed: int, **params: object) -> TransformSpec:
    return TransformSpec(operator=operator, params=params, seed=seed)


NOISY_ENVIRONMENT_SPEAKER = AudioPersona(
    id="noisy_environment_speaker",
    name="Noisy Environment Speaker",
    description="Office/cafeteria ambience: broadband noise, fan hum, typing.",
    preset=(
        _spec("add_background_noise", 101, snr_db=10.0, noise_type="pink"),
        _spec("add_fan_hum", 102, gain_db=-16.0, frequency_hz=120.0),
        _spec("add_typing_clicks", 103, click_count=10, snr_db=8.0),
    ),
    is_dictation_focused=True,
)

FAST_TECHNICAL_SPEAKER = AudioPersona(
    id="fast_technical_speaker",
    name="Fast Technical Speaker",
    description="Rapid speech over a narrow channel — stresses technical terms.",
    preset=(
        _spec("tape_speed_change", 201, rate=1.35),
        _spec("telephony_bandpass", 202, low_hz=300.0, high_hz=3400.0),
    ),
    is_dictation_focused=True,
)

LOW_VOLUME_SPEAKER = AudioPersona(
    id="low_volume_speaker",
    name="Low-Volume Speaker",
    description="Quiet speech with a soft noise floor (far-field mic).",
    preset=(
        _spec("change_volume", 301, gain_db=-14.0),
        _spec("add_background_noise", 302, snr_db=18.0, noise_type="pink"),
    ),
    is_dictation_focused=True,
)

INTERRUPTED_SPEAKER = AudioPersona(
    id="interrupted_speaker",
    name="Interrupted Speaker",
    description="Barge-ins and dead air: dropouts and mid-clip silence.",
    preset=(
        _spec("dropout_spans", 401, count=2, duration_ms=200.0),
        _spec("insert_silence", 402, duration_s=0.4, position="middle"),
    ),
    is_dictation_focused=True,
)

DOMAIN_CHANNEL_SPEAKER = AudioPersona(
    id="domain_channel_speaker",
    name="Domain Speaker on Harsh Channel",
    description="Domain vocabulary over a muffled, band-limited channel.",
    preset=(
        _spec("lowpass_muffle", 501, cutoff_hz=2600.0),
        _spec("add_echo", 502, delay_ms=120.0, decay=0.25),
    ),
)

MUMBLING_UNCLEAR_SPEAKER = AudioPersona(
    id="mumbling_unclear_speaker",
    name="Mumbling Unclear Speaker",
    description="Pumped volume, dark tone, clipped edges — articulation stress.",
    preset=(
        _spec("volume_pump", 601, rate_hz=3.0, depth=0.5),
        _spec("lowpass_muffle", 602, cutoff_hz=1800.0),
        _spec("fade_edges", 603, fade_ms=120.0),
    ),
)

# Content personas: mutate the transcript, then re-synthesize via offline TTS.
# When TTS is unavailable they are skipped honestly (recorded in run stats).

MULTILINGUAL_SPEAKER = AudioPersona(
    id="multilingual_speaker",
    name="Multilingual Speaker",
    description="Code-switched transcript (content-level; TTS re-synthesis).",
    is_content_persona=True,
    is_dictation_focused=True,
)

SELF_CORRECTING_SPEAKER = AudioPersona(
    id="self_correcting_speaker",
    name="Self-Correcting Speaker",
    description="Injects spoken self-corrections into the transcript (TTS).",
    is_content_persona=True,
    is_dictation_focused=True,
)

AMBIGUOUS_NUMBER_SPEAKER = AudioPersona(
    id="ambiguous_number_speaker",
    name="Ambiguous Number Speaker",
    description="Rewrites numbers to confusable forms: 15/50, 42/forty two (TTS).",
    is_content_persona=True,
    is_dictation_focused=True,
)

HOMOPHONE_SPEAKER = AudioPersona(
    id="homophone_speaker",
    name="Homophone Speaker",
    description="Swaps homophones (their/there, to/too) in the transcript (TTS).",
    is_content_persona=True,
    is_dictation_focused=True,
)

AUDIO_PERSONAS: dict[str, AudioPersona] = {
    p.id: p
    for p in (
        NOISY_ENVIRONMENT_SPEAKER,
        FAST_TECHNICAL_SPEAKER,
        LOW_VOLUME_SPEAKER,
        INTERRUPTED_SPEAKER,
        DOMAIN_CHANNEL_SPEAKER,
        MUMBLING_UNCLEAR_SPEAKER,
        MULTILINGUAL_SPEAKER,
        SELF_CORRECTING_SPEAKER,
        AMBIGUOUS_NUMBER_SPEAKER,
        HOMOPHONE_SPEAKER,
    )
}

DEFAULT_AUDIO_PERSONAS = [
    "noisy_environment_speaker",
    "fast_technical_speaker",
    "low_volume_speaker",
    "interrupted_speaker",
    "self_correcting_speaker",
    "homophone_speaker",
]


def get_audio_personas(ids: list[str] | None) -> list[AudioPersona]:
    """Resolve persona ids to definitions; None/empty = default set."""
    if not ids:
        return [AUDIO_PERSONAS[pid] for pid in DEFAULT_AUDIO_PERSONAS]
    unknown = [pid for pid in ids if pid not in AUDIO_PERSONAS]
    if unknown:
        raise KeyError(f"Unknown audio persona(s): {unknown}")
    return [AUDIO_PERSONAS[pid] for pid in ids]


def persona_preset_for(persona: AudioPersona, genome_seed: int) -> list[TransformSpec]:
    """Clone the persona preset with seeds offset by the genome seed so every
    genome is reproducible yet distinct."""
    offset = genome_seed & 0xFFFF
    return [
        TransformSpec(operator=s.operator, params=dict(s.params), seed=s.seed + offset)
        for s in persona.preset
    ]
