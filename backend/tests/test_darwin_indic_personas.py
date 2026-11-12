# test_darwin_indic_personas.py
# Verification of the 12 new Indic and code-switching Darwin personas.

from __future__ import annotations

from app.darwin.personas import PERSONAS, get_active_personas, get_persona

REQUIRED_INDIC_PERSONAS = [
    "hinglish_switcher",
    "benglish_speaker",
    "tanglish_speaker",
    "regional_accent_tester",
    "background_noise_injector",
    "fast_speech_persona",
    "slow_speech_persona",
    "self_correction_persona",
    "filler_word_persona",
    "proper_noun_confuser",
    "number_confuser",
    "codeswitch_mutation",
]


def test_all_12_indic_personas_registered() -> None:
    for persona_id in REQUIRED_INDIC_PERSONAS:
        assert persona_id in PERSONAS, f"Missing required persona: {persona_id}"
        persona = get_persona(persona_id)
        assert persona.id == persona_id
        assert len(persona.name) > 0
        assert len(persona.description) > 0
        assert len(persona.system_prompt) > 0
        assert len(persona.strategies) >= 1
        assert len(persona.heuristic_bank) >= 2


def test_indic_personas_are_active_and_not_stubs() -> None:
    active_ids = {p.id for p in get_active_personas()}
    for persona_id in REQUIRED_INDIC_PERSONAS:
        assert persona_id in active_ids, f"Persona {persona_id} should be active, not a stub"


def test_hinglish_heuristic_bank_contains_code_switching() -> None:
    persona = get_persona("hinglish_switcher")
    assert any("refund" in h or "order" in h for h in persona.heuristic_bank)
    assert any("karo" in h or "chahiye" in h for h in persona.heuristic_bank)


def test_number_confuser_contains_lakh_or_crore() -> None:
    persona = get_persona("number_confuser")
    assert any("lakh" in h.lower() or "crore" in h.lower() for h in persona.heuristic_bank)

