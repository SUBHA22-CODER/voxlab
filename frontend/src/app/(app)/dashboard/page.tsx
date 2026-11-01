"use client";

import Link from "next/link";
import { useMemo } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ArrowRight, ChartBar, Robot as RobotIcon, TrendUp } from "@phosphor-icons/react";
import { Agents, Runs, Reports } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import {
  Button,
  Card,
  CardBody,
  CardHeader,
  EmptyState,
  PageHeader,
  Skeleton,
  StatusBadge,
} from "@/components/ui";
import type { Report } from "@/lib/types";

export default function DashboardPage() {
  const agents = useApi(Agents.list);
  const runs = useApi(Runs.list, { pollMs: 5000 });

  const completedRunIds = useMemo(
    () =>
      (runs.data ?? [])
        .filter((r) => r.status === "completed")
        .slice(0, 10)
        .map((r) => r.id),
    [runs.data],
  );
  const reports = useApi(
    async () => {
      const settled = await Promise.allSettled(completedRunIds.map((id) => Reports.forRun(id)));
      return settled
        .filter((s): s is PromiseFulfilledResult<Report> => s.status === "fulfilled")
        .map((s) => s.value)
        .sort((a, b) => a.test_run_id - b.test_run_id);
    },
    { enabled: completedRunIds.length > 0 },
  );

  const stats = useMemo(() => {
    const allRuns = runs.data ?? [];
    const history = (reports.data ?? []).map((r) => ({ id: r.test_run_id, score: r.score }));
    const avg = history.length > 0 ? history.reduce((acc, h) => acc + h.score, 0) / history.length : null;
    const latest = history.at(-1)?.score ?? null;
    const previous = history.at(-2)?.score ?? null;
    return {
      agents: agents.data?.length ?? 0,
      connected: agents.data?.filter((a) => a.connection_status === "connected").length ?? 0,
      runs: allRuns.length,
      avg,
      history,
      trend: latest !== null && previous !== null ? latest - previous : null,
    };
  }, [agents.data, runs.data, reports.data]);

  const loading = agents.loading || runs.loading;

  return (
    <>
      <PageHeader
        title="Reliability overview"
        subtitle="How well your voice agents survive real-world stress, tracked run over run."
        actions={
          <Link href="/runs">
            <Button size="sm">
              <TrendUp size={14} weight="bold" />
              New benchmark
            </Button>
          </Link>
        }
      />

      <div className="mb-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
        {loading ? (
          [0, 1, 2].map((i) => <Skeleton key={i} className="h-[148px] rounded-xl" />)
        ) : (
          <>
            <Card className="rise rise-1">
              <CardBody className="flex h-full flex-col justify-between">
                <p className="text-[11px] font-medium uppercase tracking-wider text-zinc-500">
                  Avg. benchmark score
                </p>
                <div className="mt-3 flex items-end justify-between">
                  <p className="bg-gradient-to-b from-zinc-50 to-zinc-400 bg-clip-text text-[44px] font-semibold leading-none tracking-[-0.03em] text-transparent">
                    {stats.avg !== null ? stats.avg.toFixed(1) : "-"}
                  </p>
                  {stats.trend !== null && stats.trend !== 0 && (
                    <span
                      className={`mb-1 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ${
                        stats.trend > 0 ? "bg-emerald-500/10 text-emerald-300" : "bg-red-500/10 text-red-300"
                      }`}
                    >
                      {stats.trend > 0 ? "+" : ""}
                      {stats.trend.toFixed(1)}
                    </span>
                  )}
                </div>
                <p className="mt-3 text-[11px] text-zinc-600">
                  {stats.history.length > 0
                    ? `last ${stats.history.length} completed run${stats.history.length === 1 ? "" : "s"}, of 100`
                    : "no scored runs yet"}
                </p>
              </CardBody>
            </Card>

            <Card spotlight className="rise rise-2 lg:col-span-2">
              <CardHeader className="flex items-center justify-between">
                <span>Score history</span>
                <span className="text-[11px] text-zinc-600">weighted benchmark score per run</span>
              </CardHeader>
              <CardBody className="pb-2">
                {stats.history.length >= 2 ? (
                  <div className="h-[92px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={stats.history} margin={{ top: 6, right: 6, bottom: 0, left: 0 }}>
                        <defs>
                          <linearGradient id="scoreFill" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor="#34d399" stopOpacity={0.22} />
                            <stop offset="100%" stopColor="#34d399" stopOpacity={0} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid stroke="#18181b" strokeDasharray="3 3" vertical={false} />
                        <XAxis
                          dataKey="id"
                          tick={{ fill: "#52525b", fontSize: 10 }}
                          axisLine={{ stroke: "#27272a" }}
                          tickLine={false}
                          tickFormatter={(v) => `#${v}`}
                        />
                        <YAxis domain={[0, 100]} hide />
                        <Tooltip
                          cursor={{ stroke: "#3f3f46", strokeDasharray: "3 3" }}
                          content={({ active, payload }) =>
                            active && payload?.length ? (
                              <div className="rounded-lg border border-zinc-700/80 bg-zinc-900 px-3 py-2 shadow-[0_8px_24px_rgb(0_0_0/0.4)]">
                                <p className="text-[11px] text-zinc-400">Run #{payload[0].payload.id}</p>
                                <p className="font-mono text-sm tabular-nums text-emerald-300">
                                  {Number(payload[0].payload.score).toFixed(1)}
                                </p>
                              </div>
                            ) : null
                          }
                        />
                        <Area
                          type="monotone"
                          dataKey="score"
                          stroke="#34d399"
                          strokeWidth={2}
                          fill="url(#scoreFill)"
                          dot={{ r: 2.5, fill: "#34d399", strokeWidth: 0 }}
                          activeDot={{ r: 4, fill: "#34d399", stroke: "#09090b", strokeWidth: 2 }}
                        />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                ) : (
                  <div className="flex h-[92px] items-center justify-center text-xs text-zinc-600">
                    Complete at least two benchmarks to see the trend.
                  </div>
                )}
              </CardBody>
            </Card>
          </>
        )}
      </div>

      <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2">
        {loading ? (
          [0, 1].map((i) => <Skeleton key={i} className="h-[88px] rounded-xl" />)
        ) : (
          <>
            <StatCard
              icon={<RobotIcon size={16} className="text-emerald-400" weight="duotone" />}
              label="Agents"
              value={stats.agents}
              meta={`${stats.connected} connected`}
              href="/agents"
            />
            <StatCard
              icon={<ChartBar size={16} className="text-emerald-400" weight="duotone" />}
              label="Test runs"
              value={stats.runs}
              meta="all time"
              href="/runs"
            />
          </>
        )}
      </div>

      <Card spotlight className="rise rise-3">
        <CardHeader className="flex items-center justify-between">
          <span>Recent test runs</span>
          <Link
            href="/runs"
            className="flex items-center gap-1 text-xs font-normal text-emerald-400 transition-colors hover:text-emerald-300"
          >
            View all <ArrowRight size={12} weight="bold" />
          </Link>
        </CardHeader>
        <CardBody className="p-0">
          {loading ? (
            <div className="space-y-2 p-5">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-10" />
              ))}
            </div>
          ) : (runs.data ?? []).length === 0 ? (
            <EmptyState
              icon={<ChartBar size={20} weight="duotone" />}
              title="No test runs yet"
              hint="Benchmark an agent against the scenario library to see reliability scores here."
              action={
                <Link href="/runs">
                  <Button size="sm" variant="secondary">
                    Run first benchmark
                  </Button>
                </Link>
              }
            />
          ) : (
            <table className="w-full text-[13px]">
              <thead>
                <tr className="border-b border-zinc-800/60 text-left text-[11px] uppercase tracking-wider text-zinc-500">
                  <th className="px-5 py-2.5 font-medium">Run</th>
                  <th className="px-5 py-2.5 font-medium">Progress</th>
                  <th className="px-5 py-2.5 font-medium">Status</th>
                  <th className="px-5 py-2.5 text-right font-medium">Score</th>
                  <th className="hidden px-5 py-2.5 font-medium sm:table-cell">Started</th>
                </tr>
              </thead>
              <tbody>
                {(runs.data ?? []).slice(0, 8).map((run) => {
                  const report = reports.data?.find((r) => r.test_run_id === run.id);
                  return (
                    <tr
                      key={run.id}
                      className="border-b border-zinc-800/40 transition-colors last:border-0 hover:bg-zinc-800/20"
                    >
                      <td className="px-5 py-3">
                        <Link
                          href={`/runs/${run.id}`}
                          className="font-medium text-emerald-400 transition-colors hover:text-emerald-300"
                        >
                          Run #{run.id}
                        </Link>
                      </td>
                      <td className="px-5 py-3 tabular-nums text-zinc-400">
                        {run.progress}/{run.total_sessions}
                      </td>
                      <td className="px-5 py-3">
                        <StatusBadge status={run.status} />
                      </td>
                      <td className="px-5 py-3 text-right">
                        {report ? (
                          <span className="inline-flex items-center justify-end gap-2.5">
                            <span className="hidden h-1 w-16 overflow-hidden rounded-full bg-zinc-800 sm:block">
                              <span
                                className={`block h-full rounded-full ${
                                  report.score >= 80 ? "bg-emerald-400" : report.score >= 60 ? "bg-amber-400" : "bg-red-400"
                                }`}
                                style={{ width: `${Math.min(100, report.score)}%` }}
                              />
                            </span>
                            <span className="w-12 font-mono text-[13px] tabular-nums text-zinc-100">
                              {report.score.toFixed(1)}
                            </span>
                          </span>
                        ) : (
                          <span className="font-mono text-[13px] text-zinc-600">-</span>
                        )}
                      </td>
                      <td className="hidden px-5 py-3 text-zinc-500 sm:table-cell">
                        {new Date(run.started_at).toLocaleString(undefined, {
                          month: "short",
                          day: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </CardBody>
      </Card>
    </>
  );
}

function StatCard({
  icon,
  label,
  value,
  meta,
  href,
}: {
  icon: React.ReactNode;
  label: string;
  value: number | string;
  meta: string;
  href: string;
}) {
  return (
    <Link href={href} className="group block">
      <Card spotlight className="transition-colors duration-200 group-hover:border-zinc-700">
        <CardBody className="flex items-center justify-between">
          <div>
            <p className="text-[11px] font-medium uppercase tracking-wider text-zinc-500">{label}</p>
            <p className="mt-1.5 text-[26px] font-semibold leading-none tracking-[-0.02em] text-zinc-100">
              {value}
            </p>
            <p className="mt-2 text-[11px] text-zinc-600">{meta}</p>
          </div>
          <span className="flex h-9 w-9 items-center justify-center rounded-lg border border-zinc-800 bg-zinc-900/80 transition-colors group-hover:border-zinc-700">
            {icon}
          </span>
        </CardBody>
      </Card>
    </Link>
  );
}
