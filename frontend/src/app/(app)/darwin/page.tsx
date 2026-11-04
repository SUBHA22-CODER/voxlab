"use client";

import { FormEvent, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { CaretRight, Dna, Play, Sparkle, Warning } from "@phosphor-icons/react";
import { Agents, Darwin } from "@/lib/api";
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

export default function DarwinPage() {
  const router = useRouter();
  const agents = useApi(Agents.list);
  const personas = useApi(Darwin.personas);
  const runs = useApi(Darwin.listRuns, { pollMs: 3000 });

  const [agentId, setAgentId] = useState<string>("");
  const [popSize, setPopSize] = useState<number>(6);
  const [generations, setGenerations] = useState<number>(5);
  const [selectedPersonas, setSelectedPersonas] = useState<Set<string>>(
    new Set(["self_corrector", "filler_heavy_rambler", "command_vs_dictation_confuser", "jargon_and_names_speaker"])
  );
  const [seed, setSeed] = useState<number>(42);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const connectedAgent =
    agents.data?.find((a) => String(a.id) === agentId) ??
    agents.data?.find((a) => a.name.toLowerCase().includes("wispr")) ??
    agents.data?.[0];
  const effectiveAgentId = agentId || (connectedAgent ? String(connectedAgent.id) : "");

  const plannedSessions = popSize * generations;
  const isOverBudget = plannedSessions > 60;

  function togglePersona(id: string) {
    setSelectedPersonas((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function startDarwin(event: FormEvent) {
    event.preventDefault();
    if (!effectiveAgentId || selectedPersonas.size === 0) return;
    setStarting(true);
    setError(null);
    try {
      const run = await Darwin.createRun({
        agent_id: Number(effectiveAgentId),
        population_size: popSize,
        generations: generations,
        personas: [...selectedPersonas],
        seed: seed,
      });
      router.push(`/darwin/${run.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start Darwin run");
    } finally {
      setStarting(false);
    }
  }

  if (agents.loading || personas.loading) {
    return (
      <>
        <PageHeader title="Darwin Fuzzing" />
        <Skeleton className="h-72 rounded-xl" />
        <Skeleton className="mt-6 h-48 rounded-xl" />
      </>
    );
  }

  return (
    <>
      <PageHeader
        title={
          <span className="flex items-center gap-2.5">
            <Dna size={26} className="text-emerald-400" weight="duotone" />
            Darwin — Voice & Dictation Fuzzing
          </span>
        }
        subtitle="Automated evolutionary stress-testing tailored for Wispr Flow. Breeds adversarial personas to discover failure boundaries."
      />

      <Card spotlight className="rise rise-1 mb-8">
        <CardHeader className="flex items-center justify-between">
          <span>New Evolutionary Fuzzing Campaign</span>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5 text-[11px] font-medium text-emerald-300">
            <Sparkle size={12} weight="fill" /> Wispr Flow Optimized
          </span>
        </CardHeader>
        <CardBody>
          <form onSubmit={startDarwin} className="space-y-6">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
              <div className="sm:col-span-2">
                <label
                  htmlFor="agent"
                  className="mb-1.5 block text-[11px] font-medium uppercase tracking-wider text-zinc-500"
                >
                  Target Voice / Dictation Agent
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

              <div>
                <label
                  htmlFor="population"
                  className="mb-1.5 block text-[11px] font-medium uppercase tracking-wider text-zinc-500"
                >
                  Population Size
                </label>
                <input
                  id="population"
                  type="number"
                  min={2}
                  max={20}
                  value={popSize}
                  onChange={(e) => setPopSize(Number(e.target.value))}
                  className="h-9.5 w-full rounded-lg border border-zinc-800 bg-zinc-900/70 px-3 text-sm text-zinc-100 focus:border-emerald-500/60 focus:outline-none"
                />
              </div>

              <div>
                <label
                  htmlFor="generations"
                  className="mb-1.5 block text-[11px] font-medium uppercase tracking-wider text-zinc-500"
                >
                  Generations
                </label>
                <input
                  id="generations"
                  type="number"
                  min={1}
                  max={15}
                  value={generations}
                  onChange={(e) => setGenerations(Number(e.target.value))}
                  className="h-9.5 w-full rounded-lg border border-zinc-800 bg-zinc-900/70 px-3 text-sm text-zinc-100 focus:border-emerald-500/60 focus:outline-none"
                />
              </div>
            </div>

            <div>
              <div className="mb-2 flex items-center justify-between">
                <span className="text-[11px] font-medium uppercase tracking-wider text-zinc-500">
                  Attack Personas (Select to Include in Gene Pool)
                </span>
                <span className="text-xs text-zinc-500">
                  {selectedPersonas.size} of {(personas.data ?? []).length} active
                </span>
              </div>

              <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-4">
                {(personas.data ?? []).map((p) => {
                  const active = selectedPersonas.has(p.id);
                  return (
                    <button
                      type="button"
                      key={p.id}
                      onClick={() => togglePersona(p.id)}
                      className={`flex flex-col items-start rounded-xl border p-3 text-left transition-all ${
                        active
                          ? "border-emerald-500/50 bg-emerald-500/10 text-zinc-100 shadow-sm"
                          : "border-zinc-800/80 bg-zinc-900/40 text-zinc-400 hover:border-zinc-700 hover:text-zinc-300"
                      }`}
                    >
                      <div className="flex w-full items-center justify-between">
                        <span className="text-xs font-semibold">{p.name}</span>
                        {p.is_dictation_focused && (
                          <span className="rounded bg-emerald-400/20 px-1.5 py-0.5 text-[9px] font-bold text-emerald-300 uppercase">
                            Wispr
                          </span>
                        )}
                      </div>
                      <p className="mt-1 line-clamp-2 text-[11px] text-zinc-400 leading-relaxed">
                        {p.description}
                      </p>
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-4 border-t border-zinc-800/60 pt-4">
              <div className="flex items-center gap-3">
                <span className="text-xs text-zinc-400">
                  Seed:{" "}
                  <input
                    type="number"
                    value={seed}
                    onChange={(e) => setSeed(Number(e.target.value))}
                    className="ml-1 inline h-7 w-20 rounded border border-zinc-800 bg-zinc-900 px-2 text-xs text-zinc-200"
                  />
                </span>
                <div
                  className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${
                    isOverBudget
                      ? "border border-amber-500/40 bg-amber-500/10 text-amber-300"
                      : "border border-zinc-700 bg-zinc-800/60 text-zinc-400"
                  }`}
                >
                  {isOverBudget && <Warning size={13} />}
                  Budget estimate: {plannedSessions} sessions {isOverBudget && "(clamped to 60)"}
                </div>
              </div>

              <Button
                type="submit"
                disabled={starting || !effectiveAgentId || selectedPersonas.size === 0}
              >
                <Play size={14} weight="fill" />
                {starting ? "Launching campaign…" : "Launch Darwin campaign"}
              </Button>
            </div>

            {error && (
              <p role="alert" className="rounded-lg border border-red-500/25 bg-red-500/10 px-3 py-2 text-xs text-red-400">
                {error}
              </p>
            )}
          </form>
        </CardBody>
      </Card>

      <Card spotlight className="rise rise-2">
        <CardHeader>Campaign History</CardHeader>
        <CardBody className="p-0">
          {(runs.data ?? []).length === 0 ? (
            <EmptyState
              title="No Darwin runs yet"
              hint="Launch your first evolutionary campaign above to discover voice failure modes."
            />
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-800/80 text-left text-[11px] uppercase tracking-wider text-zinc-500">
                  <th className="px-5 py-2.5 font-medium">Campaign</th>
                  <th className="px-5 py-2.5 font-medium">Status</th>
                  <th className="px-5 py-2.5 font-medium">Progress</th>
                  <th className="px-5 py-2.5 font-medium">Best Fitness</th>
                  <th className="px-5 py-2.5 font-medium">Findings</th>
                  <th className="hidden px-5 py-2.5 font-medium sm:table-cell">Started</th>
                  <th className="w-8 px-5 py-2.5" aria-label="Open" />
                </tr>
              </thead>
              <tbody>
                {(runs.data ?? []).map((run) => (
                  <tr
                    key={run.id}
                    onClick={() => router.push(`/darwin/${run.id}`)}
                    className="group cursor-pointer border-b border-zinc-800/40 transition-colors last:border-0 hover:bg-zinc-800/40"
                  >
                    <td className="px-5 py-3">
                      <Link
                        href={`/darwin/${run.id}`}
                        onClick={(e) => e.stopPropagation()}
                        className="font-medium text-emerald-400 transition-colors group-hover:text-emerald-300"
                      >
                        Darwin #{run.id}
                      </Link>
                    </td>
                    <td className="px-5 py-3">
                      <StatusBadge status={run.status} />
                    </td>
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-2">
                        <div className="h-1.5 w-20 overflow-hidden rounded-full bg-zinc-800">
                          <div
                            className="h-full rounded-full bg-emerald-500 transition-all duration-300"
                            style={{ width: `${run.progress}%` }}
                          />
                        </div>
                        <span className="tabular-nums text-xs text-zinc-400">{run.progress}%</span>
                      </div>
                    </td>
                    <td className="px-5 py-3 font-mono text-xs tabular-nums text-zinc-200">
                      {run.stats?.best_fitness !== undefined ? run.stats.best_fitness.toFixed(3) : "—"}
                    </td>
                    <td className="px-5 py-3">
                      <span className="rounded-full bg-red-500/10 px-2 py-0.5 text-xs font-semibold text-red-400">
                        {run.stats?.findings_count || 0} defects
                      </span>
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
