"use client";

import type { TraceData, VoxEvent } from "@/lib/types";

const STAGE_COLORS: Record<string, string> = {
  agent_processing: "#60a5fa",
  tool_execution: "#a78bfa",
  stt: "#34d399",
  tts: "#fbbf24",
  e2e: "#52525b",
};

const EVENT_ICONS: Record<string, string> = {
  session_started: "▶",
  session_ended: "■",
  user_message: "👤",
  agent_message: "🤖",
  agent_processing: "⏳",
  tool_call: "🔧",
  interruption: "⚡",
  tool_failure_injected: "⚑",
  silence: "…",
  error: "✗",
  audio_received: "🎤",
  stt_completed: "📝",
  tts_completed: "🔊",
};

const ERROR_EVENTS = new Set(["error", "tool_failure_injected"]);

export function StageTimeline({ trace }: { trace: TraceData | null }) {
  if (!trace || trace.turns.length === 0) {
    return <p className="py-6 text-center text-sm text-zinc-500">No pipeline stages recorded for this session.</p>;
  }
  return (
    <div className="space-y-4">
      {trace.turns.map((turn) => {
        const e2e = turn.stages.find((s) => s.stage === "e2e")?.duration_ms ?? 0;
        return (
          <div key={turn.turn} className="rounded-lg border border-zinc-800 bg-zinc-950 p-4">
            <div className="mb-2.5 flex items-center justify-between text-xs">
              <span className="font-semibold uppercase tracking-widest text-zinc-500">Turn {turn.turn}</span>
              <span className="font-mono text-zinc-400">e2e {e2e} ms</span>
            </div>
            <div className="flex h-6 w-full overflow-hidden rounded-md bg-zinc-900" role="img" aria-label={`Turn ${turn.turn} stage durations`}>
              {turn.stages
                .filter((s) => s.stage !== "e2e")
                .map((stage, i) => {
                  const width = e2e > 0 ? Math.max((stage.duration_ms / e2e) * 100, 2) : 100 / turn.stages.length;
                  return (
                    <div
                      key={i}
                      title={`${stage.stage}: ${stage.duration_ms} ms`}
                      className="flex items-center justify-center overflow-hidden whitespace-nowrap text-[10px] font-medium text-zinc-950"
                      style={{ width: `${width}%`, backgroundColor: STAGE_COLORS[stage.stage] ?? "#71717a" }}
                    >
                      {width > 12 ? `${stage.stage} ${stage.duration_ms}ms` : ""}
                    </div>
                  );
                })}
            </div>
            <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-zinc-500">
              {turn.stages
                .filter((s) => s.stage !== "e2e")
                .map((stage, i) => (
                  <span key={i} className="flex items-center gap-1.5">
                    <span
                      aria-hidden
                      className="inline-block h-2 w-2 rounded-full"
                      style={{ backgroundColor: STAGE_COLORS[stage.stage] ?? "#71717a" }}
                    />
                    {stage.stage}: {stage.duration_ms} ms
                  </span>
                ))}
            </div>
          </div>
        );
      })}
      {trace.summary?.illustrative && (
        <p className="text-[11px] text-zinc-600">
          Stage timings can overlap in streaming systems; totals use measured per-turn wall-clock durations.
        </p>
      )}
    </div>
  );
}

export function EventTimeline({ events }: { events: VoxEvent[] }) {
  if (events.length === 0) {
    return <p className="py-6 text-center text-sm text-zinc-500">No events recorded.</p>;
  }
  return (
    <ol className="relative space-y-0 border-l border-zinc-800 pl-6">
      {events.map((event) => {
        const isError = ERROR_EVENTS.has(event.event_type);
        const content = String(event.payload.content ?? event.payload.error ?? "");
        return (
          <li key={event.sequence} className="relative pb-4">
            <span
              aria-hidden
              className={`absolute -left-[31px] flex h-5 w-5 items-center justify-center rounded-full border text-[10px] ${
                isError
                  ? "border-red-500/40 bg-red-500/10 text-red-400"
                  : "border-zinc-700 bg-zinc-900 text-zinc-400"
              }`}
            >
              {EVENT_ICONS[event.event_type] ?? "•"}
            </span>
            <div className="flex items-baseline justify-between gap-3">
              <p className={`text-xs font-semibold ${isError ? "text-red-400" : "text-zinc-300"}`}>
                {event.event_type.replace(/_/g, " ")}
              </p>
              <p className="shrink-0 font-mono text-[10px] text-zinc-600">
                {new Date(event.timestamp).toLocaleTimeString()}
                {event.duration_ms !== null ? ` · ${event.duration_ms} ms` : ""}
              </p>
            </div>
            {content && (
              <p className="mt-1 whitespace-pre-wrap rounded-lg bg-zinc-900/70 px-3 py-1.5 text-xs text-zinc-400">
                {content.slice(0, 300)}
                {content.length > 300 ? "…" : ""}
              </p>
            )}
            {event.event_type === "tool_call" && event.payload.name !== undefined && (
              <p className="mt-1 font-mono text-[11px] text-zinc-500">
                {String(event.payload.name)} → {String(event.payload.status)}
              </p>
            )}
          </li>
        );
      })}
    </ol>
  );
}
