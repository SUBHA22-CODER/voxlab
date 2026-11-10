# transforms.py
# Reproducible audio attack transformations — the mutation substrate of the
# Darwin audio evolution engine.
#
# Rules every transform follows (product contract):
# - Deterministic: same (samples, seed, params) -> bit-identical output.
#   Randomness comes exclusively from a per-apply numpy Generator.
# - Self-describing: parameters are bounded, recorded, and serializable, so a
#   failing artifact can be replayed byte-for-byte.
# - Non-destructive to provenance: transforms never modify the input array in
#   place; they return a new array.
# - Validity-preserving: transforms must not destroy intelligibility entirely;
#   the fitness layer additionally gates adversarial candidates on audibility
#   (see darwin_audio/fitness.py) so meaningless noise is never rewarded.

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

from .exceptions import TransformError

TARGET_SAMPLE_RATE = 16_000


def _rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed)


# --- noise generators -----------------------------------------------------------


def _white_noise(rng: np.random.Generator, n: int) -> np.ndarray:
    return rng.standard_normal(n).astype(np.float32)


def _pink_noise(rng: np.random.Generator, n: int) -> np.ndarray:
    """1/f noise via FFT shaping of white noise (TF Paul Kellet approximation
    is time-domain; the FFT method is equivalent and dependency-free)."""
    white = rng.standard_normal(n)
    spectrum = np.fft.rfft(white)
    freqs = np.fft.rfftfreq(n, d=1.0 / TARGET_SAMPLE_RATE)
    shaping = np.ones_like(freqs)
    nonzero = freqs > 0
    shaping[nonzero] = 1.0 / np.sqrt(np.maximum(freqs[nonzero], 1.0))
    pink = np.fft.irfft(spectrum * shaping, n=n)
    std = float(np.std(pink))
    if std > 1e-12:
        pink = pink / std
    return pink.astype(np.float32)


def _snr_gain(samples: np.ndarray, noise: np.ndarray, snr_db: float) -> np.ndarray:
    """Scale noise so signal/noise power ratio equals snr_db."""
    sig_power = float(np.mean(np.square(samples, dtype=np.float64))) + 1e-12
    noise_power = float(np.mean(np.square(noise, dtype=np.float64))) + 1e-12
    target_noise_power = sig_power / (10.0 ** (snr_db / 10.0))
    return noise * math.sqrt(target_noise_power / noise_power)


# --- transform definitions --------------------------------------------------------


@dataclass(frozen=True)
class TransformSpec:
    """One serialization-ready transformation step.

    `operator` names a registered factory; `params` are bounded kwargs; `seed`
    makes the step fully reproducible.
    """

    operator: str
    params: dict[str, float | int | str] = field(default_factory=dict)
    seed: int = 0

    def to_dict(self) -> dict[str, object]:
        return {"operator": self.operator, "params": dict(self.params), "seed": self.seed}

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> TransformSpec:
        operator = str(payload.get("operator", ""))
        if not operator:
            raise TransformError("TransformSpec requires an operator name.")
        params = dict(payload.get("params") or {})
        return cls(operator=operator, params=params, seed=int(payload.get("seed", 0)))


TransformFn = Callable[[np.ndarray, int, np.random.Generator, dict[str, float | int | str]], np.ndarray]

_REGISTRY: dict[str, tuple[TransformFn, dict[str, tuple[type, float | int | str, float | int | str]]]] = {}


def register_transform(
    name: str, bounds: dict[str, tuple[type, object, object]] | None = None
) -> Callable[[TransformFn], TransformFn]:
    """Register a transform operator with parameter bounds (min, max).

    Bounds are enforced on every apply so recorded artifacts can never carry
    out-of-range parameters.
    """

    def decorator(fn: TransformFn) -> TransformFn:
        _REGISTRY[name] = (fn, bounds or {})
        return fn

    return decorator


