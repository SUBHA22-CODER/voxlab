"use client";

import { useState } from "react";
import Link from "next/link";
import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { Badge, Button, Card, CardBody, CardHeader } from "@/components/ui";
import { Reports, Runs } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import type { ReportSummary } from "@/lib/types";

const COMPONENT_COLORS: Record<string, string> = {
  T: "#34d399",
  Q: "#60a5fa",
  R: "#a78bfa",
  L: "#fbbf24",
  E: "#f87171",
};

export function ScoreRing({ score, size = 120 }: { score: number; size?: number }) {
  const radius = (size - 14) / 2;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.max(0, Math.min(100, score));
  const color = clamped >= 80 ? "#34d399" : clamped >= 60 ? "#fbbf24" : "#f87171";
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={`Score ${score} of 100`}>
      <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="#27272a" strokeWidth="10" />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        stroke={color}
        strokeWidth="10"
        strokeLinecap="round"
        strokeDasharray={`${(clamped / 100) * circumference} ${circumference}`}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
      />
      <text x="50%" y="47%" textAnchor="middle" dominantBaseline="middle" className="fill-zinc-100" fontSize={size / 4} fontWeight="700">
        {clamped.toFixed(1)}
      </text>
      <text x="50%" y="66%" textAnchor="middle" dominantBaseline="middle" className="fill-zinc-500" fontSize={size / 9}>
        / 100
      </text>
    </svg>
  );
}

