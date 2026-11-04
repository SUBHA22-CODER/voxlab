"use client";

import { use, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  ArrowLeft,
  CheckCircle,
  Dna,
  Export,
  GitDiff,
  ShieldCheck,
  Warning,
  XCircle,
} from "@phosphor-icons/react";
import { Darwin } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import {
  Button,
  Card,
  CardBody,
  CardHeader,
  PageHeader,
  Skeleton,
  StatusBadge,
} from "@/components/ui";
import type { DarwinFinding } from "@/lib/types";

export default function DarwinDetailPage() {
  const params = useParams<{ id: string }>();
  const runId = Number(params.id);
  const router = useRouter();

  const run = useApi(() => Darwin.getRun(runId), { pollMs: 2500 });
  const [exportingId, setExportingId] = useState<number | null>(null);
  const [exportedIds, setExportedIds] = useState<Set<number>>(new Set());
  const [verifyingId, setVerifyingId] = useState<number | null>(null);
  const [patchResults, setPatchResults] = useState<Record<number, any>>({});

  if (run.loading) {
    return (
      <>
        <Skeleton className="h-9 w-48" />
        <div className="mt-6 grid gap-4 lg:grid-cols-3">
          <Skeleton className="h-64 rounded-xl" />
          <Skeleton className="h-64 rounded-xl lg:col-span-2" />
        </div>
        <Skeleton className="mt-4 h-48 rounded-xl" />
      </>
    );
  }

  if (run.error || !run.data) {
    return <p className="text-sm text-red-400">{run.error || "Darwin run not found"}</p>;
  }

  const data = run.data;
  const stillRunning = data.status === "queued" || data.status === "running";
  const generations = data.generations_data ?? [];
  const findings = data.findings ?? [];

  async function handleExport(findingId: number) {
    setExportingId(findingId);
    try {
      await Darwin.exportFinding(findingId);
      setExportedIds((prev) => new Set(prev).add(findingId));
      run.refetch();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Export failed");
    } finally {
      setExportingId(null);
    }
  }

  async function handleVerifyPatch(findingId: number) {
    setVerifyingId(findingId);
    try {
      const res = await Darwin.verifyPatch(findingId);
      setPatchResults((prev) => ({ ...prev, [findingId]: res }));
      run.refetch();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Patch verification failed");
    } finally {
      setVerifyingId(null);
    }
  }

  return (
    <>
      <PageHeader
        title={
          <span className="flex items-center gap-3">
            <Link
              href="/darwin"
              aria-label="Back to Darwin"
              className="rounded-lg p-1 text-zinc-500 transition-colors hover:bg-zinc-900 hover:text-zinc-200"
            >
              <ArrowLeft size={18} />
            </Link>
            <Dna size={22} className="text-emerald-400" />
            Darwin Campaign #{data.id}
          </span>
        }
        subtitle={
          stillRunning
            ? `Evolving population (Gen ${data.stats?.current_generation || 0} of ${data.config?.generations}). Mutating personas & hunting edge cases...`
            : data.status === "failed"
            ? `Campaign stopped: ${data.error || "Encountered an issue during execution"}`
            : `Completed ${data.finished_at ? new Date(data.finished_at).toLocaleString() : ""}`
        }
        actions={
          stillRunning ? (
            <Button
              variant="danger"
              size="sm"
              onClick={async () => {
                await Darwin.cancelRun(data.id);
                run.refetch();
              }}
            >
              <XCircle size={14} />
              Stop campaign
            </Button>
          ) : undefined
        }
      />

      {/* Progress & Stat Cards */}
      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-5">
        <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-4">
          <span className="text-[11px] font-medium uppercase tracking-wider text-zinc-500">Status</span>
          <div className="mt-1 flex items-center gap-2">
            <StatusBadge status={data.status} />
            <span className="text-xs text-zinc-400 tabular-nums">{data.progress}%</span>
          </div>
        </div>

        <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-4">
          <span className="text-[11px] font-medium uppercase tracking-wider text-zinc-500">Mode</span>
          <div className="mt-1 flex items-center gap-1.5 text-xs font-mono">
            <span
              className={`h-2 w-2 rounded-full ${
                data.stats?.heuristic_mode ? "bg-amber-400" : "bg-emerald-400"
              }`}
            />
            <span className={data.stats?.heuristic_mode ? "text-amber-300" : "text-emerald-300"}>
              {data.stats?.heuristic_mode ? "Heuristic" : "LLM Guided"}
            </span>
          </div>
        </div>

        <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-4">
          <span className="text-[11px] font-medium uppercase tracking-wider text-zinc-500">Best Attack Fitness</span>
          <p className="mt-1 font-mono text-xl font-semibold text-emerald-400 tabular-nums">
            {data.stats?.best_fitness !== undefined ? (data.stats.best_fitness * 100).toFixed(1) + "%" : "0%"}
          </p>
        </div>

        <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-4">
          <span className="text-[11px] font-medium uppercase tracking-wider text-zinc-500">Sessions Used</span>
          <p className="mt-1 font-mono text-xl font-semibold text-zinc-200 tabular-nums">
            {data.stats?.sessions_executed || 0} <span className="text-xs font-normal text-zinc-500">/ 60 budget</span>
          </p>
        </div>

        <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-4">
          <span className="text-[11px] font-medium uppercase tracking-wider text-zinc-500">Defects Found</span>
          <p className="mt-1 font-mono text-xl font-semibold text-red-400 tabular-nums">
            {findings.length}
          </p>
        </div>
      </div>

      {/* Fitness Over Time Chart */}
      <Card spotlight className="rise rise-1 mb-8">
        <CardHeader className="flex items-center justify-between">
          <span>Adversarial Fitness Over Time</span>
          <span className="text-[11px] text-zinc-500">Higher fitness = agent degradation under fuzzing</span>
        </CardHeader>
        <CardBody className="pt-2">
          {generations.length === 0 ? (
            <p className="py-12 text-center text-xs text-zinc-500">
              {data.status === "failed"
                ? `Campaign stopped before Generation 0 finished (${data.error || "Interrupted"}). Launch a new campaign to test.`
                : "Generating first generation attacks..."}
            </p>
          ) : (
            <div className="h-[220px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart
                  data={generations.map((g) => ({
                    gen: `Gen ${g.generation_index}`,
                    best: Number((g.best_fitness * 100).toFixed(1)),
                    avg: Number((g.avg_fitness * 100).toFixed(1)),
                  }))}
                  margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
                >
                  <defs>
                    <linearGradient id="bestGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#10b981" stopOpacity={0.0} />
                    </linearGradient>
                    <linearGradient id="avgGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#6366f1" stopOpacity={0.2} />
                      <stop offset="95%" stopColor="#6366f1" stopOpacity={0.0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                  <XAxis dataKey="gen" stroke="#71717a" fontSize={11} />
                  <YAxis stroke="#71717a" fontSize={11} domain={[0, 100]} unit="%" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#18181b",
                      border: "1px solid #27272a",
                      borderRadius: "8px",
                      fontSize: "12px",
                    }}
                  />
                  <Legend wrapperStyle={{ fontSize: "11px", paddingTop: "8px" }} />
                  <Area
                    type="monotone"
                    dataKey="best"
                    name="Peak Attack Fitness"
                    stroke="#10b981"
                    fill="url(#bestGrad)"
                    strokeWidth={2}
                  />
                  <Area
                    type="monotone"
                    dataKey="avg"
                    name="Average Population Fitness"
                    stroke="#6366f1"
                    fill="url(#avgGrad)"
                    strokeWidth={1.5}
                    strokeDasharray="4 4"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </CardBody>
      </Card>

      {/* Discovered Defects / Findings */}
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-base font-semibold text-zinc-100">
          Discovered Vulnerabilities & Regressions ({findings.length})
        </h2>
        <span className="text-xs text-zinc-500">
          Minimized via Delta Debugging (ddmin) & Diagnosed by AI Root-Cause Engine
        </span>
      </div>

      {findings.length === 0 ? (
        <Card className="p-8 text-center">
          <p className="text-sm text-zinc-400">
            {stillRunning
              ? "Scanning agent boundaries... Any reproduction causing score drops below 50% will appear here."
              : "No critical failure boundaries found in this run. Agent successfully withstood all tested persona attacks."}
          </p>
        </Card>
      ) : (
        <div className="space-y-6">
          {findings.map((f) => {
            const isExported = exportedIds.has(f.id) || f.exported_scenario_id !== null;
            const patch = patchResults[f.id] || f.patch_proposal;

            return (
              <Card key={f.id} spotlight className="border-zinc-800 bg-zinc-900/50">
                <CardHeader className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800/80 pb-3">
                  <div className="flex items-center gap-2.5">
                    <span className="rounded-md border border-red-500/30 bg-red-500/10 px-2 py-0.5 text-xs font-semibold text-red-400">
                      {f.diagnosis?.category?.replace(/_/g, " ") || "Failure"}
                    </span>
                    <span className="rounded-md border border-zinc-700 bg-zinc-800/70 px-2 py-0.5 text-xs text-zinc-300 capitalize">
                      Persona: {f.persona.replace(/_/g, " ")}
                    </span>
                    <span className="text-xs text-zinc-500">
                      Shrunk:{" "}
                      <span className="font-mono text-zinc-300">
                        {f.original_steps_count} → {f.minimized_steps_count} turns
                      </span>
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    {f.trace_id && (
                      <Link
                        href={`/traces/${f.session_id || f.trace_id}`}
                        className="rounded-lg border border-zinc-800 bg-zinc-900 px-2.5 py-1 text-xs text-zinc-300 transition-colors hover:border-zinc-700 hover:text-white"
                      >
                        Inspect Trace
                      </Link>
                    )}

                    <Button
                      size="sm"
                      variant="secondary"
                      disabled={isExported || exportingId === f.id}
                      onClick={() => handleExport(f.id)}
                    >
                      {isExported ? (
                        <>
                          <CheckCircle size={13} weight="fill" className="text-emerald-400" /> Exported
                        </>
                      ) : (
                        <>
                          <Export size={13} /> {exportingId === f.id ? "Exporting…" : "Export to Regression"}
                        </>
                      )}
                    </Button>
                  </div>
                </CardHeader>

                <CardBody className="space-y-4 pt-4">
                  {/* Diagnosis summary */}
                  <div>
                    <div className="flex items-center gap-2">
                      <h4 className="text-[11px] font-medium uppercase tracking-wider text-zinc-500">
                        Root Cause Diagnosis ({Math.round((f.diagnosis?.confidence || 0.8) * 100)}% confidence)
                      </h4>
                      <span
                        className={`rounded px-1.5 py-0.5 text-[10px] font-mono uppercase ${
                          f.diagnosis?.heuristic !== false
                            ? "border border-amber-500/30 bg-amber-500/10 text-amber-400"
                            : "border border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                        }`}
                      >
                        {f.diagnosis?.heuristic !== false ? "Heuristic Rules" : "LLM Grounded"}
                      </span>
                    </div>
                    <p className="mt-1 text-sm font-medium text-zinc-200">
                      {f.diagnosis?.summary}
                    </p>
                    {f.diagnosis?.evidence_event_ids && f.diagnosis.evidence_event_ids.length > 0 && (
                      <div className="mt-1.5 flex items-center gap-1.5 text-xs text-zinc-400">
                        <span className="text-zinc-500">Grounded in trace event(s):</span>
                        {f.diagnosis.evidence_event_ids.map((evId) => (
                          <span
                            key={evId}
                            className="rounded border border-zinc-700 bg-zinc-800/80 px-1.5 py-0.5 font-mono text-[10px] text-zinc-200"
                          >
                            #{evId}
                          </span>
                        ))}
                      </div>
                    )}
                    <p className="mt-1 text-xs text-zinc-500">
                      Target strategy: <span className="text-zinc-400">{f.strategy}</span>
                    </p>
                  </div>

                  {/* Minimized Conversation Reproduction */}
                  <div>
                    <span className="mb-2 block text-[11px] font-medium uppercase tracking-wider text-zinc-500">
                      Minimized Repro Sequence (ddmin 1-minimal turns)
                    </span>
                    <div className="space-y-2 rounded-lg border border-zinc-800/80 bg-zinc-950/60 p-3">
                      {(f.minimized_steps || []).map((step, sIdx) => (
                        <div key={sIdx} className="flex items-start gap-2 text-xs">
                          <span
                            className={`rounded px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase ${
                              step.type === "interrupt"
                                ? "bg-amber-500/20 text-amber-300"
                                : step.type === "tool_failure"
                                ? "bg-red-500/20 text-red-300"
                                : "bg-emerald-500/20 text-emerald-300"
                            }`}
                          >
                            {step.type}
                          </span>
                          <span className="text-zinc-300">
                            {step.content || "(injected internal API failure)"}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Phase 2: Auto-Doctor Patch & Sandbox Verification */}
                  <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <GitDiff size={16} className="text-emerald-400" />
                        <span className="text-xs font-semibold text-zinc-200">
                          Auto-Doctor: Remediation Patch & Sandbox Verification
                        </span>
                      </div>

                      <Button
                        size="sm"
                        variant="secondary"
                        disabled={verifyingId === f.id}
                        onClick={() => handleVerifyPatch(f.id)}
                      >
                        <ShieldCheck size={14} className="text-emerald-400" />
                        {verifyingId === f.id ? "Testing in Sandbox…" : "Verify Fix in Sandbox"}
                      </Button>
                    </div>

                    {patch && (
                      <div className="mt-3 space-y-2.5">
                        <div className="flex items-center gap-3 text-xs">
                          <span className="font-medium text-zinc-400">Diagnosis fix:</span>
                          <span className="text-zinc-200">{patch.explanation}</span>
                        </div>

                        <div className="flex items-center gap-4 text-xs font-mono">
                          <span>
                            Before: <span className="text-red-400 font-bold">{patch.before_score}/100</span>
                          </span>
                          <span>→</span>
                          <span>
                            After Patch: <span className="text-emerald-400 font-bold">{patch.after_score}/100</span>
                          </span>
                          <span className="rounded bg-emerald-500/20 px-1.5 py-0.5 text-[11px] font-bold text-emerald-300">
                            +{patch.score_delta} pts ({patch.status})
                          </span>
                        </div>

                        {patch.diff && (
                          <pre className="max-h-36 overflow-auto rounded border border-zinc-800 bg-black/60 p-2.5 font-mono text-[11px] text-zinc-300">
                            {patch.diff}
                          </pre>
                        )}
                      </div>
                    )}
                  </div>
                </CardBody>
              </Card>
            );
          })}
        </div>
      )}
    </>
  );
}
