"use client";

import { useState } from "react";
import Link from "next/link";
import { Agents } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { Badge, Button, Card, CardBody, EmptyState, PageHeader, Spinner, statusTone } from "@/components/ui";

export default function AgentsPage() {
  const agents = useApi(Agents.list);
  const [testingId, setTestingId] = useState<number | null>(null);
  const [testResult, setTestResult] = useState<string | null>(null);
  const [removing, setRemoving] = useState(false);

  async function testConnection(id: number) {
    setTestingId(id);
    setTestResult(null);
    try {
      const result = await Agents.connect(id);
      setTestResult(
        `${result.ok ? "✓ Connected" : "✗ Failed"} (${result.latency_ms ?? "?"} ms): ${result.detail}`,
      );
      agents.refetch();
    } catch (err) {
      setTestResult(err instanceof Error ? err.message : "Connection test failed");
    } finally {
      setTestingId(null);
    }
  }

  async function removeAgent(id: number) {
    if (!window.confirm("Delete this agent?")) return;
    setRemoving(true);
    try {
      await Agents.remove(id);
      agents.refetch();
    } finally {
      setRemoving(false);
    }
  }

  if (agents.loading) return <Spinner label="Loading agents…" />;

  return (
    <>
      <PageHeader
        title="Connected agents"
        subtitle="Register any voice agent via its HTTP endpoint — VoxLab adapts it into a common event format."
        actions={
          <Link href="/agents/new">
            <Button>Register agent</Button>
          </Link>
        }
      />

      {testResult && (
        <p className="mb-4 rounded-lg border border-zinc-800 bg-zinc-900 px-4 py-2.5 text-xs text-zinc-300">
          {testResult}
        </p>
      )}

      {(agents.data ?? []).length === 0 ? (
        <Card>
          <EmptyState
            title="No agents registered"
            hint="Register your first agent, or start the demo customer-support agent from agent-examples/."
          />
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {(agents.data ?? []).map((agent) => (
            <Card key={agent.id}>
              <CardBody>
                <div className="mb-2 flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h2 className="truncate text-sm font-semibold text-zinc-100">{agent.name}</h2>
                    <p className="mt-0.5 truncate font-mono text-xs text-zinc-500">{agent.endpoint}</p>
                  </div>
                  <Badge tone={statusTone(agent.connection_status)}>{agent.connection_status}</Badge>
                </div>
                {agent.description && (
                  <p className="mb-3 line-clamp-2 text-xs text-zinc-400">{agent.description}</p>
                )}
                <div className="mb-4 flex flex-wrap gap-1.5 text-[11px] text-zinc-500">
                  <span className="rounded bg-zinc-800 px-1.5 py-0.5">{agent.agent_type}</span>
                  {agent.stt_provider && <span className="rounded bg-zinc-800 px-1.5 py-0.5">STT: {agent.stt_provider}</span>}
                  {agent.llm_provider && <span className="rounded bg-zinc-800 px-1.5 py-0.5">LLM: {agent.llm_provider}</span>}
                  {agent.tts_provider && <span className="rounded bg-zinc-800 px-1.5 py-0.5">TTS: {agent.tts_provider}</span>}
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="secondary"
                    onClick={() => testConnection(agent.id)}
                    disabled={testingId === agent.id}
                  >
                    {testingId === agent.id ? "Testing…" : "Test connection"}
                  </Button>
                  <Link href={`/playground?agent=${agent.id}`}>
                    <Button variant="ghost">Open playground</Button>
                  </Link>
                  <Button variant="ghost" className="ml-auto text-zinc-500" onClick={() => removeAgent(agent.id)} disabled={removing}>
                    Delete
                  </Button>
                </div>
              </CardBody>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
