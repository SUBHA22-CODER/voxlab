"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ArrowRight, Warning } from "@phosphor-icons/react";
import { Button, Card, CardBody, CardHeader } from "@/components/ui";
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

const COMPONENT_NAMES: Record<string, string> = {
  T: "Task completion",
  Q: "Response quality",
  R: "Context retention",
  L: "Latency",
  E: "Error recovery",
};

export function ScoreRing({ score, size = 132 }: { score: number; size?: number }) {
  const radius = (size - 16) / 2;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.max(0, Math.min(100, score));
  const color = clamped >= 80 ? "#34d399" : clamped >= 60 ? "#fbbf24" : "#f87171";
  const grade = clamped >= 80 ? "Strong" : clamped >= 60 ? "Needs review" : "At risk";
  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative">
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={`Score ${score} of 100`}>
          <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="#1c1c21" strokeWidth="10" />
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
            style={{ filter: `drop-shadow(0 0 6px ${color}55)` }}
          />
          <text
            x="50%"
            y="46%"
            textAnchor="middle"
            dominantBaseline="middle"
            fill="#fafafa"
            fontSize={size / 3.6}
            fontWeight="650"
            letterSpacing="-0.03em"
          >
            {clamped.toFixed(1)}
          </text>
          <text x="50%" y="66%" textAnchor="middle" dominantBaseline="middle" fill="#71717a" fontSize={size / 10.5}>
            / 100
          </text>
        </svg>
      </div>
      <span className="text-xs font-medium" style={{ color }}>
        {grade}
      </span>
    </div>
  );
}

function ChartTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: { key: string; value: number } }> }) {
  if (!active || !payload?.length) return null;
  const { key, value } = payload[0].payload;
  return (
    <div className="rounded-lg border border-zinc-700/80 bg-zinc-900 px-3 py-2 shadow-[0_8px_24px_rgb(0_0_0/0.4)]">
      <p className="text-[11px] font-medium text-zinc-300">{COMPONENT_NAMES[key] ?? key}</p>
      <p className="mt-0.5 font-mono text-sm tabular-nums" style={{ color: COMPONENT_COLORS[key] }}>
        {value.toFixed(1)}
      </p>
    </div>
  );
}

