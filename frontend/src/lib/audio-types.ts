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

export interface TranscriptionResult {
  engine: string;
  text: string;
  language: string | null;
  language_probability: number | null;
  segments: TranscriptSegment[];
  duration_seconds: number;
  processing_time_seconds: number;
  metadata: Record<string, unknown>;
  metrics: TranscriptMetricsReport | null;
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
