export interface User {
  id: number;
  email: string;
  created_at: string;
}

export interface Agent {
  id: number;
  name: string;
  description: string;
  endpoint: string;
  agent_type: "http" | "websocket";
  connection_status: string;
  stt_provider: string;
  llm_provider: string;
  tts_provider: string;
  config: Record<string, unknown>;
  created_at: string;
}

export interface Scenario {
  id: number;
  name: string;
  category: string;
  definition: ScenarioDefinition;
  is_builtin: boolean;
  user_id: number | null;
  created_at: string;
}

export interface ScenarioStep {
  type: "user_message" | "interrupt" | "tool_failure" | "silence";
  content?: string;
}

export interface ScenarioCheck {
  type: string;
  [key: string]: unknown;
}

export interface ScenarioDefinition {
  name?: string;
  description?: string;
  steps: ScenarioStep[];
  expected_behavior?: string;
  latency_budget_ms?: number;
  checks?: ScenarioCheck[];
}

export interface TestRun {
  id: number;
  agent_id: number;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  progress: number;
  total_sessions: number;
  config: { scenario_ids?: number[]; weights?: Record<string, number> };
  error: string | null;
  started_at: string;
  finished_at: string | null;
}

export interface RunSessionSummary {
  id: number;
  scenario_id: number | null;
  scenario_name: string | null;
  status: string;
  started_at: string;
  finished_at: string | null;
  evaluation: { scores: Scores; feedback: Feedback } | null;
}

export interface Scores {
  task_completion: number;
  response_quality: number;
  context_retention: number;
  latency: number;
  error_recovery: number;
}

export interface Feedback {
  checks: CheckResult[];
  judge?: { mode: string; notes?: string };
  latency_budget_ms?: number;
  turn_latencies_ms?: number[];
}

export interface CheckResult {
  type: string;
  params: Record<string, unknown>;
  passed: boolean;
  detail: string;
}

export interface RunDetail extends TestRun {
  sessions: RunSessionSummary[];
  report: ReportSummary | null;
}

export interface ReportFailure {
  session_id: number;
  scenario_name: string;
  category: string;
  failed_checks: CheckResult[];
  judge_notes: string;
}

export interface ReportSession {
  session_id: number;
  scenario_name: string;
  category: string;
  status: string;
  passed: boolean;
  overall: number | null;
  scores: Scores | Record<string, never>;
  failed_checks: CheckResult[];
  judge_notes: string;
  judge_mode: string | null;
}

export interface ReportSummary {
  score: number;
  components: { T: number; Q: number; R: number; L: number; E: number };
  weights: Record<string, number>;
  formula: string;
  legend: Record<string, string>;
  judge_mode: string | null;
  totals: { sessions: number; completed: number; passed: number; failed: number };
  per_session: ReportSession[];
  failures: ReportFailure[];
  methodology: Record<string, string>;
}

export interface Report {
  id: number;
  test_run_id: number;
  score: number;
  summary: ReportSummary;
  created_at: string;
}

export interface Comparison {
  baseline: CompactReport;
  candidate: CompactReport;
  deltas: Record<string, number>;
}

export interface CompactReport {
  score: number | null;
  components: Record<string, number> | null;
  totals: Record<string, number> | null;
  failures: ReportFailure[] | null;
}

export interface VoxEvent {
  id?: number;
  sequence: number;
  event_type: string;
  timestamp: string;
  duration_ms: number | null;
  payload: Record<string, unknown>;
}

export interface SessionDetailData {
  id: number;
  test_run_id: number | null;
  agent_id: number;
  scenario_id: number | null;
  trace_id: string;
  status: string;
  source: string;
  started_at: string;
  finished_at: string | null;
  events: VoxEvent[];
  evaluation: { scores: Scores; feedback: Feedback } | null;
  trace: TraceData | null;
}

export interface TraceStage {
  stage: string;
  duration_ms: number;
  detail?: string;
}

export interface TraceTurn {
  turn: number;
  stages: TraceStage[];
}

export interface TraceData {
  turns: TraceTurn[];
  summary: {
    stage_totals_ms: Record<string, number>;
    e2e_total_ms: number;
    turn_count: number;
    illustrative?: boolean;
  };
}

// --- Darwin Types ---

export interface DarwinPersona {
  id: string;
  name: string;
  description: string;
  is_dictation_focused: boolean;
  strategies: string[];
}

export interface DarwinGeneration {
  id: number;
  generation_index: number;
  best_fitness: number;
  avg_fitness: number;
  stats: Record<string, unknown>;
  created_at: string;
}

export interface DarwinFinding {
  id: number;
  run_id: number;
  persona: string;
  strategy: string;
  genome: {
    persona: string;
    strategy: string;
    steps: ScenarioStep[];
  };
  minimized_steps: ScenarioStep[];
  original_steps_count: number;
  minimized_steps_count: number;
  fitness: number;
  diagnosis: {
    category: string;
    summary: string;
    evidence_event_ids?: string[];
    confidence: number;
    suggested_fix_area?: string;
    heuristic?: boolean;
  };
  trace_id: string | null;
  session_id: number | null;
  exported_scenario_id: number | null;
  patch_proposal: {
    status: string;
    explanation: string;
    diff: string;
    before_score: number;
    after_score: number;
    score_delta: number;
    verified: boolean;
  } | null;
  created_at: string;
}

export interface DarwinRun {
  id: number;
  agent_id: number;
  status: "queued" | "running" | "completed" | "failed" | "cancelled" | "partial";
  config: {
    population_size: number;
    generations: number;
    top_k: number;
    personas: string[];
    seed: number;
    failure_threshold: number;
  };
  stats: {
    current_generation: number;
    total_generations: number;
    sessions_executed: number;
    best_fitness: number;
    avg_fitness: number;
    findings_count: number;
    heuristic_mode?: boolean;
  };
  progress: number;
  error: string | null;
  started_at: string;
  finished_at: string | null;
  generations_data?: DarwinGeneration[];
  findings?: DarwinFinding[];
}

