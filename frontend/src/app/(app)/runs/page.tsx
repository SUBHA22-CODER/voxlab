"use client";

import { FormEvent, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { CaretRight, Play } from "@phosphor-icons/react";
import { Agents, Runs, Scenarios } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import {
  Button,
  Card,
  CardBody,
  CardHeader,
  EmptyState,
  PageHeader,
  Skeleton,
  StatusBadge,
} from "@/components/ui";
import type { Scenario } from "@/lib/types";

export default function RunsPage() {
  const router = useRouter();
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

  if (agents.loading || scenarios.loading) {
    return (
      <>
        <PageHeader title="Test runs" />
        <Skeleton className="h-72 rounded-xl" />
        <Skeleton className="mt-6 h-48 rounded-xl" />
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Test runs"
        subtitle="Benchmark an agent against selected scenarios. Every conversation is traced and scored."
      />

      <Card spotlight className="rise rise-1 mb-8">
        <CardHeader>New benchmark</CardHeader>
        <CardBody>
          <form onSubmit={startRun} className="space-y-5">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <div>
                <label
                  htmlFor="agent"
                  className="mb-1.5 block text-[11px] font-medium uppercase tracking-wider text-zinc-500"
                >
                  Agent
                </label>
                <select
                  id="agent"
                  value={effectiveAgentId}
                  onChange={(e) => setAgentId(e.target.value)}
                  className="h-9.5 w-full rounded-lg border border-zinc-800 bg-zinc-900/70 px-3 text-sm text-zinc-100 transition-colors hover:border-zinc-700 focus:border-emerald-500/60 focus:outline-none"
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
                <span className="mb-1.5 block text-[11px] font-medium uppercase tracking-wider text-zinc-500">
                  Scenarios
                </span>
                <div className="flex h-9.5 items-center gap-3 text-xs text-zinc-400">
                  <button
                    type="button"
                    className="font-medium text-emerald-400 transition-colors hover:text-emerald-300"
                    onClick={() => setSelected(new Set((scenarios.data ?? []).map((s) => s.id)))}
                  >
                    Select all
                  </button>
                  <button
                    type="button"
                    className="text-zinc-500 transition-colors hover:text-zinc-300"
                    onClick={() => setSelected(new Set())}
                  >
                    Clear
                  </button>
                  <span className="text-zinc-600">
                    <span className="font-mono tabular-nums text-zinc-300">{selected.size}</span> of{" "}
                    {(scenarios.data ?? []).length} selected
                  </span>
                </div>
              </div>
            </div>

            {grouped.map(([category, items]) => (
              <div key={category}>
                <h3 className="mb-2 text-[13px] font-medium capitalize text-zinc-300">
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
                        className={`rounded-full border px-3 py-1.5 text-xs transition-all duration-150 active:scale-[0.97] ${
                          active
                            ? "border-emerald-500/50 bg-emerald-500/10 text-emerald-300"
                            : "border-zinc-800 bg-zinc-900/60 text-zinc-400 hover:border-zinc-600 hover:text-zinc-200"
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
              <p role="alert" className="rounded-lg border border-red-500/25 bg-red-500/10 px-3 py-2 text-xs text-red-400">
                {error}
              </p>
            )}
            <div className="flex items-center gap-3 border-t border-zinc-800/60 pt-4">
              <Button type="submit" disabled={starting || !effectiveAgentId || selected.size === 0}>
                <Play size={14} weight="fill" />
                {starting ? "Starting…" : `Run benchmark`}
              </Button>
              {selected.size > 0 && (
                <span className="text-xs text-zinc-500">
                  {selected.size} scenario{selected.size === 1 ? "" : "s"} queued
                </span>
              )}
            </div>
          </form>
        </CardBody>
      </Card>

      <Card spotlight className="rise rise-2">
        <CardHeader>History</CardHeader>
        <CardBody className="p-0">
          {(runs.data ?? []).length === 0 ? (
            <EmptyState title="No runs yet" hint="Start your first benchmark above." />
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-800/80 text-left text-[11px] uppercase tracking-wider text-zinc-500">
                  <th className="px-5 py-2.5 font-medium">Run</th>
                  <th className="px-5 py-2.5 font-medium">Progress</th>
                  <th className="px-5 py-2.5 font-medium">Status</th>
                  <th className="hidden px-5 py-2.5 font-medium sm:table-cell">Started</th>
                  <th className="w-8 px-5 py-2.5" aria-label="Open" />
                </tr>
              </thead>
              <tbody>
                {(runs.data ?? []).map((run) => (
                  <tr
                    key={run.id}
                    onClick={() => router.push(`/runs/${run.id}`)}
                    className="group cursor-pointer border-b border-zinc-800/40 transition-colors last:border-0 hover:bg-zinc-800/40"
                  >
                    <td className="px-5 py-3">
                      <Link
                        href={`/runs/${run.id}`}
                        onClick={(e) => e.stopPropagation()}
                        className="font-medium text-emerald-400 transition-colors group-hover:text-emerald-300"
                      >
                        Run #{run.id}
                      </Link>
                    </td>
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-2.5">
                        <div className="h-1 w-20 overflow-hidden rounded-full bg-zinc-800">
                          <div
                            className="h-full rounded-full bg-emerald-500 transition-all duration-300"
                            style={{ width: `${run.total_sessions ? (run.progress / run.total_sessions) * 100 : 0}%` }}
                          />
                        </div>
                        <span className="tabular-nums text-xs text-zinc-400">
                          {run.progress}/{run.total_sessions}
                        </span>
                      </div>
                    </td>
                    <td className="px-5 py-3">
                      <StatusBadge status={run.status} />
                    </td>
                    <td className="hidden px-5 py-3 text-zinc-500 sm:table-cell">
                      {new Date(run.started_at).toLocaleString(undefined, {
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </td>
                    <td className="px-5 py-3 text-zinc-600 transition-colors group-hover:text-emerald-400">
                      <CaretRight size={13} className="transition-transform group-hover:translate-x-0.5" />
                    </td>
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
