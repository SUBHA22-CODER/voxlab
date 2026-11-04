"use client";

import type {
  Agent,
  Comparison,
  DarwinFinding,
  DarwinPersona,
  DarwinRun,
  Report,
  RunDetail,
  Scenario,
  SessionDetailData,
  TestRun,
  User,
} from "./types";

export const API_URL = (
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
).replace(/\/+$/, "");

const TOKEN_KEY = "voxlab_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const response = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (response.status === 401 && typeof window !== "undefined") {
    setToken(null);
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
  return response.json() as Promise<T>;
}

export function wsUrl(path: string): string {
  const wsBase = API_URL.replace(/^http/, "ws");
  return `${wsBase}${path}`;
}

// --- Typed endpoints ---

export const Auth = {
  login: (email: string, password: string) =>
    api<{ access_token: string }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  register: (email: string, password: string) =>
    api<{ access_token: string }>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  me: () => api<User>("/api/auth/me"),
};

export const Agents = {
  list: () => api<Agent[]>("/api/agents"),
  get: (id: number) => api<Agent>(`/api/agents/${id}`),
  create: (body: Partial<Agent> & { name: string; endpoint: string }) =>
    api<Agent>("/api/agents", { method: "POST", body: JSON.stringify(body) }),
  update: (id: number, body: Partial<Agent>) =>
    api<Agent>(`/api/agents/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  remove: (id: number) => api<void>(`/api/agents/${id}`, { method: "DELETE" }),
  connect: (id: number) =>
    api<{ ok: boolean; status: string; detail: string; latency_ms: number | null }>(
      `/api/agents/${id}/connect`,
      { method: "POST" },
    ),
};

export const Scenarios = {
  list: () => api<Scenario[]>("/api/scenarios"),
  create: (body: { name: string; category: string; definition: object }) =>
    api<Scenario>("/api/scenarios", { method: "POST", body: JSON.stringify(body) }),
  remove: (id: number) => api<void>(`/api/scenarios/${id}`, { method: "DELETE" }),
};

export const Runs = {
  list: () => api<TestRun[]>("/api/test-runs"),
  get: (id: number) => api<RunDetail>(`/api/test-runs/${id}`),
  create: (body: { agent_id: number; scenario_ids: number[]; latency_budget_ms?: number }) =>
    api<TestRun>("/api/test-runs", { method: "POST", body: JSON.stringify(body) }),
  cancel: (id: number) => api<TestRun>(`/api/test-runs/${id}/cancel`, { method: "POST" }),
};

export const Sessions = {
  get: (id: number) => api<SessionDetailData>(`/api/sessions/${id}`),
};

export const Reports = {
  get: (id: number) => api<Report>(`/api/reports/${id}`),
  forRun: (runId: number) => api<Report>(`/api/test-runs/${runId}/report`),
  compare: (a: number, b: number) => api<Comparison>(`/api/reports/${a}/compare/${b}`),
};

export const Darwin = {
  personas: () => api<DarwinPersona[]>("/api/darwin/personas"),
  listRuns: () => api<DarwinRun[]>("/api/darwin/runs"),
  getRun: (id: number) => api<DarwinRun>(`/api/darwin/runs/${id}`),
  createRun: (body: {
    agent_id: number;
    population_size?: number;
    generations?: number;
    top_k?: number;
    personas?: string[];
    seed?: number;
    failure_threshold?: number;
  }) => api<DarwinRun>("/api/darwin/runs", { method: "POST", body: JSON.stringify(body) }),
  cancelRun: (id: number) => api<DarwinRun>(`/api/darwin/runs/${id}/cancel`, { method: "POST" }),
  getFinding: (id: number) => api<DarwinFinding>(`/api/darwin/findings/${id}`),
  exportFinding: (id: number) =>
    api<{ status: string; file_name: string; scenario_id?: number; message: string }>(
      `/api/darwin/findings/${id}/export`,
      { method: "POST" },
    ),
  verifyPatch: (id: number) =>
    api<{
      status: string;
      explanation: string;
      diff: string;
      before_score: number;
      after_score: number;
      score_delta: number;
      verified: boolean;
    }>(`/api/darwin/findings/${id}/verify-patch`, { method: "POST" }),
};

