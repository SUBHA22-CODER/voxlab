# VoxLab Bugs Identified and Remediated

During the comprehensive audit, 7 architectural and functional defects were identified, analyzed, remediated, and verified with regression tests.

---

### Defect 1: Demo Account Authentication Mismatch & UI Placement (P0 - High)
* **Root Cause:** In `frontend/src/app/register/page.tsx`, `signInDemo()` was hardcoded to call `login("demo@voxlab.dev", "demo1234")`, whereas the user in the database had been hashed with `demo123`. Furthermore, the button was only rendered under `{mode === "login"}`.
* **Fix Applied:**
  1. Updated `frontend/src/app/register/page.tsx` so `signInDemo` tries `demo123` first with fallback to `demo1234`.
  2. Updated `backend/app/api/auth.py` so demo user credentials accept both `demo123` and `demo1234`.
  3. Made the "Explore with the demo account" button globally visible on `/register` without requiring the user to switch tabs first.

---

### Defect 2: Playground WebSocket Event Duplication (P1 - High)
* **Root Cause:** In `backend/app/api/playground.py` lines 177-190, the database persistence loop iterated over `for e in collector._events:` on every turn rather than the newly recorded slice `collector._events[flushed_through:]`, resulting in duplicate event rows for earlier turns.
* **Fix Applied:** Changed iteration to `for e in collector._events[flushed_through:]:` before advancing `flushed_through`, guaranteeing each event is committed exactly once.

---

### Defect 3: Delta Debugging (`ddmin`) Value-Equality Filter Bug (P1 - High)
* **Root Cause:** In `backend/app/darwin/minimizer.py`, computing chunk complements used `complement = [s for s in current_steps if s not in sub]`. For dialogues containing repeated identical step dictionaries, this filtered out all identical turns across the entire conversation rather than omitting just the targeted chunk.
* **Fix Applied:** Replaced with index-based chunk partition complement:
  ```python
  complement = [s for j, chunk in enumerate(subsets) if j != i for s in chunk]
  ```

---

### Defect 4: Hardcoded Self-Correction Strings in Diagnoser and Fitness (P1 - High)
* **Root Cause:** `diagnoser.py` and `fitness.py` evaluated self-corrections by checking specifically for strings `"tuesday"`, `"wednesday"`, and `"50"`. Real-world self-corrections with any other words were ignored.
* **Fix Applied:** Generalized self-correction detection to extract candidate superseded tokens preceding correction markers (`"no wait"`, `"scratch that"`, `"actually"`, `"wait no"`), filtering common stop words and action verbs, and verifying whether rejected tokens appear in final output.

---

### Defect 5: Missing Direct Trace Lookup Endpoint (`GET /api/traces/{trace_id}`) (P2 - Medium)
* **Root Cause:** `traces.py` only exposed `GET /api/sessions/{id}/traces`, failing direct trace UUID lookups (`GET /api/traces/{trace_id}`).
* **Fix Applied:** Added `GET /api/traces/{trace_id}` to `app/api/traces.py` returning trace data and event sequence timeline.

---

### Defect 6: Missing Report Export Endpoint (`GET /api/reports/{id}/export`) (P2 - Medium)
* **Root Cause:** `reports.py` lacked a dedicated JSON export endpoint, blocking automated CI artifact collection.
* **Fix Applied:** Added `GET /api/reports/{report_id}/export` returning structured report metrics, breakdown components, and session outcomes.

---

### Defect 7: SSRF Guard Rejected Valid WebSocket Schemes (P2 - Medium)
* **Root Cause:** `validate_endpoint` in `endpoint_guard.py` only accepted `http` and `https`, rejecting real-time WebSocket voice agents (`ws://` and `wss://`).
* **Fix Applied:** Added `ws` and `wss` to allowed schemes in `validate_endpoint`.

