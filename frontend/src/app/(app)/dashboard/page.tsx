"use client";

import Link from "next/link";
import { useMemo } from "react";
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
        .slice(0, 5)
        .map((r) => r.id),
    [runs.data],
  );
  const reports = useApi(
    async () => {
      const settled = await Promise.allSettled(completedRunIds.map((id) => Reports.forRun(id)));
      return settled
        .filter((s): s is PromiseFulfilledResult<Report> => s.status === "fulfilled")
        .map((s) => s.value);
    },
    { enabled: completedRunIds.length > 0 },
  );

  const stats = useMemo(() => {
    const allRuns = runs.data ?? [];
    const scored = (reports.data ?? []).map((r) => r.score);
    const avg = scored.length > 0 ? scored.reduce((acc, s) => acc + s, 0) / scored.length : null;
    return {
      agents: agents.data?.length ?? 0,
      runs: allRuns.length,
      avg,
      connected: agents.data?.filter((a) => a.connection_status === "connected").length ?? 0,
    };
  }, [agents.data, runs.data, reports.data]);

  const loading = agents.loading || runs.loading;

  return (
    <>
      <PageHeader
        title="Dashboard"
        subtitle="Reliability overview for your connected voice agents."
        actions={
          <Link href="/runs">
            <Button size="sm">
              <TrendUp size={14} weight="bold" />
              New benchmark
            </Button>
          </Link>
        }
      />

      <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-3">
        {loading ? (
          [0, 1, 2].map((i) => <Skeleton key={i} className="h-[92px] rounded-xl" />)
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
            <StatCard
              icon={<TrendUp size={16} className="text-emerald-400" weight="duotone" />}
              label="Avg. benchmark score"
              value={stats.avg !== null ? stats.avg.toFixed(1) : "-"}
              meta={stats.avg !== null ? "of 100, recent 5 runs" : "no scored runs yet"}
              href="/runs"
              accent={stats.avg !== null}
            />
          </>
        )}
      </div>

      <Card>
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
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-800/80 text-left text-[11px] uppercase tracking-wider text-zinc-500">
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
                      className="border-b border-zinc-800/40 transition-colors last:border-0 hover:bg-zinc-900/40"
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
                          <span className="inline-flex items-center gap-2">
                            <span className="hidden h-1 w-14 overflow-hidden rounded-full bg-zinc-800 sm:block">
                              <span
                                className={`block h-full rounded-full ${report.score >= 80 ? "bg-emerald-500" : report.score >= 60 ? "bg-amber-500" : "bg-red-500"}`}
                                style={{ width: `${Math.min(100, report.score)}%` }}
                              />
                            </span>
                            <span className="font-mono text-[13px] tabular-nums text-zinc-200">
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
  accent = false,
}: {
  icon: React.ReactNode;
  label: string;
  value: number | string;
  meta: string;
  href: string;
  accent?: boolean;
}) {
  return (
    <Link href={href} className="group block">
      <Card className="transition-all duration-200 group-hover:-translate-y-0.5 group-hover:border-zinc-700">
        <CardBody className="flex items-start justify-between">
          <div>
            <p className="text-[11px] font-medium uppercase tracking-wider text-zinc-500">{label}</p>
            <p className={`mt-1.5 text-[26px] font-semibold leading-none tracking-tight ${accent ? "text-emerald-400" : "text-zinc-100"}`}>
              {value}
            </p>
            <p className="mt-2 text-[11px] text-zinc-600">{meta}</p>
          </div>
          <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-zinc-800 bg-zinc-900">
            {icon}
          </span>
        </CardBody>
      </Card>
    </Link>
  );
}
