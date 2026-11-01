"use client";

import {
  ArrowBendDoubleUpRight,
  Bug,
  CircleNotch,
  Microphone,
  Minus,
  Pause,
  Robot,
  Warning,
  Wrench,
} from "@phosphor-icons/react";
import type { Icon } from "@phosphor-icons/react";
import type { TraceData, VoxEvent } from "@/lib/types";

const STAGE_COLORS: Record<string, string> = {
  agent_processing: "#60a5fa",
  tool_execution: "#a78bfa",
  stt: "#34d399",
  tts: "#fbbf24",
  e2e: "#52525b",
};

const EVENT_ICONS: Record<string, { Comp: Icon; tone: string }> = {
  session_started: { Comp: CircleNotch, tone: "text-zinc-500" },
  session_ended: { Comp: CircleNotch, tone: "text-zinc-600" },
  user_message: { Comp: Microphone, tone: "text-emerald-400" },
  agent_message: { Comp: Robot, tone: "text-sky-400" },
  agent_processing: { Comp: CircleNotch, tone: "text-zinc-500" },
  tool_call: { Comp: Wrench, tone: "text-violet-400" },
  interruption: { Comp: ArrowBendDoubleUpRight, tone: "text-amber-400" },
  tool_failure_injected: { Comp: Bug, tone: "text-red-400" },
  silence: { Comp: Minus, tone: "text-zinc-500" },
  error: { Comp: Warning, tone: "text-red-400" },
  audio_received: { Comp: Microphone, tone: "text-emerald-400" },
  stt_completed: { Comp: Microphone, tone: "text-emerald-300" },
  tts_completed: { Comp: Microphone, tone: "text-amber-300" },
};

export function StageTimeline({ trace }: { trace: TraceData | null }) {
  if (!trace || trace.turns.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-zinc-500">
        No pipeline stages recorded for this session.
      </p>
    );
  }
  return (
    <div className="space-y-3.5">
      {trace.turns.map((turn) => {
        const e2e = turn.stages.find((s) => s.stage === "e2e")?.duration_ms ?? 0;
        const stages = turn.stages.filter((s) => s.stage !== "e2e");
        return (
          <div key={turn.turn} className="rounded-xl border border-zinc-800/70 bg-zinc-950/70 p-4">
            <div className="mb-2.5 flex items-center justify-between">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-zinc-500">
                Turn {turn.turn}
              </span>
              <span className="font-mono text-[11px] tabular-nums text-zinc-400">{e2e} ms e2e</span>
            </div>
            <div
              className="flex h-6 w-full overflow-hidden rounded-md bg-zinc-900"
              role="img"
              aria-label={`Turn ${turn.turn} stage durations`}
            >
              {stages.map((stage, i) => {
                const width = e2e > 0 ? Math.max((stage.duration_ms / e2e) * 100, 2) : 100 / stages.length;
                return (
                  <div
                    key={i}
                    title={`${stage.stage}: ${stage.duration_ms} ms`}
                    className="flex items-center justify-center overflow-hidden whitespace-nowrap text-[10px] font-medium text-zinc-950 transition-all"
                    style={{ width: `${width}%`, backgroundColor: STAGE_COLORS[stage.stage] ?? "#71717a" }}
                  >
                    {width > 14 ? `${stage.stage} ${stage.duration_ms}ms` : ""}
                  </div>
                );
              })}
            </div>
            <div className="mt-2.5 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-zinc-500">
              {stages.map((stage, i) => (
                <span key={i} className="flex items-center gap-1.5">
                  <span
                    aria-hidden
                    className="inline-block h-2 w-2 rounded-[3px]"
                    style={{ backgroundColor: STAGE_COLORS[stage.stage] ?? "#71717a" }}
                  />
                  <span className="font-mono">{stage.stage}</span>
                  <span className="tabular-nums">{stage.duration_ms} ms</span>
                </span>
              ))}
            </div>
          </div>
        );
      })}
      {trace.summary?.illustrative && (
        <p className="text-[11px] leading-relaxed text-zinc-600">
          Stage timings can overlap in streaming systems; totals use measured per-turn wall-clock durations.
        </p>
      )}
    </div>
  );
}

export function EventTimeline({ events }: { events: VoxEvent[] }) {
  if (events.length === 0) {
    return <p className="py-8 text-center text-sm text-zinc-500">No events recorded.</p>;
  }
  return (
    <ol className="relative space-y-0 border-l border-zinc-800/80 pl-7">
      {events.map((event) => {
        const meta = EVENT_ICONS[event.event_type];
        const isError = event.event_type === "error" || event.event_type === "tool_failure_injected";
        const Comp = meta?.Comp ?? Pause;
        const content = String(event.payload.content ?? event.payload.error ?? "");
        return (
          <li key={event.sequence} className="relative pb-4 last:pb-0">
            <span
              aria-hidden
              className={`absolute -left-[35px] flex h-[22px] w-[22px] items-center justify-center rounded-full border bg-zinc-950 ${
                isError ? "border-red-500/40 text-red-400" : `border-zinc-800 ${meta?.tone ?? "text-zinc-500"}`
              }`}
            >
              <Comp size={11} weight="bold" />
            </span>
            <div className="flex items-baseline justify-between gap-3">
              <p className={`text-xs font-semibold ${isError ? "text-red-400" : "text-zinc-300"}`}>
                {event.event_type.replace(/_/g, " ")}
              </p>
              <p className="shrink-0 font-mono text-[10px] tabular-nums text-zinc-600">
                {new Date(event.timestamp).toLocaleTimeString()}
                {event.duration_ms !== null ? ` · ${event.duration_ms} ms` : ""}
              </p>
            </div>
            {content && (
              <p className="mt-1 whitespace-pre-wrap rounded-lg bg-zinc-900/50 px-3 py-1.5 text-xs leading-relaxed text-zinc-400">
                {content.slice(0, 300)}
                {content.length > 300 ? "…" : ""}
              </p>
            )}
            {event.event_type === "tool_call" && event.payload.name !== undefined && (
              <p className="mt-1 font-mono text-[11px] text-zinc-500">
                {String(event.payload.name)} ({String(event.payload.status)})
              </p>
            )}
          </li>
        );
      })}
    </ol>
  );
}