def apply_transform(samples: np.ndarray, sample_rate: int, spec: TransformSpec) -> np.ndarray:
    entry = _REGISTRY.get(spec.operator)
    if entry is None:
        raise TransformError(f"Unknown transform operator: '{spec.operator}'.")
    fn, bounds = entry
    params = dict(spec.params)
    for key, (_expected_type, low, high) in bounds.items():
        if key not in params:
            continue  # defaults are applied inside the operator
        value = params[key]
        numeric = isinstance(value, (int, float)) and not isinstance(value, bool)
        if isinstance(value, str) and not isinstance(low, str):
            raise TransformError(f"Parameter '{key}' must be numeric.")
        if numeric and isinstance(low, (int, float)) and not (low <= value <= high):
            raise TransformError(
                f"Parameter '{key}'={value} outside bounds [{low}, {high}]."
            )
    return fn(np.asarray(samples, dtype=np.float32), int(sample_rate), _rng(spec.seed), params)


def apply_chain(
    samples: np.ndarray, sample_rate: int, chain: list[TransformSpec]
) -> np.ndarray:
    """Apply transformations in order; source audio is never mutated."""
    out = np.asarray(samples, dtype=np.float32)
    for spec in chain:
        out = apply_transform(out, sample_rate, spec)
    return out


# --- concrete operators --------------------------------------------------------------


@register_transform(
    "add_background_noise",
    bounds={"snr_db": (float, 0.0, 40.0)},
)
def _add_background_noise(
    samples: np.ndarray, sr: int, rng: np.random.Generator, params: dict
) -> np.ndarray:
    """Additive white or pink ("fan-like") noise at a target SNR.

    snr_db=40 is nearly inaudible, snr_db=0 is as loud as the speech.
    """
    snr_db = float(params.get("snr_db", 12.0))
    noise_type = str(params.get("noise_type", "pink"))
    generator = _white_noise(rng, samples.size) if noise_type == "white" else _pink_noise(rng, samples.size)
    return samples + _snr_gain(samples, generator, snr_db)


@register_transform(
    "add_typing_clicks",
    bounds={"click_count": (int, 1, 60), "snr_db": (float, 0.0, 40.0)},
)
def _add_typing_clicks(
    samples: np.ndarray, sr: int, rng: np.random.Generator, params: dict
) -> np.ndarray:
    """Keyboard-like clicks: exponentially decaying broadband bursts."""
    click_count = int(params.get("click_count", 8))
    snr_db = float(params.get("snr_db", 10.0))
    clicks = np.zeros(samples.size, dtype=np.float32)
    click_len = max(2, int(0.012 * sr))
    decay_env = np.exp(-np.linspace(0.0, 9.0, click_len)).astype(np.float32)
    for _ in range(click_count):
        start = int(rng.integers(0, max(1, samples.size - click_len)))
        burst = _white_noise(rng, click_len) * decay_env
        clicks[start : start + click_len] += burst
    return samples + _snr_gain(samples, clicks, snr_db)


@register_transform(
    "add_fan_hum",
    bounds={"gain_db": (float, -30.0, -3.0), "frequency_hz": (float, 40.0, 400.0)},
)
def _add_fan_hum(
    samples: np.ndarray, sr: int, rng: np.random.Generator, params: dict
) -> np.ndarray:
    """Low-frequency fan/HVAC hum: fundamental + harmonic + slow AM wobble."""
    gain_db = float(params.get("gain_db", -18.0))
    frequency_hz = float(params.get("frequency_hz", 120.0))
    t = np.arange(samples.size, dtype=np.float64) / sr
    wobble = 1.0 + 0.05 * np.sin(2 * np.pi * 0.7 * t)
    hum = (
        np.sin(2 * np.pi * frequency_hz * t)
        + 0.4 * np.sin(2 * np.pi * 2 * frequency_hz * t)
    ) * wobble
    hum = hum.astype(np.float32)
    gain = 10.0 ** (gain_db / 20.0)
    return samples + gain * hum * float(np.sqrt(np.mean(np.square(samples, dtype=np.float64))) + 1e-9)


@register_transform(
    "change_volume",
    bounds={"gain_db": (float, -30.0, 10.0)},
)
def _change_volume(
    samples: np.ndarray, sr: int, rng: np.random.Generator, params: dict
) -> np.ndarray:
    """Linear gain. Negative = quiet speaker, positive = hot/loud signal."""
    gain = 10.0 ** (float(params.get("gain_db", -6.0)) / 20.0)
    return np.clip(samples * gain, -1.0, 1.0)


