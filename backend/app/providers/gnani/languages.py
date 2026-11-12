# languages.py
# Indic language registry and voice definitions for Gnani AI (Prisma & Timbre).
# Compliant with official Gnani documentation (https://docs.gnani.ai/).

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IndicLanguage:
    code: str  # e.g., 'hi-IN'
    name: str  # e.g., 'Hindi'
    native_name: str  # e.g., 'हिन्दी'
    script: str  # e.g., 'Devanagari'
    supports_stt: bool = True
    supports_tts: bool = True
    default_voice: str = "Nalini"
    code_switch_variant: str | None = None  # e.g., 'Hinglish'


# Official Indic language registry for Gnani AI
INDIC_LANGUAGES: dict[str, IndicLanguage] = {
    "hi-IN": IndicLanguage(
        code="hi-IN",
        name="Hindi",
        native_name="हिन्दी",
        script="Devanagari",
        supports_stt=True,
        supports_tts=True,
        default_voice="Nalini",
        code_switch_variant="Hinglish",
    ),
    "bn-IN": IndicLanguage(
        code="bn-IN",
        name="Bengali",
        native_name="বাংলা",
        script="Bengali",
        supports_stt=True,
        supports_tts=True,
        default_voice="Mehuli",
        code_switch_variant="Benglish",
    ),
    "ta-IN": IndicLanguage(
        code="ta-IN",
        name="Tamil",
        native_name="தமிழ்",
        script="Tamil",
        supports_stt=True,
        supports_tts=True,
        default_voice="Oviya",
        code_switch_variant="Tanglish",
    ),
    "te-IN": IndicLanguage(
        code="te-IN",
        name="Telugu",
        native_name="తెలుగు",
        script="Telugu",
        supports_stt=True,
        supports_tts=True,
        default_voice="Saanvi",
        code_switch_variant="Telugish",
    ),
    "kn-IN": IndicLanguage(
        code="kn-IN",
        name="Kannada",
        native_name="ಕನ್ನಡ",
        script="Kannada",
        supports_stt=True,
        supports_tts=True,
        default_voice="Radhika",
        code_switch_variant="Kanglish",
    ),
    "mr-IN": IndicLanguage(
        code="mr-IN",
        name="Marathi",
        native_name="मराठी",
        script="Devanagari",
        supports_stt=True,
        supports_tts=True,
        default_voice="Trupti",
        code_switch_variant="Marathish",
    ),
    "gu-IN": IndicLanguage(
        code="gu-IN",
        name="Gujarati",
        native_name="ગુજરાતી",
        script="Gujarati",
        supports_stt=True,
        supports_tts=True,
        default_voice="Nalini",
        code_switch_variant="Gujlish",
    ),
    "ml-IN": IndicLanguage(
        code="ml-IN",
        name="Malayalam",
        native_name="മലയാളം",
        script="Malayalam",
        supports_stt=True,
        supports_tts=True,
        default_voice="Nalini",
        code_switch_variant="Manglish",
    ),
    "or-IN": IndicLanguage(
        code="or-IN",
        name="Odia",
        native_name="ଓଡ଼ିଆ",
        script="Odia",
        supports_stt=True,
        supports_tts=True,
        default_voice="Nalini",
    ),
    "pa-IN": IndicLanguage(
        code="pa-IN",
        name="Punjabi",
        native_name="ਪੰਜਾਬੀ",
        script="Gurmukhi",
        supports_stt=True,
        supports_tts=True,
        default_voice="Nalini",
    ),
    "en-IN": IndicLanguage(
        code="en-IN",
        name="Indian English",
        native_name="English (India)",
        script="Latin",
        supports_stt=True,
        supports_tts=True,
        default_voice="Tanvi",
    ),
    "indic-auto": IndicLanguage(
        code="indic-auto",
        name="Indic Auto Detect",
        native_name="Auto Detect",
        script="Multi",
        supports_stt=True,
        supports_tts=False,
    ),
}

# Known Official Gnani Timbre v2.5 Expressive Voices
TIMBRE_VOICES = [
    {"name": "Nalini", "gender": "female", "language": "hi-IN", "style": "expressive"},
    {"name": "Vikrant", "gender": "male", "language": "hi-IN", "style": "conversational"},
    {"name": "Deepak", "gender": "male", "language": "hi-IN", "style": "authoritative"},
    {"name": "Bhavna", "gender": "female", "language": "hi-IN", "style": "friendly"},
    {"name": "Mehuli", "gender": "female", "language": "bn-IN", "style": "expressive"},
    {"name": "Oviya", "gender": "female", "language": "ta-IN", "style": "conversational"},
    {"name": "Kavin", "gender": "male", "language": "ta-IN", "style": "conversational"},
    {"name": "Saanvi", "gender": "female", "language": "te-IN", "style": "conversational"},
    {"name": "Pranav", "gender": "male", "language": "te-IN", "style": "conversational"},
    {"name": "Radhika", "gender": "female", "language": "kn-IN", "style": "conversational"},
    {"name": "Trupti", "gender": "female", "language": "mr-IN", "style": "conversational"},
    {"name": "Tanvi", "gender": "female", "language": "en-IN", "style": "expressive"},
    {"name": "Zayan", "gender": "male", "language": "en-IN", "style": "conversational"},
]


def get_indic_language(code: str) -> IndicLanguage | None:
    """Lookup IndicLanguage by ISO or normalized code."""
    if code in INDIC_LANGUAGES:
        return INDIC_LANGUAGES[code]
    # Check lowercase or short code prefix (e.g. 'hi' -> 'hi-IN')
    norm = code.lower().replace("_", "-")
    for key, lang in INDIC_LANGUAGES.items():
        if key.lower() == norm or key.split("-")[0].lower() == norm:
            return lang
    return None


def supported_stt_languages() -> list[str]:
    return [k for k, v in INDIC_LANGUAGES.items() if v.supports_stt]


def supported_tts_languages() -> list[str]:
    return [k for k, v in INDIC_LANGUAGES.items() if v.supports_tts]

