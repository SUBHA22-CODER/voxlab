"use client";

import { useCallback, useEffect, useState } from "react";
import { Flask, Play, Trash, CheckCircle, WarningCircle, ArrowBendUpRight } from "@phosphor-icons/react";

import { Regressions } from "@/lib/audio-api";
import type { AudioRegressionCase, AudioRegressionReplay } from "@/lib/audio-types";
import {
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  EmptyState,
  PageHeader,
} from "@/components/ui";

/**
 * Regression corpus: persistent, replayable transcription-failure cases.
 * Replay runs the stored minimized chain through the real engine NOW and
 * classifies the outcome honestly (fixed / improved / still_failing).
 */

const severityTone: Record<string, string> = {
  critical: "border-red-500/40 bg-red-500/10 text-red-300",
  high: "border-amber-500/40 bg-amber-500/10 text-amber-300",
  medium: "border-zinc-700 bg-zinc-800/60 text-zinc-300",
  low: "border-zinc-700/70 bg-zinc-800/40 text-zinc-400",
};

function ReplayBadge({ replay }: { replay: AudioRegressionReplay | undefined }) {
  if (!replay) return null;
  const tone =
    replay.status === "fixed"
      ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
      : replay.status === "still_failing"
        ? "border-red-500/40 bg-red-500/10 text-red-300"
        : "border-amber-500/40 bg-amber-500/10 text-amber-300";
  return (
    <span className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] ${tone}`}>
      {replay.status === "fixed" ? (
        <CheckCircle className="h-3 w-3" aria-hidden />
      ) : (
        <WarningCircle className="h-3 w-3" aria-hidden />
      )}
      {replay.status.replace("_", " ")}
      {replay.wer !== null && <span className="font-mono">· WER {(replay.wer * 100).toFixed(0)}%</span>}
    </span>
  );
}

export default function RegressionsPage() {
  const [cases, setCases] = useState<AudioRegressionCase[]>([]);
  const [replays, setReplays] = useState<Record<number, AudioRegressionReplay>>({});
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(() => {
    Regressions.list()
      .then(setCases)
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(load, [load]);

  async function replay(caseId: number) {
    setBusyId(caseId);
    setError(null);
    try {
      const result = await Regressions.replay(caseId);
      setReplays((prev) => ({ ...prev, [caseId]: result }));
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Replay failed");
    } finally {
      setBusyId(null);
    }
  }

  async function remove(caseId: number) {
    setBusyId(caseId);
    try {
      await Regressions.remove(caseId);
      setCases((prev) => prev.filter((c) => c.id !== caseId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setBusyId(null);
    }
  }

  const stillFailing = cases.filter(
    (c) => c.last_run?.status === "still_failing",
  ).length;

  return (
    <div>
      <PageHeader
        title="Audio Regression Corpus"
        subtitle="Persistent transcription-failure cases discovered by Darwin. Replay any case against the live engine to verify a failure still exists, or confirm it has been fixed."
        actions={
          cases.length > 0 ? (
            <div className="flex items-center gap-2 text-xs text-zinc-500">
              <span className="font-mono text-zinc-300">{cases.length}</span> cases
              {stillFailing > 0 && (
                <span className="font-mono text-red-400">{stillFailing} still failing</span>
              )}
            </div>
          ) : undefined
        }
      />

      {error && (
        <p role="alert" className="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">
          {error}
        </p>
      )}

      {cases.length === 0 ? (
        <Card>
          <EmptyState
            icon={<Flask className="h-6 w-6" aria-hidden />}
            title="The corpus is empty"
            hint="Run the Darwin Audio Lab and promote discovered failures into the corpus to start tracking regressions over time."
          />
        </Card>
      ) : (
        <div className="space-y-4">
          {cases.map((c) => {
            const gt = c.metrics?.ground_truth;
            return (
              <Card key={c.id}>
                <CardHeader
                  right={
                    <div className="flex items-center gap-2">
                      <span className={`rounded-md border px-2 py-0.5 text-[11px] ${severityTone[c.severity] ?? severityTone.medium}`}>
                        {c.severity}
                      </span>
                      <Badge>{c.engine}</Badge>
                      {c.model_version && <Badge>{c.model_version}</Badge>}
                    </div>
                  }
                >
                  <span className="font-mono text-xs text-zinc-400">{c.test_id}</span>
                  <span className="ml-2 text-zinc-500">·</span>
                  <span className="ml-2 text-sm text-zinc-300">
                    {c.failure_category.replace(/_/g, " ")}
                  </span>
                </CardHeader>
                <CardBody className="space-y-3">
                  <div className="grid gap-3 md:grid-cols-2">
                    <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-3">
                      <p className="mb-1 text-[10px] font-medium uppercase tracking-wider text-zinc-600">
                        Reference
                      </p>
                      <p className="text-sm leading-relaxed text-zinc-300">{c.reference_transcript}</p>
                    </div>
                    <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-3">
                      <p className="mb-1 text-[10px] font-medium uppercase tracking-wider text-zinc-600">
                        Baseline failure
                      </p>
                      {gt && (
                        <div className="flex flex-wrap gap-x-4 gap-y-1 font-mono text-[11px] text-zinc-500">
                          <span>WER {(gt.wer * 100).toFixed(1)}%</span>
                          <span>CER {(gt.cer * 100).toFixed(1)}%</span>
                          <span>chain {c.chain.length} steps</span>
                        </div>
                      )}
                      <p className="mt-1.5 text-xs leading-relaxed text-zinc-400">{c.expected_behavior}</p>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      {c.last_run && (
                        <span className="flex items-center gap-1.5 text-[11px] text-zinc-500">
                          <ArrowBendUpRight className="h-3.5 w-3.5" aria-hidden />
                          last replay:{" "}
                          <span
                            className={
                              c.last_run.status === "fixed"
                                ? "text-emerald-400"
                                : c.last_run.status === "still_failing"
                                  ? "text-red-400"
                                  : "text-amber-400"
                            }
                          >
                            {c.last_run.status.replace("_", " ")}
                          </span>
                          <span className="font-mono">· WER {(c.last_run.wer * 100).toFixed(0)}%</span>
                        </span>
                      )}
                      <ReplayBadge replay={replays[c.id]} />
                    </div>
                    <div className="flex items-center gap-2">
                      <Button size="sm" variant="secondary" onClick={() => replay(c.id)} disabled={busyId === c.id}>
                        <Play className="h-3.5 w-3.5" aria-hidden />
                        {busyId === c.id ? "Replaying…" : "Replay"}
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => remove(c.id)} disabled={busyId === c.id}>
                        <Trash className="h-3.5 w-3.5" aria-hidden />
                        Delete
                      </Button>
                    </div>
                  </div>
                </CardBody>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