@register_transform(
    "clip_speech",
    bounds={"clip_level": (float, 0.05, 0.95)},
)
def _clip_speech(
    samples: np.ndarray, sr: int, rng: np.random.Generator, params: dict
) -> np.ndarray:
    """Hard amplitude clipping (overdriven mic / too-hot preamp)."""
    level = float(params.get("clip_level", 0.4))
    return np.clip(samples, -level, level) / max(level, 1e-6)


@register_transform(
    "insert_silence",
    bounds={"duration_s": (float, 0.05, 3.0)},
)
def _insert_silence(
    samples: np.ndarray, sr: int, rng: np.random.Generator, params: dict
) -> np.ndarray:
    """Insert a dead-air gap at the start, middle, or end of the clip
    (mid-sentence pauses / barge-in dead zones)."""
    duration_s = float(params.get("duration_s", 0.3))
    position = str(params.get("position", "middle"))
    gap = np.zeros(int(duration_s * sr), dtype=np.float32)
    if position == "start":
        return np.concatenate([gap, samples])
    if position == "end":
        return np.concatenate([samples, gap])
    middle = samples.size // 2
    return np.concatenate([samples[:middle], gap, samples[middle:]])


@register_transform(
    "dropout_spans",
    bounds={"count": (int, 1, 20), "duration_ms": (float, 10.0, 800.0)},
)
def _dropout_spans(
    samples: np.ndarray, sr: int, rng: np.random.Generator, params: dict
) -> np.ndarray:
    """Momentary signal loss (wireless mic dropouts / network hiccups)."""
    count = int(params.get("count", 2))
    duration_ms = float(params.get("duration_ms", 150.0))
    out = samples.copy()
    span = max(2, int(duration_ms / 1000.0 * sr))
    for _ in range(count):
        start = int(rng.integers(0, max(1, samples.size - span)))
        out[start : start + span] = 0.0
    return out


@register_transform(
    "tape_speed_change",
    bounds={"rate": (float, 0.5, 2.5)},
)
def _tape_speed_change(
    samples: np.ndarray, sr: int, rng: np.random.Generator, params: dict
) -> np.ndarray:
    """Tape-style speed change: rate > 1 = faster AND higher pitch (an honest
    combined effect, like a tape deck). Linear interpolation resampling."""
    rate = float(params.get("rate", 1.3))
    new_size = max(2, round(samples.size / rate))
    positions = np.linspace(0.0, samples.size - 1, num=new_size)
    return np.interp(positions, np.arange(samples.size), samples).astype(np.float32)


@register_transform(
    "pitch_shift",
    bounds={"semitones": (float, -6.0, 6.0)},
)
def _pitch_shift(
    samples: np.ndarray, sr: int, rng: np.random.Generator, params: dict
) -> np.ndarray:
    """Pitch shift at constant duration: resample by the pitch ratio, then
    linearly interpolate back to the original length (basic but real)."""
    semitones = float(params.get("semitones", 2.0))
    ratio = 2.0 ** (semitones / 12.0)
    stretched_size = max(2, round(samples.size * ratio))
    positions = np.linspace(0.0, samples.size - 1, num=stretched_size)
    stretched = np.interp(positions, np.arange(samples.size), samples)
    back_positions = np.linspace(0.0, stretched_size - 1, num=samples.size)
    return np.interp(back_positions, np.arange(stretched_size), stretched).astype(np.float32)


def _fft_filter(samples: np.ndarray, sr: int, low_hz: float, high_hz: float) -> np.ndarray:
    """Zero-phase brickwall-ish band filter with soft edges (raised cosine)."""
    spectrum = np.fft.rfft(samples)
    freqs = np.fft.rfftfreq(samples.size, d=1.0 / sr)
    gain = np.ones_like(freqs)
    width = max(1.0, 0.1 * (high_hz - low_hz))
    gain[freqs < low_hz] = 0.0
    ramp = (freqs >= low_hz) & (freqs < low_hz + width)
    gain[ramp] = 0.5 - 0.5 * np.cos(np.pi * (freqs[ramp] - low_hz) / width)
    gain[freqs > high_hz] = 0.0
    ramp_hi = (freqs <= high_hz) & (freqs > high_hz - width)
    gain[ramp_hi] = np.minimum(gain[ramp_hi], 0.5 + 0.5 * np.cos(np.pi * (freqs[ramp_hi] - (high_hz - width)) / width))
    return np.fft.irfft(spectrum * gain, n=samples.size).astype(np.float32)


