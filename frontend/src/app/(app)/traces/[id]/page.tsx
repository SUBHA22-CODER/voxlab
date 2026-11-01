"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft } from "@phosphor-icons/react";
import { Sessions } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { Button, Card, CardBody, CardHeader, PageHeader, Skeleton } from "@/components/ui";
import { EventTimeline, StageTimeline } from "@/components/trace-timeline";
import type { Scores } from "@/lib/types";

const SCORE_LABELS: Partial<Record<keyof Scores, string>> = {
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

  if (session.loading) {
    return (
      <>
        <Skeleton className="h-9 w-64" />
        <div className="mt-6 grid gap-6 lg:grid-cols-5">
          <div className="space-y-6 lg:col-span-3">
            <Skeleton className="h-56 rounded-xl" />
            <Skeleton className="h-72 rounded-xl" />
          </div>
          <Skeleton className="h-96 rounded-xl lg:col-span-2" />
        </div>
      </>
    );
  }
  if (session.error || !session.data) return <p className="text-sm text-red-400">{session.error}</p>;
  const data = session.data;

  return (
    <>
      <PageHeader
        title={
          <span className="flex items-center gap-3">
            {data.test_run_id && (
              <Link
                href={`/runs/${data.test_run_id}`}
                aria-label="Back to run"
                className="rounded-lg p-1 text-zinc-500 transition-colors hover:bg-zinc-900 hover:text-zinc-200"
              >
                <ArrowLeft size={18} />
              </Link>
            )}
            Session #{data.id}
          </span>
        }
        subtitle={
          <>
            Trace <span className="font-mono text-zinc-500">{data.trace_id.slice(0, 12)}</span>
            {" · "}
            {data.source === "playground" ? "playground session" : "benchmark session"}
          </>
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
                  <ul className="mb-5 space-y-2.5">
                    {(Object.entries(data.evaluation.scores) as Array<[keyof Scores, number]>)
                      .filter(([key]) => key in SCORE_LABELS)
                      .map(([key, value]) => (
                        <li key={key} className="flex items-center gap-3 text-[13px]">
                          <span className="w-32 shrink-0 text-zinc-400">{SCORE_LABELS[key]}</span>
                          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-zinc-800/80">
                            <div
                              className={`h-full rounded-full transition-all duration-500 ${
                                value >= 80 ? "bg-emerald-500" : value >= 50 ? "bg-amber-500" : "bg-red-500"
                              }`}
                              style={{ width: `${Math.min(100, value)}%` }}
                            />
                          </div>
                          <span className="w-9 text-right font-mono text-xs tabular-nums text-zinc-300">
                            {value.toFixed(0)}
                          </span>
                        </li>
                      ))}
                  </ul>
                  {data.evaluation.feedback.judge && (
                    <p className="mb-4 text-xs italic leading-relaxed text-zinc-600">
                      judge ({data.evaluation.feedback.judge.mode}):{" "}
                      {data.evaluation.feedback.judge.notes || "no notes"}
                    </p>
                  )}
                  <div className="space-y-1.5">
                    {data.evaluation.feedback.checks.map((check, i) => (
                      <div
                        key={i}
                        className={`rounded-lg border px-3 py-2 text-xs leading-relaxed ${
                          check.passed
                            ? "border-emerald-500/15 bg-emerald-500/[0.04] text-zinc-400"
                            : "border-red-500/15 bg-red-500/[0.04] text-zinc-400"
                        }`}
                      >
                        <span className={`mr-2 font-mono ${check.passed ? "text-emerald-400" : "text-red-400"}`}>
                          {check.passed ? "pass" : "fail"} · {check.type}
                        </span>
                        <span className="text-zinc-500">{check.detail}</span>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <p className="text-sm leading-relaxed text-zinc-500">
                  This session was not evaluated. Playground conversations are traced but not scored.
                </p>
              )}
            </CardBody>
          </Card>
        </div>
      </div>
    </>
  );
}
