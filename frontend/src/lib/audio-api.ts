/**
 * Typed client for the VoxLab 2.0 v1 audio APIs.
 * Multipart uploads use fetch directly (no manual Content-Type: the browser
 * must set the multipart boundary itself).
 */

import { API_URL, ApiError, getToken } from "./api";
import type {
  AudioBenchmark,
  DatasetInfo,
  DriftComparisonView,
  DriftSnapshotView,
  RobustnessReport,
  SecurityAuditEvent,
  SecurityHealth,
  AudioPersona,
  AudioRegressionCase,
  AudioRegressionReplay,
  BenchmarkEngineResult,
  DarwinAudioFinding,
  DarwinAudioRun,
  EngineHealth,
  EngineInfo,
  TransformCatalogEntry,
  TranscriptionResult,
} from "./audio-types";

async function apiForm<T>(path: string, form: FormData): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const response = await fetch(`${API_URL}${path}`, { method: "POST", body: form, headers });
  if (response.status === 401 && typeof window !== "undefined") {
    setTokenNull();
    window.location.href = "/register";
    throw new ApiError("Session expired", 401);
  }
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      /* keep statusText */
    }
    throw new ApiError(detail, response.status);
  }
  return (await response.json()) as T;
}

function setTokenNull(): void {
  // Local re-implementation to avoid a circular import with api.ts.
  try {
    window.localStorage.removeItem("voxlab_token");
  } catch {
    /* storage unavailable */
  }
}

export const AudioEngines = {
  list: () => fetchJson<EngineInfo[]>("/api/v1/engines"),
  health: (engineId: string) => fetchJson<EngineHealth>(`/api/v1/engines/${engineId}/health`),
};

export const AudioTranscribe = {
  transcribe: (params: {
    file: File;
    engineId: string;
    language?: string;
    referenceTranscript?: string;
    entities?: string;
    technicalVocab?: string;
  }) => {
    const form = new FormData();
    form.append("file", params.file);
    form.append("engine_id", params.engineId);
    if (params.language) form.append("language", params.language);
    if (params.referenceTranscript) form.append("reference_transcript", params.referenceTranscript);
    if (params.entities) form.append("entities", params.entities);
    if (params.technicalVocab) form.append("technical_vocab", params.technicalVocab);
    return apiForm<TranscriptionResult>("/api/v1/audio/transcribe", form);
  },
};

export const DarwinAudio = {
  personas: () => fetchJson<AudioPersona[]>("/api/v1/darwin/audio/personas"),
  transforms: () => fetchJson<TransformCatalogEntry[]>("/api/v1/darwin/audio/transforms"),
  evolve: (params: {
    file: File;
    referenceTranscript: string;
    engineId: string;
    language: string;
    populationSize: number;
    generations: number;
    topK: number;
    seed: number;
    failureThreshold: number;
    personas: string[];
    entities?: string;
    technicalVocab?: string;
  }) => {
    const form = new FormData();
    form.append("file", params.file);
    form.append("reference_transcript", params.referenceTranscript);
    form.append("engine_id", params.engineId);
    form.append("language", params.language);
    form.append("population_size", String(params.populationSize));
    form.append("generations", String(params.generations));
    form.append("top_k", String(params.topK));
    form.append("seed", String(params.seed));
    form.append("failure_threshold", String(params.failureThreshold));
    if (params.personas.length) form.append("personas", params.personas.join(","));
    if (params.entities) form.append("entities", params.entities);
    if (params.technicalVocab) form.append("technical_vocab", params.technicalVocab);
    return apiForm<DarwinAudioRun>("/api/v1/darwin/audio/evolve", form);
  },
  listRuns: () => fetchJson<DarwinAudioRun[]>("/api/v1/darwin/audio/runs"),
  getRun: (id: number) => fetchJson<DarwinAudioRun>(`/api/v1/darwin/audio/runs/${id}`),
  cancelRun: (id: number) =>
    fetchJson<DarwinAudioRun>(`/api/v1/darwin/audio/runs/${id}/cancel`, { method: "POST" }),
  findings: (runId: number) =>
    fetchJson<DarwinAudioFinding[]>(`/api/v1/darwin/audio/runs/${runId}/findings`),
};

export const Regressions = {
  list: () => fetchJson<AudioRegressionCase[]>("/api/v1/regressions"),
  promoteFromFinding: (findingId: number) =>
    fetchJson<AudioRegressionCase>(`/api/v1/regressions/from-finding/${findingId}`, {
      method: "POST",
    }),
  replay: (caseId: number) =>
    fetchJson<AudioRegressionReplay>(`/api/v1/regressions/${caseId}/run`, { method: "POST" }),
  remove: (caseId: number) => fetchJson<void>(`/api/v1/regressions/${caseId}`, { method: "DELETE" }),
};

export const Benchmarks = {
  run: (params: {
    file: File;
    engines: string;
    referenceTranscript?: string;
    label?: string;
  }) => {
    const form = new FormData();
    form.append("file", params.file);
    form.append("engines", params.engines);
    if (params.referenceTranscript) form.append("reference_transcript", params.referenceTranscript);
    if (params.label) form.append("label", params.label);
    return apiForm<AudioBenchmark>("/api/v1/benchmarks/audio", form);
  },
  list: () => fetchJson<AudioBenchmark[]>("/api/v1/benchmarks"),
  get: (id: number) => fetchJson<AudioBenchmark>(`/api/v1/benchmarks/${id}`),
};

export type { BenchmarkEngineResult };

export const Analytics = {
  robustness: () => fetchJson<RobustnessReport>("/api/v1/analytics/robustness"),
  listDatasets: () => fetchJson<DatasetInfo[]>("/api/v1/analytics/datasets"),
  createSnapshot: (dataset: string, engineId: string) =>
    fetchJson<DriftSnapshotView>(
      `/api/v1/analytics/datasets/${dataset}/snapshot?engine_id=${encodeURIComponent(engineId)}`,
      { method: "POST" },
    ),
  listSnapshots: (dataset: string) =>
    fetchJson<DriftSnapshotView[]>(`/api/v1/analytics/datasets/${dataset}/snapshots`),
  compare: (dataset: string, baselineId: number, currentId: number) =>
    fetchJson<DriftComparisonView>(
      `/api/v1/analytics/datasets/${dataset}/compare?baseline_id=${baselineId}&current_id=${currentId}`,
    ),
};

export const Security = {
  health: () => fetchJson<SecurityHealth>("/api/v1/security/health"),
  audit: () => fetchJson<SecurityAuditEvent[]>("/api/v1/security/audit"),
};

async function fetchJson<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const response = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (response.status === 401 && typeof window !== "undefined") {
    setTokenNull();
    window.location.href = "/register";
    throw new ApiError("Session expired", 401);
  }
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      /* keep statusText */
    }
    throw new ApiError(detail, response.status);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
