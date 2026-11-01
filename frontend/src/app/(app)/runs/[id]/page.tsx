"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, XCircle } from "@phosphor-icons/react";
import { Runs } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { Button, PageHeader, Skeleton, StatusBadge } from "@/components/ui";
import { ReportView } from "@/components/report-view";

export default function RunDetailPage() {
  const params = useParams<{ id: string }>();
  const runId = Number(params.id);
  const run = useApi(() => Runs.get(runId), { pollMs: 2500 });

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
  if (run.error || !run.data) return <p className="text-sm text-red-400">{run.error}</p>;

  const data = run.data;
  const stillRunning = data.status === "queued" || data.status === "running";

  return (
    <>
      <PageHeader
        title={
          <span className="flex items-center gap-3">
            <Link
              href="/runs"
              aria-label="Back to runs"
              className="rounded-lg p-1 text-zinc-500 transition-colors hover:bg-zinc-900 hover:text-zinc-200"
            >
              <ArrowLeft size={18} />
            </Link>
            Run #{data.id}
          </span>
        }
        subtitle={
          stillRunning
            ? "Benchmark in progress. Sessions execute and evaluate live."
            : `Finished ${data.finished_at ? new Date(data.finished_at).toLocaleString() : ""}`
        }
        actions={
          stillRunning ? (
            <Button
              variant="danger"
              size="sm"
              onClick={async () => {
                await Runs.cancel(data.id);
                run.refetch();
              }}
            >
              <XCircle size={14} />
              Cancel run
            </Button>
          ) : undefined
        }
      />

      <div className="mb-6 flex items-center gap-4">
        <StatusBadge status={data.status} />
        <span className="text-sm tabular-nums text-zinc-400">
          {data.progress}/{data.total_sessions} sessions
        </span>
        <div className="h-1.5 w-48 overflow-hidden rounded-full bg-zinc-800/80">
          <div
            className="h-full rounded-full bg-emerald-500 transition-all duration-500"
            style={{ width: `${data.total_sessions ? (data.progress / data.total_sessions) * 100 : 0}%` }}
          />
        </div>
        {data.error && <span className="font-mono text-xs text-red-400">{data.error}</span>}
      </div>

      {data.report ? (
        <ReportView summary={data.report} runId={data.id} />
      ) : stillRunning ? (
        <p className="rounded-xl border border-zinc-800/80 bg-zinc-900/40 px-5 py-4 text-sm text-zinc-400">
          The report generates automatically when all sessions finish.
        </p>
      ) : (
        <p className="text-sm text-zinc-500">No report was generated for this run.</p>
      )}
    </>
  );
}
