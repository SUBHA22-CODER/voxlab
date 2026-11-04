# Observability, Tracing & Telemetry

> **Assumptions:**
> - Turn-level metrics and pipeline traces are captured in real time and stored for historical auditing.

---

## 1. Trace Collector & Event Architecture

Every conversational execution creates a unique `TraceCollector` instance linked to a `trace_id` (UUID4).

### Standard Event Taxonomy:
1. `session_started`: Logs persona metadata, seed, and attack strategy.
2. `turn_started`: Records user utterance, turn index, and timestamp.
3. `agent_response_received`: Captures agent text reply, tool calls, and state diffs.
4. `pipeline_timings_recorded`:
   - `stt_ms`: Speech-to-text inference latency.
   - `llm_ms`: Language model processing latency.
   - `tool_ms`: External API / tool execution latency.
   - `tts_ms`: Text-to-speech audio generation latency.
   - `e2e_ms`: Total round-trip time.
5. `session_ended`: Summarizes turn count, outcome status (`completed` / `failed`), and final fitness score.

---

## 2. Real-Time Telemetry Streaming

- **Incremental Progress Updates:** The Darwin evolution loop commits `sessions_executed` and `progress` after each individual candidate turn so frontend monitors update in real time without lag.
- **Fitness Progression Curves:** Generations are serialized into an AreaChart schema reporting:
  - `Peak Attack Fitness`: Max degradation score discovered in generation.
  - `Average Population Fitness`: Mean fitness across all population genomes.
