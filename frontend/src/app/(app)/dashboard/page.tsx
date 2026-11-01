"use client";

import Link from "next/link";
import { useMemo } from "react";
import { Agents, Runs, Reports } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { Badge, Card, CardBody, CardHeader, EmptyState, PageHeader, Spinner, statusTone } from "@/components/ui";
import type { Report } from "@/lib/types";

export default function DashboardPage() {
  const agents = useApi(Agents.list);
  const runs = useApi(Runs.list, { pollMs: 5000 });

  // Reports for the 5 most recent completed runs, fetched in parallel.
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
    return {
      agents: agents.data?.length ?? 0,
      runs: allRuns.length,
      passRate:
        scored.length > 0
          ? Math.round(
              (scored.reduce((acc, s) => acc + s, 0) / scored.length) * 10,
            ) / 10
          : null,
    };
  }, [agents.data, runs.data, reports.data]);

  if (agents.loading || runs.loading) return <Spinner label="Loading dashboard…" />;

  return (
    <>
      <PageHeader
        title="Dashboard"
        subtitle="Overview of your connected voice agents and benchmark activity."
      />

      <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard label="Connected agents" value={stats.agents} href="/agents" />
        <StatCard label="Test runs" value={stats.runs} href="/runs" />
        <StatCard
          label="Avg. benchmark score"
          value={stats.passRate !== null ? `${stats.passRate}/100` : "—"}
          href="/runs"
        />
      </div>

      <Card>
        <CardHeader className="flex items-center justify-between">
          <span>Recent test runs</span>
          <Link href="/runs" className="text-xs font-normal text-emerald-400 hover:underline">
            View all →
          </Link>
        </CardHeader>
        <CardBody className="p-0">
          {(runs.data ?? []).length === 0 ? (
            <EmptyState
              title="No test runs yet"
              hint="Head to Test Runs to benchmark an agent against the scenario library."
            />
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-800 text-left text-xs uppercase tracking-wide text-zinc-500">
                  <th className="px-5 py-3 font-medium">Run</th>
                  <th className="px-5 py-3 font-medium">Scenarios</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Score</th>
                  <th className="px-5 py-3 font-medium">Started</th>
                </tr>
              </thead>
              <tbody>
                {(runs.data ?? []).slice(0, 8).map((run) => {
                  const report = reports.data?.find((r) => r.test_run_id === run.id);
                  return (
                    <tr key={run.id} className="border-b border-zinc-800/50 last:border-0 hover:bg-zinc-900/50">
                      <td className="px-5 py-3">
                        <Link href={`/runs/${run.id}`} className="text-emerald-400 hover:underline">
                          Run #{run.id}
                        </Link>
                      </td>
                      <td className="px-5 py-3 text-zinc-300">
                        {run.progress}/{run.total_sessions}
                      </td>
                      <td className="px-5 py-3">
                        <Badge tone={statusTone(run.status)}>{run.status}</Badge>
                      </td>
                      <td className="px-5 py-3 font-mono text-zinc-300">
                        {report ? `${report.score}/100` : "—"}
                      </td>
                      <td className="px-5 py-3 text-zinc-500">
                        {new Date(run.started_at).toLocaleString()}
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

function StatCard({ label, value, href }: { label: string; value: number | string; href: string }) {
  return (
    <Link href={href}>
      <Card className="transition-colors hover:border-zinc-700">
        <CardBody>
          <p className="text-xs uppercase tracking-wide text-zinc-500">{label}</p>
          <p className="mt-1 text-2xl font-semibold text-zinc-100">{value}</p>
        </CardBody>
      </Card>
    </Link>
  );
}
