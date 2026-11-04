# Automated Regression Library Integration

## Exporting Findings to CI

A critical failure mode of AI teams is fixing a prompt or model only to have the same bug reappear two weeks later.

VoxLab solves this by making every Darwin defect exportable as a standardized CI regression scenario:

### 1. One-Click UI Export
On any discovered finding card in `/darwin/{run_id}`:
- Click **"Export to Regression Suite"**.
- Calls `POST /api/darwin/findings/{id}/export`.

### 2. File Generation
In `backend/app/darwin/regression.py`, the finding is converted to a version-controlled JSON scenario in `scenarios/regression/`:

```json
{
  "name": "Regression - self_correction_missed - 9a905b2e",
  "description": "Auto-exported from Darwin finding #4. Category: self_correction_missed",
  "category": "regression",
  "turns": [
    {
      "user_utterance": "Schedule a call for Tuesday, no wait, Wednesday at 2pm.",
      "expected_output_substrings": ["Wednesday at 2pm"],
      "forbidden_output_substrings": ["Tuesday"]
    }
  ]
}
```

### 3. CI Gate
These scenarios execute automatically in GitHub Actions CI (`pytest backend/tests/test_darwin_integration.py`), failing the PR build if the agent ever regresses.

