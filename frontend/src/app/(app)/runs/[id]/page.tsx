"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { Runs } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { Badge, Button, PageHeader, Spinner, statusTone } from "@/components/ui";
import { ReportView } from "@/components/report-view";

export default function RunDetailPage() {
  const params = useParams<{ id: string }>();
  const runId = Number(params.id);
  const run = useApi(() => Runs.get(runId), { pollMs: 2500 });

  if (run.loading) return <Spinner label="Loading run…" />;
  if (run.error || !run.data) return <p className="text-sm text-red-400">{run.error}</p>;
  const data = run.data;
  const stillRunning = data.status === "queued" || data.status === "running";

  return (
    <>
      <PageHeader
        title={`Run #${data.id}`}
        subtitle={
          stillRunning
            ? "Benchmark in progress — sessions execute and evaluate live."
            : `Completed ${data.finished_at ? new Date(data.finished_at).toLocaleString() : ""}`
        }
        actions={
          stillRunning ? (
            <Button
              variant="danger"
              onClick={async () => {
                await Runs.cancel(data.id);
                run.refetch();
              }}
            >
              Cancel run
            </Button>
          ) : (
            <Link href="/runs">
              <Button variant="secondary">All runs</Button>
            </Link>
          )
        }
      />

      <div className="mb-6 flex items-center gap-3">
        <Badge tone={statusTone(data.status)}>{data.status}</Badge>
        <span className="text-sm text-zinc-400">
          {data.progress}/{data.total_sessions} sessions
        </span>
        <div className="h-1.5 w-48 overflow-hidden rounded-full bg-zinc-800">
          <div
            className="h-full rounded-full bg-emerald-500 transition-all"
            style={{ width: `${data.total_sessions ? (data.progress / data.total_sessions) * 100 : 0}%` }}
          />
        </div>
        {data.error && <span className="text-xs text-red-400">{data.error}</span>}
      </div>

      {data.report ? (
        <ReportView summary={data.report} runId={data.id} />
      ) : stillRunning ? (
        <p className="text-sm text-zinc-400">
          Report generates automatically when all sessions finish.
        </p>
      ) : (
        <p className="text-sm text-zinc-500">No report was generated for this run.</p>
      )}
    </>
  );
}
