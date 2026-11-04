# Wispr Flow Dictation Agent (Demo)

A dedicated voice-dictation pipeline target for VoxLab and Darwin fuzzing. Takes raw, spoken transcripts with human conversational flaws (self-corrections, fillers, ambiguous commands, and dialect names) and transforms them into polished text.

## Running Locally
```bash
uvicorn main:app --port 8200
```

## Failure Switches (`failure_config.json`)
- `ignore_self_corrections`: When `true`, ignores "no wait" corrections and retains superseded words.
- `strip_fillers`: When `false`, fails to clean up "um", "uh", "you know".
- `literal_period_handling`: When `true`, spells out "period" literally.
- `mangle_names`: When `true`, fails on phonetic proper nouns.

Use Darwin evolutionary fuzzing to uncover these failure modes automatically!