@register_transform(
    "telephony_bandpass",
    bounds={"low_hz": (float, 100.0, 600.0), "high_hz": (float, 2000.0, 6000.0)},
)
def _telephony_bandpass(
    samples: np.ndarray, sr: int, rng: np.random.Generator, params: dict
) -> np.ndarray:
    """Narrow telephone band (300-3400 Hz default): kills sibilance and lows."""
    low_hz = float(params.get("low_hz", 300.0))
    high_hz = float(params.get("high_hz", 3400.0))
    return _fft_filter(samples, sr, low_hz, high_hz)


@register_transform(
    "lowpass_muffle",
    bounds={"cutoff_hz": (float, 500.0, 6000.0)},
)
def _lowpass_muffle(
    samples: np.ndarray, sr: int, rng: np.random.Generator, params: dict
) -> np.ndarray:
    """Muffled/obstructed mic: everything above the cutoff removed."""
    cutoff_hz = float(params.get("cutoff_hz", 2000.0))
    return _fft_filter(samples, sr, 10.0, cutoff_hz)


@register_transform(
    "add_echo",
    bounds={"delay_ms": (float, 40.0, 800.0), "decay": (float, 0.05, 0.9)},
)
def _add_echo(
    samples: np.ndarray, sr: int, rng: np.random.Generator, params: dict
) -> np.ndarray:
    """Single-tap echo/room reverb approximation."""
    delay_ms = float(params.get("delay_ms", 150.0))
    decay = float(params.get("decay", 0.35))
    delay = max(1, int(delay_ms / 1000.0 * sr))
    out = samples.copy()
    if delay < samples.size:
        out[delay:] += decay * samples[: samples.size - delay]
    return np.clip(out, -1.0, 1.0)


@register_transform(
    "fade_edges",
    bounds={"fade_ms": (float, 10.0, 2000.0)},
)
def _fade_edges(
    samples: np.ndarray, sr: int, rng: np.random.Generator, params: dict
) -> np.ndarray:
    """Cosine fades on both edges (clipped word onsets / cut-off endings)."""
    fade_ms = float(params.get("fade_ms", 150.0))
    fade = min(max(1, int(fade_ms / 1000.0 * sr)), samples.size // 2)
    out = samples.copy()
    ramp = 0.5 - 0.5 * np.cos(np.pi * np.arange(fade) / fade)
    out[:fade] *= ramp
    out[-fade:] *= ramp[::-1]
    return out


@register_transform(
    "volume_pump",
    bounds={"rate_hz": (float, 0.5, 12.0), "depth": (float, 0.05, 0.9)},
)
def _volume_pump(
    samples: np.ndarray, sr: int, rng: np.random.Generator, params: dict
) -> np.ndarray:
    """AGC-style volume pumping: periodic gain modulation."""
    rate_hz = float(params.get("rate_hz", 4.0))
    depth = float(params.get("depth", 0.4))
    t = np.arange(samples.size, dtype=np.float64) / sr
    modulation = 1.0 - depth * 0.5 * (1.0 - np.cos(2 * np.pi * rate_hz * t))
    return np.clip(samples * modulation.astype(np.float32), -1.0, 1.0)


def list_transforms() -> list[dict[str, object]]:
    """Catalog of every registered operator and its parameter bounds (for the
    API and docs — the UI can render exact controls from this)."""
    catalog: list[dict[str, object]] = []
    for name, (_fn, bounds) in sorted(_REGISTRY.items()):
        catalog.append(
            {
                "operator": name,
                "params": {
                    key: {"type": typ.__name__, "min": low, "max": high}
                    for key, (typ, low, high) in bounds.items()
                },
            }
        )
    return catalog
