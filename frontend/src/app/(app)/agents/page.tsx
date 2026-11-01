"use client";

import { useState } from "react";
import Link from "next/link";
import { Play, PlugsConnected, Plus, Robot as RobotIcon, Trash } from "@phosphor-icons/react";
import { Agents } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { Button, Card, CardBody, EmptyState, PageHeader, Skeleton, StatusBadge } from "@/components/ui";

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
        `${result.ok ? "Connected" : "Failed"} (${result.latency_ms ?? "?"} ms): ${result.detail}`,
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

  if (agents.loading) {
    return (
      <>
        <PageHeader title="Connected agents" />
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {[0, 1].map((i) => (
            <Skeleton key={i} className="h-44 rounded-xl" />
          ))}
        </div>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Connected agents"
        subtitle="Register any voice agent via its conversation endpoint. VoxLab adapts it into a common event format, no rebuild required."
        actions={
          <Link href="/agents/new">
            <Button size="sm">
              <Plus size={14} weight="bold" />
              Register agent
            </Button>
          </Link>
        }
      />

      {testResult && (
        <p className="mb-4 rounded-lg border border-zinc-800 bg-zinc-900/70 px-4 py-2.5 font-mono text-xs text-zinc-300">
          {testResult}
        </p>
      )}

      {(agents.data ?? []).length === 0 ? (
        <Card>
          <EmptyState
            icon={<RobotIcon />}
            title="No agents registered"
            hint="Register your first agent, or start the bundled demo customer-support agent from agent-examples/."
            action={
              <Link href="/agents/new">
                <Button size="sm" variant="secondary">
                  <Plus size={14} weight="bold" />
                  Register agent
                </Button>
              </Link>
            }
          />
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {(agents.data ?? []).map((agent) => (
            <Card key={agent.id} className="transition-colors duration-200 hover:border-zinc-700">
              <CardBody>
                <div className="mb-2.5 flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h2 className="truncate text-sm font-semibold text-zinc-100">{agent.name}</h2>
                    <p className="mt-1 truncate font-mono text-[11px] text-zinc-500">{agent.endpoint}</p>
                  </div>
                  <StatusBadge status={agent.connection_status} />
                </div>
                {agent.description && (
                  <p className="mb-3 line-clamp-2 text-xs leading-relaxed text-zinc-400">{agent.description}</p>
                )}
                <div className="mb-4 flex flex-wrap gap-1.5 font-mono text-[10px] text-zinc-500">
                  <span className="rounded border border-zinc-800 bg-zinc-900 px-1.5 py-0.5">{agent.agent_type}</span>
                  {agent.stt_provider && (
                    <span className="rounded border border-zinc-800 bg-zinc-900 px-1.5 py-0.5">stt {agent.stt_provider}</span>
                  )}
                  {agent.llm_provider && (
                    <span className="rounded border border-zinc-800 bg-zinc-900 px-1.5 py-0.5">llm {agent.llm_provider}</span>
                  )}
                  {agent.tts_provider && (
                    <span className="rounded border border-zinc-800 bg-zinc-900 px-1.5 py-0.5">tts {agent.tts_provider}</span>
                  )}
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => testConnection(agent.id)}
                    disabled={testingId === agent.id}
                  >
                    <PlugsConnected size={13} />
                    {testingId === agent.id ? "Testing…" : "Test connection"}
                  </Button>
                  <Link href={`/playground?agent=${agent.id}`}>
                    <Button variant="ghost" size="sm">
                      <Play size={13} />
                      Playground
                    </Button>
                  </Link>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="ml-auto text-zinc-600 hover:text-red-400"
                    onClick={() => removeAgent(agent.id)}
                    disabled={removing}
                    aria-label={`Delete ${agent.name}`}
                  >
                    <Trash size={13} />
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
