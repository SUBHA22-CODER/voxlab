"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { Agents, getToken, wsUrl } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { Badge, Button, Card, CardBody, CardHeader, PageHeader, Select, Spinner, statusTone } from "@/components/ui";
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

  // Connect a fresh playground session when the agent (or mode) changes.
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
      // The WS reconnects on mode change; instruct the user to press again.
      setNotice("Voice mode connected — press the mic again to speak.");
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

  if (agents.loading) return <Spinner label="Loading playground…" />;

  const agent = agents.data?.find((a) => String(a.id) === effectiveAgentId);

  return (
    <>
      <PageHeader
        title="Voice Playground"
        subtitle="Talk to your agent and watch every pipeline event in real time."
        actions={
          <div className="flex items-center gap-2">
            {sessionId && (
              <Link href={`/traces/${sessionId}`} className="text-xs text-emerald-400 hover:underline">
                View session trace →
              </Link>
            )}
            <Badge tone={connected ? "green" : "red"}>{connected ? "connected" : "disconnected"}</Badge>
          </div>
        }
      />

      <Card className="mb-4">
        <CardBody className="py-3">
          <div className="flex flex-wrap items-center gap-3">
            <div className="w-64">
              <Select
                aria-label="Agent"
                value={effectiveAgentId}
                onChange={(e) => setAgentId(e.target.value)}
              >
                {(agents.data ?? []).map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </Select>
            </div>
            <div className="flex overflow-hidden rounded-lg border border-zinc-700" role="tablist" aria-label="Conversation mode">
              {(["text", "voice"] as Mode[]).map((m) => (
                <button
                  key={m}
                  role="tab"
                  aria-selected={mode === m}
                  onClick={() => setMode(m)}
                  className={`px-4 py-2 text-xs font-medium transition-colors ${
                    mode === m ? "bg-emerald-500/10 text-emerald-400" : "text-zinc-400 hover:bg-zinc-800"
                  }`}
                >
                  {m === "text" ? "Text mode" : "Voice mode"}
                </button>
              ))}
            </div>
            {agent && (
              <span className="ml-auto flex items-center gap-2 text-xs text-zinc-500">
                {agent.name}
                <Badge tone={statusTone(agent.connection_status)}>{agent.connection_status}</Badge>
              </span>
            )}
          </div>
        </CardBody>
      </Card>

      {notice && (
        <p role="status" className="mb-4 rounded-lg border border-sky-500/30 bg-sky-500/10 px-4 py-2 text-xs text-sky-300">
          {notice}
        </p>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="flex h-[540px] flex-col lg:col-span-2">
          <CardHeader>Conversation</CardHeader>
          <div ref={transcriptRef} className="flex-1 space-y-3 overflow-y-auto p-5">
            {turns.length === 0 && (
              <div className="flex h-full flex-col items-center justify-center gap-1.5 text-center">
                <p className="text-sm text-zinc-400">Start a conversation</p>
                <p className="text-xs text-zinc-600">
                  {mode === "voice"
                    ? "Press the microphone and speak. VoxLab transcribes in-browser and plays the agent's reply."
                    : "Type a message below — try “Check the status of order ORD-1001”."}
                </p>
              </div>
            )}
            {turns.map((turn, i) => (
              <div key={i} className={`flex ${turn.role === "user" ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm ${
                    turn.role === "user"
                      ? "rounded-br-sm bg-emerald-500/15 text-emerald-100"
                      : turn.error
                        ? "rounded-bl-sm border border-red-500/30 bg-red-500/10 text-red-200"
                        : "rounded-bl-sm bg-zinc-800 text-zinc-100"
                  }`}
                >
                  <p className="whitespace-pre-wrap">{turn.content}</p>
                  {turn.role === "agent" && turn.latencyMs !== undefined && (
                    <p className="mt-1 text-right font-mono text-[10px] text-zinc-500">{turn.latencyMs} ms</p>
                  )}
                </div>
              </div>
            ))}
          </div>
          <div className="border-t border-zinc-800 p-4">
            <form onSubmit={submitText} className="flex items-center gap-2">
              {mode === "voice" && (
                <button
                  type="button"
                  onClick={toggleMic}
                  aria-pressed={listening}
                  aria-label={listening ? "Stop listening" : "Start listening"}
                  className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full border transition-colors ${
                    listening
                      ? "animate-pulse border-red-500 bg-red-500/20 text-red-400"
                      : "border-zinc-700 bg-zinc-900 text-zinc-300 hover:border-zinc-600"
                  }`}
                >
                  🎤
                </button>
              )}
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={mode === "voice" ? "…or type instead" : "Type a message…"}
                aria-label="Message"
                className="flex-1 rounded-lg border border-zinc-700 bg-zinc-900 px-3.5 py-2.5 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-emerald-500 focus:outline-none"
              />
              <Button type="submit" disabled={!connected || !input.trim()}>
                Send
              </Button>
            </form>
            {mode === "voice" && !speechRecognitionAvailable() && (
              <p className="mt-2 text-[11px] text-amber-400">
                Web Speech recognition needs Chrome or Edge — typing still works.
              </p>
            )}
          </div>
        </Card>

        <Card className="h-[540px] overflow-hidden">
          <CardHeader>Live event stream</CardHeader>
          <div className="h-full space-y-1.5 overflow-y-auto p-4 font-mono text-[11px]">
            {events.length === 0 && <p className="text-zinc-600">Events appear here as the conversation runs.</p>}
            {[...events].reverse().map((event) => (
              <div key={`${event.sequence}-${event.timestamp}`} className="rounded border border-zinc-800/60 bg-zinc-900/60 px-2.5 py-1.5">
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
