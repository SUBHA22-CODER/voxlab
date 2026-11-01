"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { Sessions } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { Badge, Button, Card, CardBody, CardHeader, PageHeader, Spinner } from "@/components/ui";
import { EventTimeline, StageTimeline } from "@/components/trace-timeline";
import type { Scores } from "@/lib/types";

const SCORE_LABELS: Record<keyof Scores, string> = {
  task_completion: "Task completion",
  response_quality: "Response quality",
  context_retention: "Context retention",
  latency: "Latency",
  error_recovery: "Error recovery",
};

export default function TracePage() {
  const params = useParams<{ id: string }>();
  const sessionId = Number(params.id);
  const session = useApi(() => Sessions.get(sessionId));

  if (session.loading) return <Spinner label="Loading session…" />;
  if (session.error || !session.data) return <p className="text-sm text-red-400">{session.error}</p>;
  const data = session.data;

  return (
    <>
      <PageHeader
        title={`Trace · session #${data.id}`}
        subtitle={`Trace ${data.trace_id.slice(0, 12)}… · ${data.source === "playground" ? "playground session" : "benchmark session"}`}
        actions={
          data.test_run_id ? (
            <Link href={`/runs/${data.test_run_id}`}>
              <Button variant="secondary">Back to run</Button>
            </Link>
          ) : undefined
        }
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
        <div className="lg:col-span-3">
          <Card>
            <CardHeader>Pipeline timeline</CardHeader>
            <CardBody>
              <StageTimeline trace={data.trace} />
            </CardBody>
          </Card>
          <Card className="mt-6">
            <CardHeader>Event stream</CardHeader>
            <CardBody>
              <EventTimeline events={data.events} />
            </CardBody>
          </Card>
        </div>

        <div className="space-y-6 lg:col-span-2">
          <Card>
            <CardHeader>Evaluation</CardHeader>
            <CardBody>
              {data.evaluation ? (
                <>
                  <ul className="mb-4 space-y-2">
                    {(Object.entries(data.evaluation.scores) as Array<[keyof Scores, number]>)
                      .filter(([key]) => key in SCORE_LABELS)
                      .map(([key, value]) => (
                        <li key={key} className="flex items-center gap-3 text-sm">
                          <span className="w-36 text-zinc-400">{SCORE_LABELS[key]}</span>
                          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-zinc-800">
                            <div
                              className={`h-full rounded-full ${value >= 80 ? "bg-emerald-500" : value >= 50 ? "bg-amber-500" : "bg-red-500"}`}
                              style={{ width: `${value}%` }}
                            />
                          </div>
                          <span className="w-10 text-right font-mono text-xs text-zinc-300">{value.toFixed(0)}</span>
                        </li>
                      ))}
                  </ul>
                  {data.evaluation.feedback.judge && (
                    <p className="mb-3 text-xs italic text-zinc-500">
                      judge ({data.evaluation.feedback.judge.mode}): {data.evaluation.feedback.judge.notes || "—"}
                    </p>
                  )}
                  <div className="space-y-1.5">
                    {data.evaluation.feedback.checks.map((check, i) => (
                      <div
                        key={i}
                        className={`rounded-lg border px-3 py-2 text-xs ${
                          check.passed
                            ? "border-emerald-500/20 bg-emerald-500/5 text-zinc-300"
                            : "border-red-500/20 bg-red-500/5 text-zinc-300"
                        }`}
                      >
                        <span className={`font-mono ${check.passed ? "text-emerald-400" : "text-red-400"}`}>
                          {check.passed ? "✓" : "✗"} {check.type}
                        </span>
                        <span className="ml-2 text-zinc-500">{check.detail}</span>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <p className="text-sm text-zinc-500">This session was not evaluated (playground conversation).</p>
              )}
            </CardBody>
          </Card>
        </div>
      </div>
    </>
  );
}

export function SessionStatusBadge({ status }: { status: string }) {
  return <Badge tone={status === "completed" ? "green" : "red"}>{status}</Badge>;
}
