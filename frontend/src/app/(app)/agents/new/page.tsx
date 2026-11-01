"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { Agents } from "@/lib/api";
import { Button, Card, CardBody, CardHeader, Input, Label, PageHeader, Select, Textarea } from "@/components/ui";

export default function NewAgentPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [endpoint, setEndpoint] = useState("http://localhost:8100/conversation");
  const [agentType, setAgentType] = useState<"http" | "websocket">("http");
  const [sttProvider, setSttProvider] = useState("");
  const [llmProvider, setLlmProvider] = useState("");
  const [ttsProvider, setTtsProvider] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const agent = await Agents.create({
        name,
        description,
        endpoint,
        agent_type: agentType,
        stt_provider: sttProvider,
        llm_provider: llmProvider,
        tts_provider: ttsProvider,
        config: { timeout_s: 30 },
      });
      router.push(`/agents`);
      // Fire-and-forget first connection test.
      void Agents.connect(agent.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Register an agent"
        subtitle="Point VoxLab at your agent's conversation endpoint. No rebuild required — the adapter handles the rest."
      />
      <div className="max-w-2xl">
        <Card>
          <CardHeader>Agent details</CardHeader>
          <CardBody>
            <form onSubmit={onSubmit} className="space-y-4">
              <div>
                <Label htmlFor="name">Agent name</Label>
                <Input id="name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Customer Support Agent" required />
              </div>
              <div>
                <Label htmlFor="description">Description</Label>
                <Textarea
                  id="description"
                  rows={2}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="What does this agent do?"
                />
              </div>
              <div>
                <Label htmlFor="endpoint">Conversation endpoint</Label>
                <Input
                  id="endpoint"
                  type="url"
                  value={endpoint}
                  onChange={(e) => setEndpoint(e.target.value)}
                  placeholder="https://your-agent.example.com/conversation"
                  required
                />
                <p className="mt-1.5 text-xs text-zinc-500">
                  Must accept POST {"{session_id, message, metadata}"} and return{" "}
                  {"{reply, tool_calls, state, timings}"}. See docs/api-reference.md.
                </p>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="type">Connection type</Label>
                  <Select
                    id="type"
                    value={agentType}
                    onChange={(e) => setAgentType(e.target.value === "websocket" ? "websocket" : "http")}
                  >
                    <option value="http">HTTP request/response</option>
                    <option value="websocket">WebSocket streaming</option>
                  </Select>
                </div>
                <div>
                  <Label htmlFor="llm">LLM provider (optional)</Label>
                  <Input id="llm" value={llmProvider} onChange={(e) => setLlmProvider(e.target.value)} placeholder="openai, glm, groq…" />
                </div>
                <div>
                  <Label htmlFor="stt">STT provider (optional)</Label>
                  <Input id="stt" value={sttProvider} onChange={(e) => setSttProvider(e.target.value)} placeholder="deepgram, whisper…" />
                </div>
                <div>
                  <Label htmlFor="tts">TTS provider (optional)</Label>
                  <Input id="tts" value={ttsProvider} onChange={(e) => setTtsProvider(e.target.value)} placeholder="elevenlabs, azure…" />
                </div>
              </div>
              {error && (
                <p role="alert" className="rounded-lg bg-red-500/10 px-3 py-2 text-xs text-red-400">
                  {error}
                </p>
              )}
              <div className="flex gap-2">
                <Button type="submit" disabled={busy}>
                  {busy ? "Registering…" : "Register agent"}
                </Button>
                <Button type="button" variant="ghost" onClick={() => router.back()}>
                  Cancel
                </Button>
              </div>
            </form>
          </CardBody>
        </Card>
      </div>
    </>
  );
}
