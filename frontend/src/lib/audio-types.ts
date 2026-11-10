/**
 * VoxLab 2.0 audio API types — mirrors backend/app/schemas/audio.py.
 */

export interface EngineCapabilities {
  languages: string[] | null;
  supports_timestamps: boolean;
  supports_language_detection: boolean;
  streaming_mode: "none" | "chunked_window" | "true";
  max_audio_duration_seconds: number | null;
}

export interface EngineInfo {
  engine_id: string;
  installed: boolean;
  capabilities?: Record<string, unknown> | null;
  attribution?: string | null;
  install_hint?: string | null;
}

export interface EngineHealth {
  engine_id: string;
  status: "healthy" | "degraded" | "unavailable";
  detail: string;
  model_loaded: boolean;
}

export interface TranscriptSegment {
  start_seconds: number;
  end_seconds: number;
  text: string;
}

export interface TranscriptMetricsReport {
  ground_truth: {
    wer: number;
    wer_detail: {
      substitutions: number;
      deletions: number;
      insertions: number;
      reference_words: number;
    };
    cer: number;
    punctuation_accuracy: number | null;
    number_accuracy: number | null;
    entity_accuracy: number | null;
    technical_vocab_accuracy: number | null;
    language_correct: boolean | null;
    timestamp_alignment_error_seconds: number | null;
    realtime_factor: number | null;
    processing_latency_seconds: number | null;
  };
  heuristic: {
    semantic_overlap_proxy: number | null;
  };
  normalization: Record<string, boolean>;
  definitions: Record<string, string>;
}

export interface WordTimingPoint {
  word_index: number;
  start_seconds: number;
  end_seconds: number;
  confidence: number | null;
}

export interface AlignedTokenView {
  operation: "correct" | "substitution" | "insertion" | "deletion" | string;
  ref_index: number | null;
  hyp_index: number | null;
  ref_word: string | null;
  hyp_word: string | null;
  severity: string | null;
  start_seconds: number | null;
  end_seconds: number | null;
  confidence: number | null;
  explanation: string | null;
}

export interface AlignmentView {
  tokens: AlignedTokenView[];
  counts: {
    reference_words: number;
    hypothesis_words: number;
    correct: number;
    substitutions: number;
    insertions: number;
    deletions: number;
  };
}

export interface SemanticErrorView {
  type: string;
  severity: string;
  description: string;
  reference: string | null;
  hypothesis: string | null;
  ref_index: number | null;
  hyp_index: number | null;
}

export interface SemanticAnalysisView {
  meaning_preserved: boolean;
  error_count: number;
  errors: SemanticErrorView[];
}

export interface LLMJudgmentView {
  layer: "llm";
  available: boolean;
  meaning_preserved: boolean | null;
  confidence: number | null;
  errors: Array<Record<string, unknown>>;
  provenance: Record<string, unknown>;
}

export interface TranscriptionResult {
  engine: string;
  text: string;
  language: string | null;
  language_probability: number | null;
  segments: TranscriptSegment[];
  duration_seconds: number;
  processing_time_seconds: number;
  metadata: Record<string, unknown>;
  word_timings: WordTimingPoint[];
  metrics: TranscriptMetricsReport | null;
  alignment: AlignmentView | null;
  semantic: SemanticAnalysisView | null;
  llm_judgment: LLMJudgmentView | null;
}

// --- analytics (Phases 5+6) ---

export interface BucketStat { count: number; mean_wer: number | null; }

export interface RobustnessReport {
  total_findings: number;
  filters: Record<string, string | null>;
  by_persona: Record<string, BucketStat>;
  by_noise_level: Record<string, BucketStat>;
  by_speaking_speed: Record<string, BucketStat>;
  by_duration: Record<string, BucketStat>;
  note: string;
}

export interface DatasetInfo { name: string; case_count: number; description: string; }

export interface DriftSnapshotView {
  id: number;
  dataset_name: string;
  engine: string;
  model_version: string;
  case_count: number;
  mean_wer: number;
  mean_cer: number;
  mean_rtf: number;
  created_at: string;
}

export interface DriftComparisonView {
  dataset: string;
  baseline: DriftSnapshotView;
  current: DriftSnapshotView;
  paired_cases: number;
  deltas: { wer: number | null; cer: number | null; rtf: number | null };
  wer_ci_95: [number | null, number | null];
  significant: boolean | null;
  regression_detected: boolean;
  note: string;
  per_case: Array<{ case_id: string; wer_baseline: number; wer_current: number; wer_delta: number }>;
}

export interface SecurityAuditEvent {
  id: number;
  event_type: string;
  detail: Record<string, unknown>;
  source_ip: string | null;
  created_at: string;
}

export interface SecurityHealth {
  status: string;
  checked_at: string;
  database: { reachable: boolean; revoked_tokens: number };
  auth: {
    token_type: string;
    revocation: string;
    demo_bypass_removed: boolean;
    rate_limit_rules: Array<{ path: string; window_seconds: number; max_requests: number }>;
  };
  retention: { audio_retention_days: number; storage_dir: string };
  engines: Array<{ engine_id: string; installed: boolean }>;
  own_audit_events: number;
}

export interface AudioPersona {
  id: string;
  name: string;
  description: string;
  is_content_persona: boolean;
  is_dictation_focused: boolean;
  preset_operators: string[];
}

export interface TransformSpec {
  operator: string;
  params: Record<string, number | string>;
  seed: number;
}

export interface TransformCatalogEntry {
  operator: string;
  params: Record<string, { type: string; min: number | string; max: number | string }>;
}

export interface DarwinAudioRun {
  id: number;
  status: string;
  config: Record<string, unknown>;
  stats: Record<string, unknown>;
  progress: number;
  error: string | null;
  created_at: string;
}

export interface DarwinAudioFinding {
  id: number;
  run_id: number;
  persona_id: string;
  genome: Record<string, unknown>;
  original_chain_length: number;
  minimized_chain_length: number;
  minimized_genome: Record<string, unknown> | null;
  fitness: number;
  metrics: TranscriptMetricsReport;
  audio_artifact_ref: string;
  reference_transcript: string;
  failed_transcript: string;
  reproduction: Record<string, unknown>;
  created_at: string;
}

export interface AudioRegressionCase {
  id: number;
  test_id: string;
  engine: string;
  model_version: string;
  language: string;
  severity: "low" | "medium" | "high" | "critical" | string;
  failure_category: string;
  seed_audio_ref: string;
  chain: TransformSpec[];
  seed: number;
  reference_transcript: string;
  expected_behavior: string;
  metrics: TranscriptMetricsReport;
  tags: string[];
  last_run: {
    status: string;
    wer: number;
    cer: number;
    hypothesis: string;
    engine: string;
    model: string | null;
    at: string;
  } | null;
  created_at: string;
}

export interface AudioRegressionReplay {
  test_id: string;
  status: "fixed" | "improved" | "still_failing" | "error";
  wer: number | null;
  cer: number | null;
  hypothesis: string;
  detail: string;
}

export interface BenchmarkEngineResult {
  engine: string;
  status: "ok" | "error" | "not_installed";
  model?: string | null;
  text?: string;
  language?: string | null;
  processing_time_seconds?: number;
  metrics?: TranscriptMetricsReport;
  error?: string;
}

export interface AudioBenchmark {
  id: number;
  label: string;
  engine_results: BenchmarkEngineResult[];
  audio_duration_seconds: number;
  reference_transcript: string;
  audio_ref: string;
  created_at: string;
}
