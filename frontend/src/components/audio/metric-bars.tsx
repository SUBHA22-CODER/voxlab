"use client";

import type { TranscriptMetricsReport } from "@/lib/audio-types";

/**
 * Honest metric display for transcription evaluation. Follows the existing
 * report-view bar language (dark zinc, emerald accent) but for error metrics:
 * lower is better, so the bar fill encodes the error magnitude.
 */

function pct(value: number | null | undefined): string {
  if (value === null || value === undefined) return "N/A";
  return `${(value * 100).toFixed(1)}%`;
}

function ErrorBar({
  label,
  value,
  invert = false,
  hint,
}: {
  label: string;
  value: number | null;
  invert?: boolean;
  hint?: string;
}) {
  // invert: for "higher is better" metrics (accuracy), fill = value.
  const display = invert ? (value === null ? null : 1 - value) : value;
  const width = display === null ? 0 : Math.min(100, Math.max(0, display * 100));
  const tone =
    display === null
      ? "bg-zinc-700"
      : display >= 0.5
        ? "bg-red-500/80"
        : display >= 0.2
          ? "bg-amber-500/80"
          : "bg-emerald-500/80";
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between gap-2">
        <span className="text-xs font-medium text-zinc-400">{label}</span>
        <span className="font-mono text-xs text-zinc-200">{pct(value)}</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-zinc-800">
        <div className={`h-full rounded-full ${tone} transition-[width] duration-500`} style={{ width: `${width}%` }} />
      </div>
      {hint && <p className="mt-1 text-[10px] leading-snug text-zinc-600">{hint}</p>}
    </div>
  );
}

export function AudioMetricBars({ metrics }: { metrics: TranscriptMetricsReport }) {
  const gt = metrics.ground_truth;
  return (
    <div className="grid gap-x-8 gap-y-4 sm:grid-cols-2">
      <ErrorBar
        label="Word Error Rate (WER)"
        value={gt.wer}
        hint={`${gt.wer_detail.substitutions} sub · ${gt.wer_detail.deletions} del · ${gt.wer_detail.insertions} ins / ${gt.wer_detail.reference_words} words`}
      />
      <ErrorBar label="Character Error Rate (CER)" value={gt.cer} />
      <ErrorBar
        label="Number accuracy"
        value={gt.number_accuracy}
        invert
        hint={gt.number_accuracy === null ? "no numbers in reference" : undefined}
      />
      <ErrorBar
        label="Entity accuracy"
        value={gt.entity_accuracy}
        invert
        hint={gt.entity_accuracy === null ? "no entities provided" : undefined}
      />
      <ErrorBar
        label="Technical vocabulary"
        value={gt.technical_vocab_accuracy}
        invert
        hint={gt.technical_vocab_accuracy === null ? "no vocabulary list provided" : undefined}
      />
      <ErrorBar
        label="Semantic overlap (heuristic)"
        value={metrics.heuristic.semantic_overlap_proxy}
        invert
        hint="rule-based proxy, not a ground-truth metric"
      />
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-xs text-zinc-500 sm:col-span-2">
        <span>
          Real-time factor:{" "}
          <span className="font-mono text-zinc-300">
            {gt.realtime_factor === null ? "N/A" : gt.realtime_factor.toFixed(3)}
          </span>
        </span>
        <span>
          Processing:{" "}
          <span className="font-mono text-zinc-300">
            {gt.processing_latency_seconds === null
              ? "N/A"
              : `${(gt.processing_latency_seconds * 1000).toFixed(0)} ms`}
          </span>
        </span>
        <span>
          Language:{" "}
          <span className="font-mono text-zinc-300">
            {gt.language_correct === null ? "N/A" : gt.language_correct ? "correct" : "wrong"}
          </span>
        </span>
      </div>
    </div>
  );
}