export function ComponentChart({ components }: { components: ReportSummary["components"] }) {
  const data = Object.entries(components).map(([key, value]) => ({ key, value }));
  return (
    <div className="h-56 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -20 }}>
          <CartesianGrid stroke="#27272a" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="key" tick={{ fill: "#a1a1aa", fontSize: 12 }} axisLine={{ stroke: "#3f3f46" }} tickLine={false} />
          <YAxis domain={[0, 100]} tick={{ fill: "#71717a", fontSize: 11 }} axisLine={false} tickLine={false} />
          <ReferenceLine y={100} stroke="#3f3f46" />
          <Bar dataKey="value" radius={[4, 4, 0, 0]} maxBarSize={48}>
            {data.map((entry) => (
              <Cell key={entry.key} fill={COMPONENT_COLORS[entry.key] ?? "#71717a"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ComponentLegend({ summary }: { summary: ReportSummary }) {
  return (
    <ul className="space-y-1 text-xs text-zinc-500">
      {Object.entries(summary.legend).map(([key, text]) => (
        <li key={key}>
          <span className="font-semibold" style={{ color: COMPONENT_COLORS[key] }}>
            {key}
          </span>{" "}
          — {text}
        </li>
      ))}
    </ul>
  );
}

export function FailuresList({ summary }: { summary: ReportSummary }) {
  if (summary.failures.length === 0) {
    return (
      <p className="px-5 py-6 text-center text-sm text-emerald-400">
        All scenarios passed. Agent handled every stress condition.
      </p>
    );
  }
  return (
    <div className="divide-y divide-zinc-800">
      {summary.failures.map((failure) => (
        <div key={failure.session_id} className="px-5 py-4">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium text-zinc-200">{failure.scenario_name}</p>
            <Link href={`/traces/${failure.session_id}`} className="text-xs text-emerald-400 hover:underline">
              Inspect trace →
            </Link>
          </div>
          <ul className="mt-2 space-y-1.5">
            {failure.failed_checks.map((check, i) => (
              <li key={i} className="rounded-lg border border-red-500/20 bg-red-500/5 px-3 py-2 text-xs text-zinc-300">
                <span className="font-mono text-red-400">{check.type}</span> — {check.detail}
              </li>
            ))}
          </ul>
          {failure.judge_notes && <p className="mt-1.5 text-xs italic text-zinc-500">judge: {failure.judge_notes}</p>}
        </div>
      ))}
    </div>
  );
}

export function ReportView({ summary, runId }: { summary: ReportSummary; runId: number }) {
  const [compareId, setCompareId] = useState("");
  const [comparison, setComparison] = useState<Awaited<ReturnType<typeof Reports.compare>> | null>(null);
  const [comparing, setComparing] = useState(false);
  const runs = useApi(Runs.list);

  const otherRuns = (runs.data ?? [])
    .filter((run) => run.id !== runId && run.status === "completed")
    .map((run) => run.id)
    .sort((a, b) => b - a)
    .slice(0, 10);

  async function runCompare() {
    if (!compareId) return;
    setComparing(true);
    try {
      const report = await Reports.forRun(runId);
      setComparison(await Reports.compare(report.id, Number(compareId)));
    } finally {
      setComparing(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader>Overall score</CardHeader>
          <CardBody className="flex flex-col items-center gap-3">
            <ScoreRing score={summary.score} />
            <p className="text-center font-mono text-[11px] text-zinc-500">{summary.formula}</p>
            <p className="text-xs text-zinc-400">
              {summary.totals.passed}/{summary.totals.sessions} scenarios passed
              {summary.judge_mode && (
                <>
                  {" · "}
                  <span className={summary.judge_mode === "llm" ? "text-sky-400" : "text-amber-400"}>
                    {summary.judge_mode === "llm" ? "LLM judge" : "heuristic scoring"}
                  </span>
                </>
              )}
            </p>
          </CardBody>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>Component breakdown</CardHeader>
          <CardBody>
            <ComponentChart components={summary.components} />
            <ComponentLegend summary={summary} />
          </CardBody>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex flex-wrap items-center justify-between gap-3">
          <span>Failures &amp; diagnosis</span>
          <span className="flex items-center gap-2 text-xs font-normal">
            <select
              value={compareId}
              onChange={(e) => setCompareId(e.target.value)}
              className="rounded-lg border border-zinc-700 bg-zinc-900 px-2 py-1 text-xs text-zinc-300"
              aria-label="Compare with another run"
            >
              <option value="">Compare with…</option>
              {(otherRuns ?? []).map((id) => (
                <option key={id} value={id}>
                  Run #{id}
                </option>
              ))}
            </select>
            <Button variant="secondary" className="px-2.5 py-1 text-xs" onClick={runCompare} disabled={!compareId || comparing}>
              {comparing ? "Comparing…" : "Compare"}
            </Button>
          </span>
        </CardHeader>
        <CardBody className="p-0">
          {comparison && <ComparisonStrip comparison={comparison} />}
          <FailuresList summary={summary} />
        </CardBody>
      </Card>

      <Card>
        <CardHeader>Per-scenario results</CardHeader>
        <CardBody className="p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-800 text-left text-xs uppercase tracking-wide text-zinc-500">
                <th className="px-5 py-3 font-medium">Scenario</th>
                <th className="px-5 py-3 font-medium">Category</th>
                <th className="px-5 py-3 font-medium">Result</th>
                <th className="px-5 py-3 font-medium">Overall</th>
                <th className="px-5 py-3 font-medium">Trace</th>
              </tr>
            </thead>
            <tbody>
              {summary.per_session.map((session) => (
                <tr key={session.session_id} className="border-b border-zinc-800/50 last:border-0 hover:bg-zinc-900/50">
                  <td className="px-5 py-3 text-zinc-200">{session.scenario_name}</td>
                  <td className="px-5 py-3 text-zinc-500">{session.category.replace(/_/g, " ")}</td>
                  <td className="px-5 py-3">
                    <Badge tone={session.passed ? "green" : "red"}>{session.passed ? "passed" : "failed"}</Badge>
                  </td>
                  <td className="px-5 py-3 font-mono text-zinc-300">{session.overall ?? "—"}</td>
                  <td className="px-5 py-3">
                    <Link href={`/traces/${session.session_id}`} className="text-emerald-400 hover:underline">
                      view
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>Scoring methodology</CardHeader>
        <CardBody className="space-y-1.5 text-xs text-zinc-500">
          {Object.entries(summary.methodology).map(([key, text]) => (
            <p key={key}>{text}</p>
          ))}
          <p>Weights used for this run: {Object.entries(summary.weights).map(([k, v]) => `${k}=${v}`).join(", ")}.</p>
        </CardBody>
      </Card>
    </div>
  );
}

function ComparisonStrip({ comparison }: { comparison: Awaited<ReturnType<typeof Reports.compare>> }) {
  const rows: Array<[string, number | null, number | null, number]> = [
    ["Overall", comparison.baseline.score, comparison.candidate.score, comparison.deltas.score],
    ...(["T", "Q", "R", "L", "E"] as const).map((key) => [
      key,
      comparison.baseline.components?.[key] ?? null,
      comparison.candidate.components?.[key] ?? null,
      comparison.deltas[key],
    ] as [string, number | null, number | null, number]),
  ];
  return (
    <div className="border-b border-zinc-800 bg-zinc-950/50 px-5 py-4">
      <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-zinc-500">
        Before → after (run #{comparison.baseline.score !== null ? "baseline" : "?"} vs candidate)
      </p>
      <div className="grid grid-cols-3 gap-2 sm:grid-cols-6">
        {rows.map(([label, before, after, delta]) => (
          <div key={label} className="rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2 text-center">
            <p className="text-[11px] uppercase text-zinc-500">{label}</p>
            <p className="font-mono text-sm text-zinc-200">
              {before ?? "—"} → {after ?? "—"}
            </p>
            <p className={`text-xs font-medium ${delta > 0 ? "text-emerald-400" : delta < 0 ? "text-red-400" : "text-zinc-500"}`}>
              {delta > 0 ? "+" : ""}
              {delta}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
