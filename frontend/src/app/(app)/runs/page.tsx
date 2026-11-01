"use client";

import { FormEvent, useMemo, useState } from "react";
import Link from "next/link";
import { Agents, Runs, Scenarios } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import {
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  EmptyState,
  PageHeader,
  Spinner,
  statusTone,
} from "@/components/ui";
import type { Scenario } from "@/lib/types";

export default function RunsPage() {
  const agents = useApi(Agents.list);
  const scenarios = useApi(Scenarios.list);
  const runs = useApi(Runs.list, { pollMs: 4000 });

  const [agentId, setAgentId] = useState<string>("");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const grouped = useMemo(() => {
    const map = new Map<string, Scenario[]>();
    for (const s of scenarios.data ?? []) {
      const list = map.get(s.category) ?? [];
      list.push(s);
      map.set(s.category, list);
    }
    return [...map.entries()];
  }, [scenarios.data]);

  const connectedAgent = agents.data?.find((a) => String(a.id) === agentId) ?? agents.data?.[0];
  const effectiveAgentId = agentId || (connectedAgent ? String(connectedAgent.id) : "");

  function toggleScenario(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function startRun(event: FormEvent) {
    event.preventDefault();
    if (!effectiveAgentId || selected.size === 0) return;
    setStarting(true);
    setError(null);
    try {
      const run = await Runs.create({
        agent_id: Number(effectiveAgentId),
        scenario_ids: [...selected],
      });
      window.location.href = `/runs/${run.id}`;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start run");
    } finally {
      setStarting(false);
    }
  }

  if (agents.loading || scenarios.loading) return <Spinner label="Loading…" />;

  return (
    <>
      <PageHeader
        title="Test runs"
        subtitle="Benchmark an agent against selected scenarios. Every conversation is traced and scored."
      />

      <Card className="mb-8">
        <CardHeader>New benchmark</CardHeader>
        <CardBody>
          <form onSubmit={startRun} className="space-y-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <div className="sm:col-span-1">
                <label htmlFor="agent" className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-zinc-400">
                  Agent
                </label>
                <select
                  id="agent"
                  value={effectiveAgentId}
                  onChange={(e) => setAgentId(e.target.value)}
                  className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 focus:border-emerald-500 focus:outline-none"
                  required
                >
                  {(agents.data ?? []).map((agent) => (
                    <option key={agent.id} value={agent.id}>
                      {agent.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="sm:col-span-2">
                <span className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-zinc-400">
                  Selected: {selected.size} scenario{selected.size === 1 ? "" : "s"}
                </span>
                <div className="flex flex-wrap gap-2 pt-1">
                  <Button
                    type="button"
                    variant="ghost"
                    className="text-xs"
                    onClick={() => setSelected(new Set((scenarios.data ?? []).map((s) => s.id)))}
                  >
                    Select all
                  </Button>
                  <Button type="button" variant="ghost" className="text-xs" onClick={() => setSelected(new Set())}>
                    Clear
                  </Button>
                </div>
              </div>
            </div>

            {grouped.map(([category, items]) => (
              <div key={category}>
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-widest text-zinc-500">
                  {category.replace(/_/g, " ")}
                </h3>
                <div className="flex flex-wrap gap-2">
                  {items.map((scenario) => {
                    const active = selected.has(scenario.id);
                    return (
                      <button
                        type="button"
                        key={scenario.id}
                        onClick={() => toggleScenario(scenario.id)}
                        aria-pressed={active}
                        className={`rounded-full border px-3 py-1.5 text-xs transition-colors ${
                          active
                            ? "border-emerald-500/50 bg-emerald-500/10 text-emerald-300"
                            : "border-zinc-700 bg-zinc-900 text-zinc-400 hover:border-zinc-600"
                        }`}
                      >
                        {scenario.name}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}

            {error && (
              <p role="alert" className="rounded-lg bg-red-500/10 px-3 py-2 text-xs text-red-400">
                {error}
              </p>
            )}
            <Button type="submit" disabled={starting || !effectiveAgentId || selected.size === 0}>
              {starting ? "Starting…" : `Run benchmark (${selected.size} scenarios)`}
            </Button>
          </form>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>History</CardHeader>
        <CardBody className="p-0">
          {(runs.data ?? []).length === 0 ? (
            <EmptyState title="No runs yet" hint="Start your first benchmark above." />
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-800 text-left text-xs uppercase tracking-wide text-zinc-500">
                  <th className="px-5 py-3 font-medium">Run</th>
                  <th className="px-5 py-3 font-medium">Progress</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Started</th>
                </tr>
              </thead>
              <tbody>
                {(runs.data ?? []).map((run) => (
                  <tr key={run.id} className="border-b border-zinc-800/50 last:border-0 hover:bg-zinc-900/50">
                    <td className="px-5 py-3">
                      <Link href={`/runs/${run.id}`} className="text-emerald-400 hover:underline">
                        Run #{run.id}
                      </Link>
                    </td>
                    <td className="px-5 py-3 text-zinc-300">
                      {run.progress}/{run.total_sessions}
                    </td>
                    <td className="px-5 py-3">
                      <Badge tone={statusTone(run.status)}>{run.status}</Badge>
                      {run.error && <span className="ml-2 text-xs text-red-400">{run.error.slice(0, 60)}</span>}
                    </td>
                    <td className="px-5 py-3 text-zinc-500">{new Date(run.started_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardBody>
      </Card>
    </>
  );
}
