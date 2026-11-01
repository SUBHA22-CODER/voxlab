"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { ArrowSquareOut, PaperPlaneRight, Microphone, TextAa, Robot } from "@phosphor-icons/react";
import { Agents, getToken, wsUrl } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { Button, Card, CardBody, CardHeader, EmptyState, PageHeader, Select, Skeleton, StatusBadge } from "@/components/ui";
import { speak, speechRecognitionAvailable, startRecognition, stopSpeaking, type RecognitionHandle } from "@/lib/speech";

interface Turn {
  role: "user" | "agent";
  content: string;
  latencyMs?: number;
  kind?: string;
  error?: string | null;
}

interface WireEvent {
  sequence: number;
  event_type: string;
  timestamp: string;
  duration_ms: number | null;
  payload: Record<string, unknown>;
}

type Mode = "text" | "voice";

export default function PlaygroundPage() {
  const searchParams = useSearchParams();
  const agents = useApi(Agents.list);

  const requested = searchParams.get("agent");
  const [agentId, setAgentId] = useState<string>(requested ?? "");
  const effectiveAgentId = agentId || (agents.data?.length ? String(agents.data[0].id) : "");

  const [mode, setMode] = useState<Mode>("text");
  const [connected, setConnected] = useState(false);
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [events, setEvents] = useState<WireEvent[]>([]);
  const [input, setInput] = useState("");
  const [listening, setListening] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const recognitionRef = useRef<RecognitionHandle | null>(null);
  const audioStartRef = useRef<number>(0);
  const transcriptRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!effectiveAgentId) return;
    const token = getToken();
    if (!token) return;

    setConnected(false);
    setSessionId(null);
    setTurns([]);
    setEvents([]);
    setNotice(null);

    const ws = new WebSocket(wsUrl(`/ws/playground/${effectiveAgentId}?token=${token}`));
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onmessage = (message) => {
      const frame = JSON.parse(message.data as string);
      if (frame.type === "session_started") {
        setSessionId(frame.session_id);
      } else if (frame.type === "agent_message") {
        setTurns((prev) => [
          ...prev,
          {
            role: "agent",
            content: frame.content || (frame.error ? `(agent error: ${frame.error})` : "(empty reply)"),
            latencyMs: frame.latency_ms,
            error: frame.error,
          },
        ]);
        setEvents((prev) => [...prev, ...(frame.events ?? [])]);
        if (mode === "voice" && frame.content) speak(frame.content);
      } else if (frame.type === "error") {
        setNotice(frame.message);
      }
    };
    ws.onclose = () => setConnected(false);

    return () => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "stop" }));
      }
      ws.close();
      wsRef.current = null;
    };
  }, [effectiveAgentId, mode]);

  useEffect(() => {
    transcriptRef.current?.scrollTo({ top: transcriptRef.current.scrollHeight });
  }, [turns]);

  const sendText = useCallback(
    (content: string, kind: "text" | "voice" = "text", sttMs?: number, audioMs?: number) => {
      const ws = wsRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN || !content) return;
      setTurns((prev) => [...prev, { role: "user", content, kind }]);
      ws.send(
        JSON.stringify(
          kind === "voice"
            ? { type: "voice_transcript", content, stt_ms: sttMs ?? 0, audio_ms: audioMs ?? 0 }
            : { type: "text_message", content },
        ),
      );
    },
    [],
  );

  function submitText(event: React.FormEvent) {
    event.preventDefault();
    if (!input.trim()) return;
    sendText(input.trim());
    setInput("");
  }

  function toggleMic() {
    if (listening) {
      recognitionRef.current?.stop();
      recognitionRef.current = null;
      setListening(false);
      return;
    }
    if (mode !== "voice") {
      setMode("voice");
      setNotice("Voice mode connected. Press the microphone again to speak.");
      return;
    }
    stopSpeaking();
    audioStartRef.current = performance.now();
    const handle = startRecognition(
      (transcript, sttMs) => {
        const audioMs = Math.round(performance.now() - audioStartRef.current);
        sendText(transcript, "voice", sttMs, audioMs);
        setListening(false);
        recognitionRef.current = null;
      },
      (message) => {
        setNotice(message);
        setListening(false);
        recognitionRef.current = null;
      },
    );
    if (handle) {
      recognitionRef.current = handle;
      setListening(true);
    }
  }

  if (agents.loading) {
    return (
      <>
        <PageHeader title="Voice Playground" />
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <Skeleton className="h-[560px] rounded-xl lg:col-span-2" />
          <Skeleton className="h-[560px] rounded-xl" />
        </div>
      </>
    );
  }

  const agent = agents.data?.find((a) => String(a.id) === effectiveAgentId);

  return (
    <>
      <PageHeader
        title="Voice Playground"
        subtitle="Talk to your agent and watch every pipeline event in real time."
        actions={
          <div className="flex items-center gap-2.5">
            {sessionId && (
              <Link
                href={`/traces/${sessionId}`}
                className="flex items-center gap-1.5 text-xs text-emerald-400 transition-colors hover:text-emerald-300"
              >
                Session trace <ArrowSquareOut size={12} />
              </Link>
            )}
            <StatusBadge status={connected ? "connected" : "unreachable"} />
          </div>
        }
      />

      <Card className="mb-4">
        <CardBody className="flex flex-wrap items-center gap-3 py-3">
          <div className="w-56">
            <Select aria-label="Agent" value={effectiveAgentId} onChange={(e) => setAgentId(e.target.value)}>
              {(agents.data ?? []).map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </Select>
          </div>
          <div className="flex overflow-hidden rounded-lg border border-zinc-800" role="tablist" aria-label="Conversation mode">
            {(
              [
                { id: "text", label: "Text", Icon: TextAa },
                { id: "voice", label: "Voice", Icon: Microphone },
              ] as const
            ).map(({ id, label, Icon }) => (
              <button
                key={id}
                role="tab"
                aria-selected={mode === id}
                onClick={() => setMode(id)}
                className={`flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium transition-colors ${
                  mode === id ? "bg-emerald-500/10 text-emerald-300" : "text-zinc-500 hover:bg-zinc-800/60 hover:text-zinc-300"
                }`}
              >
                <Icon size={13} weight={mode === id ? "fill" : "regular"} />
                {label}
              </button>
            ))}
          </div>
          {agent && <span className="ml-auto truncate font-mono text-[11px] text-zinc-600">{agent.endpoint}</span>}
        </CardBody>
      </Card>

      {notice && (
        <p
          role="status"
          className="mb-4 rounded-lg border border-sky-500/25 bg-sky-500/[0.06] px-4 py-2 text-xs text-sky-300"
        >
          {notice}
        </p>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card spotlight className="flex h-[560px] flex-col lg:col-span-2">
          <CardHeader>Conversation</CardHeader>
          <div ref={transcriptRef} className="flex-1 space-y-3 overflow-y-auto p-5">
            {turns.length === 0 && (
              <EmptyState
                icon={<Robot size={20} weight="duotone" />}
                title="Start a conversation"
                hint={
                  mode === "voice"
                    ? "Press the microphone and speak. VoxLab transcribes in your browser and plays the agent's reply."
                    : "Try “Check the status of order ORD-1001” to see tools, latency and tracing in action."
                }
              />
            )}
            {turns.map((turn, i) => (
              <div key={i} className={`flex ${turn.role === "user" ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                    turn.role === "user"
                      ? "rounded-br-md border border-emerald-500/20 bg-emerald-500/10 text-emerald-100"
                      : turn.error
                        ? "rounded-bl-md border border-red-500/25 bg-red-500/[0.06] text-red-200"
                        : "rounded-bl-md border border-zinc-800 bg-zinc-800/60 text-zinc-100"
                  }`}
                >
                  <p className="whitespace-pre-wrap">{turn.content}</p>
                  {turn.role === "agent" && turn.latencyMs !== undefined && (
                    <p className="mt-1.5 text-right font-mono text-[10px] tabular-nums text-zinc-500">
                      {turn.latencyMs} ms
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
          <div className="border-t border-zinc-800/80 p-4">
            <form onSubmit={submitText} className="flex items-center gap-2.5">
              {mode === "voice" && (
                <button
                  type="button"
                  onClick={toggleMic}
                  aria-pressed={listening}
                  aria-label={listening ? "Stop listening" : "Start listening"}
                  className={`relative flex h-10 w-10 shrink-0 items-center justify-center rounded-full border transition-all ${
                    listening
                      ? "border-red-500/60 bg-red-500/15 text-red-400"
                      : "border-zinc-700 bg-zinc-900 text-zinc-300 hover:border-zinc-600 hover:text-zinc-100"
                  }`}
                >
                  {listening && (
                    <span
                      aria-hidden
                      className="live-dot absolute inset-0 rounded-full border border-red-500/40"
                    />
                  )}
                  <Microphone size={16} weight={listening ? "fill" : "regular"} />
                </button>
              )}
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={mode === "voice" ? "…or type instead" : "Type a message"}
                aria-label="Message"
                className="h-10 flex-1 rounded-lg border border-zinc-800 bg-zinc-900/70 px-3.5 text-sm text-zinc-100 placeholder:text-zinc-600 transition-colors hover:border-zinc-700 focus:border-emerald-500/60 focus:outline-none focus:ring-2 focus:ring-emerald-500/20"
              />
              <Button type="submit" disabled={!connected || !input.trim()} className="h-10 px-3.5">
                <PaperPlaneRight size={15} weight="fill" />
                <span className="max-[420px]:hidden">Send</span>
              </Button>
            </form>
            {mode === "voice" && !speechRecognitionAvailable() && (
              <p className="mt-2 text-[11px] text-amber-400">
                Web Speech recognition needs Chrome or Edge. Typing still works everywhere.
              </p>
            )}
          </div>
        </Card>

        <Card className="h-[560px] overflow-hidden">
          <CardHeader>Live event stream</CardHeader>
          <div className="h-[calc(100%-53px)] space-y-1.5 overflow-y-auto p-4 font-mono text-[11px]">
            {events.length === 0 && (
              <p className="py-6 text-center text-zinc-600">Events appear here as the conversation runs.</p>
            )}
            {[...events].reverse().map((event) => (
              <div
                key={`${event.sequence}-${event.timestamp}`}
                className="rounded-lg border border-zinc-800/50 bg-zinc-900/50 px-2.5 py-1.5"
              >
                <span className={event.event_type === "error" ? "text-red-400" : "text-emerald-400"}>
                  {event.event_type}
                </span>
                {event.duration_ms !== null && <span className="text-zinc-500"> · {event.duration_ms}ms</span>}
                {event.payload.content !== undefined && (
                  <p className="truncate text-zinc-500">{String(event.payload.content).slice(0, 80)}</p>
                )}
              </div>
            ))}
          </div>
        </Card>
      </div>
    </>
  );
}
