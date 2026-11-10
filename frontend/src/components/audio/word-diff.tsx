"use client";

import { Info } from "@phosphor-icons/react";

import type { AlignmentView } from "@/lib/audio-types";

/**
 * Word-level error localization (VoxLab 2.5 Phase 4): renders the aligned
 * token stream. Green = correct, red = substitution, amber = insertion,
 * strikethrough gray = deletion. Timestamps appear ONLY when the engine
 * provided word timings; the absence is stated, never faked.
 */

const OP_STYLES: Record<string, string> = {
  correct: "bg-transparent text-zinc-300",
  substitution: "bg-red-500/15 text-red-200 border border-red-500/30",
  insertion: "bg-amber-500/15 text-amber-200 border border-amber-500/30",
  deletion: "bg-zinc-800 text-zinc-500 border border-zinc-700 line-through",
};

const OP_LABELS: Record<string, string> = {
  correct: "correct",
  substitution: "substituted",
  insertion: "inserted",
  deletion: "missing",
};

export function WordDiff({ alignment }: { alignment: AlignmentView }) {
  const hasTimings = alignment.tokens.some((t) => t.start_seconds !== null);
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-1.5">
        {alignment.tokens.map((token, i) => (
          <span
            key={i}
            title={`${OP_LABELS[token.operation]}${token.explanation ? `: ${token.explanation}` : ""}${
              token.start_seconds !== null
                ? ` · ${token.start_seconds.toFixed(2)}s–${(token.end_seconds ?? 0).toFixed(2)}s`
                : ""
            }${token.confidence !== null && token.confidence !== undefined ? ` · p=${token.confidence.toFixed(2)}` : ""}`}
            className={`rounded-md px-1.5 py-0.5 text-[13px] leading-relaxed ${OP_STYLES[token.operation] ?? ""}`}
          >
            {token.operation === "deletion"
              ? token.ref_word
              : token.operation === "insertion"
                ? token.hyp_word
                : (token.hyp_word ?? token.ref_word)}
          </span>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-zinc-500">
        <span className="flex items-center gap-1">
          <span className="h-2 w-2 rounded-sm border border-red-500/40 bg-red-500/15" /> substituted
        </span>
        <span className="flex items-center gap-1">
          <span className="h-2 w-2 rounded-sm border border-amber-500/40 bg-amber-500/15" /> inserted
        </span>
        <span className="flex items-center gap-1">
          <span className="h-2 w-2 rounded-sm border border-zinc-700 bg-zinc-800" /> missing
        </span>
        <span className="font-mono">
          {alignment.counts.correct} correct · {alignment.counts.substitutions} sub ·{" "}
          {alignment.counts.insertions} ins · {alignment.counts.deletions} del
        </span>
        <span className="flex items-center gap-1">
          <Info className="h-3 w-3" aria-hidden />
          {hasTimings
            ? "word timings from the engine"
            : "no word timings (enable word_timestamps in the engine config)"}
        </span>
      </div>
    </div>
  );
}