export function ComponentChart({ components }: { components: ReportSummary["components"] }) {
  const data = Object.entries(components).map(([key, value]) => ({ key, value }));
  return (
    <div className="h-56 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
          <CartesianGrid stroke="#1c1c21" strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="key"
            tick={{ fill: "#a1a1aa", fontSize: 12, fontWeight: 600 }}
            axisLine={{ stroke: "#27272a" }}
            tickLine={false}
          />
          <YAxis domain={[0, 100]} tick={{ fill: "#52525b", fontSize: 11 }} axisLine={false} tickLine={false} />
          <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgb(255 255 255 / 0.03)" }} />
          <Bar dataKey="value" radius={[5, 5, 0, 0]} maxBarSize={44}>
            {data.map((entry) => (
              <Cell key={entry.key} fill={COMPONENT_COLORS[entry.key] ?? "#71717a"} fillOpacity={0.85} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ComponentLegend({ summary }: { summary: ReportSummary }) {
  return (
    <ul className="grid grid-cols-1 gap-x-6 gap-y-1 text-xs text-zinc-500 sm:grid-cols-2">
      {Object.entries(summary.legend).map(([key, text]) => (
        <li key={key} className="flex gap-2">
          <span className="font-mono font-semibold" style={{ color: COMPONENT_COLORS[key] }}>
            {key}
          </span>
          <span className="min-w-0">{text}</span>
        </li>
      ))}
    </ul>
  );
}

export function FailuresList({ summary }: { summary: ReportSummary }) {
  if (summary.failures.length === 0) {
    return (
      <p className="px-5 py-8 text-center text-sm text-emerald-400">
        All scenarios passed. The agent handled every stress condition.
      </p>
    );
  }
  return (
    <div className="divide-y divide-zinc-800/60">
      {summary.failures.map((failure) => (
        <div key={failure.session_id} className="px-5 py-4">
          <div className="flex items-center justify-between">
            <p className="flex items-center gap-2 text-sm font-medium text-zinc-200">
              <Warning size={14} className="text-red-400" weight="fill" />
              {failure.scenario_name}
            </p>
            <Link
              href={`/traces/${failure.session_id}`}
              className="flex items-center gap-1 text-xs text-emerald-400 transition-colors hover:text-emerald-300"
            >
              Inspect trace <ArrowRight size={11} weight="bold" />
            </Link>
          </div>
          <ul className="mt-2.5 space-y-1.5">
            {failure.failed_checks.map((check, i) => (
              <li
                key={i}
                className="rounded-lg border border-red-500/15 bg-red-500/[0.04] px-3 py-2 text-xs leading-relaxed text-zinc-400"
              >
                <span className="mr-2 font-mono text-red-400">{check.type}</span>
                {check.detail}
              </li>
            ))}
          </ul>
          {failure.judge_notes && (
            <p className="mt-2 text-xs italic text-zinc-600">judge: {failure.judge_notes}</p>
          )}
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
    <div className="rise space-y-6">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <CardHeader>Overall score</CardHeader>
          <CardBody className="flex flex-col items-center gap-3 pb-6">
            <ScoreRing score={summary.score} />
            <div className="w-full border-t border-zinc-800/60 pt-3 text-center">
              <p className="font-mono text-[11px] leading-relaxed text-zinc-600">{summary.formula}</p>
              <p className="mt-2 text-xs text-zinc-400">
                <span className="font-mono tabular-nums text-zinc-200">
                  {summary.totals.passed}/{summary.totals.sessions}
                </span>{" "}
                scenarios passed
                {summary.judge_mode && (
                  <span className={summary.judge_mode === "llm" ? " text-sky-400" : " text-amber-400"}>
                    {" "}
                    · {summary.judge_mode === "llm" ? "LLM judge" : "heuristic scoring"}
                  </span>
                )}
              </p>
            </div>
          </CardBody>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>Component breakdown</CardHeader>
          <CardBody className="pb-2">
            <ComponentChart components={summary.components} />
            <div className="mt-2 border-t border-zinc-800/60 pt-3">
              <ComponentLegend summary={summary} />
            </div>
          </CardBody>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex flex-wrap items-center justify-between gap-3">
          <span>Failures and diagnosis</span>
          <span className="flex items-center gap-2">
            <select
              value={compareId}
              onChange={(e) => setCompareId(e.target.value)}
              className="h-8 rounded-lg border border-zinc-800 bg-zinc-900 px-2.5 text-xs text-zinc-300 transition-colors hover:border-zinc-700 focus:outline-none"
              aria-label="Compare with another run"
            >
              <option value="">Compare with…</option>
              {otherRuns.map((id) => (
                <option key={id} value={id}>
                  Run #{id}
                </option>
              ))}
            </select>
            <Button
              variant="secondary"
              size="sm"
              onClick={runCompare}
              disabled={!compareId || comparing}
            >
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
              <tr className="border-b border-zinc-800/80 text-left text-[11px] uppercase tracking-wider text-zinc-500">
                <th className="px-5 py-2.5 font-medium">Scenario</th>
                <th className="hidden px-5 py-2.5 font-medium md:table-cell">Category</th>
                <th className="px-5 py-2.5 font-medium">Result</th>
                <th className="px-5 py-2.5 text-right font-medium">Overall</th>
                <th className="px-5 py-2.5 text-right font-medium">Trace</th>
              </tr>
            </thead>
            <tbody>
              {summary.per_session.map((session) => (
                <tr
                  key={session.session_id}
                  className="border-b border-zinc-800/40 transition-colors last:border-0 hover:bg-zinc-900/40"
                >
                  <td className="px-5 py-3 text-zinc-200">{session.scenario_name}</td>
                  <td className="hidden px-5 py-3 capitalize text-zinc-500 md:table-cell">
                    {session.category.replace(/_/g, " ")}
                  </td>
                  <td className="px-5 py-3">
                    <span
                      className={`inline-flex items-center gap-1.5 text-xs font-medium ${session.passed ? "text-emerald-400" : "text-red-400"}`}
                    >
                      <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-current" />
                      {session.passed ? "passed" : "failed"}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-right">
                    {session.overall !== null && session.overall !== undefined ? (
                      <span className="inline-flex min-w-14 items-center justify-end gap-2">
                        <span className="hidden h-1 w-12 overflow-hidden rounded-full bg-zinc-800 lg:block">
                          <span
                            className={`block h-full rounded-full ${session.overall >= 80 ? "bg-emerald-500" : session.overall >= 60 ? "bg-amber-500" : "bg-red-500"}`}
                            style={{ width: `${Math.min(100, session.overall)}%` }}
                          />
                        </span>
                        <span className="font-mono text-[13px] tabular-nums text-zinc-200">
                          {session.overall.toFixed(1)}
                        </span>
                      </span>
                    ) : (
                      <span className="font-mono text-[13px] text-zinc-600">-</span>
                    )}
                  </td>
                  <td className="px-5 py-3 text-right">
                    <Link
                      href={`/traces/${session.session_id}`}
                      className="text-xs text-emerald-400 transition-colors hover:text-emerald-300"
                    >
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
        <CardBody className="space-y-2 text-xs leading-relaxed text-zinc-500">
          {Object.entries(summary.methodology).map(([key, text]) => (
            <p key={key}>{text}</p>
          ))}
          <p>
            Weights for this run:{" "}
            {Object.entries(summary.weights)
              .map(([k, v]) => `${k}=${v}`)
              .join(", ")}
            .
          </p>
        </CardBody>
      </Card>
    </div>
  );
}

function ComparisonStrip({ comparison }: { comparison: Awaited<ReturnType<typeof Reports.compare>> }) {
  const rows: Array<[string, number | null, number | null, number]> = [
    ["Overall", comparison.baseline.score, comparison.candidate.score, comparison.deltas.score],
    ...(["T", "Q", "R", "L", "E"] as const).map(
      (key) =>
        [
          key,
          comparison.baseline.components?.[key] ?? null,
          comparison.candidate.components?.[key] ?? null,
          comparison.deltas[key],
        ] as [string, number | null, number | null, number],
    ),
  ];
  return (
    <div className="border-b border-zinc-800/60 bg-zinc-950/60 px-5 py-4">
      <p className="mb-3 text-[11px] font-medium uppercase tracking-wider text-zinc-500">
        Before / after
      </p>
      <div className="grid grid-cols-3 gap-2 sm:grid-cols-6">
        {rows.map(([label, before, after, delta]) => (
          <div
            key={label}
            className="rounded-lg border border-zinc-800/80 bg-zinc-900/60 px-3 py-2.5 text-center"
          >
            <p className="text-[10px] font-medium uppercase tracking-wider text-zinc-500">{label}</p>
            <p className="mt-1 font-mono text-[13px] tabular-nums text-zinc-200">
              {before ?? "-"}
              <span className="mx-1 text-zinc-600">/</span>
              {after ?? "-"}
            </p>
            <p
              className={`mt-0.5 font-mono text-[11px] font-medium tabular-nums ${
                delta > 0 ? "text-emerald-400" : delta < 0 ? "text-red-400" : "text-zinc-500"
              }`}
            >
              {delta > 0 ? "+" : ""}
              {delta}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
