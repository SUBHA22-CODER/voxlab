"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Scenarios } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { Badge, Button, Card, CardBody, EmptyState, PageHeader, Spinner } from "@/components/ui";
import type { Scenario } from "@/lib/types";

const CATEGORY_TONES: Record<string, "green" | "red" | "amber" | "zinc" | "blue"> = {
  interruption: "red",
  tool_failure: "red",
  recovery: "amber",
  context_retention: "blue",
  long_conversation: "blue",
  language: "green",
  ambiguity: "amber",
  conversation: "zinc",
};

export default function ScenariosPage() {
  const scenarios = useApi(Scenarios.list);
  const [expanded, setExpanded] = useState<number | null>(null);

  const grouped = useMemo(() => {
    const byCategory = new Map<string, Scenario[]>();
    for (const scenario of scenarios.data ?? []) {
      const list = byCategory.get(scenario.category) ?? [];
      list.push(scenario);
      byCategory.set(scenario.category, list);
    }
    return [...byCategory.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [scenarios.data]);

  if (scenarios.loading) return <Spinner label="Loading scenarios…" />;

  return (
    <>
      <PageHeader
        title="Scenario library"
        subtitle="Stress tests your agent must survive — interruptions, API failures, language switches, memory probes."
      />

      {grouped.length === 0 ? (
        <Card>
          <EmptyState title="No scenarios loaded" hint="Builtin scenarios load from the repo's scenarios/ directory on startup." />
        </Card>
      ) : (
        <div className="space-y-6">
          {grouped.map(([category, items]) => (
            <div key={category}>
              <h2 className="mb-2 text-xs font-semibold uppercase tracking-widest text-zinc-500">
                {category.replace(/_/g, " ")} · {items.length}
              </h2>
              <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
                {items.map((scenario) => (
                  <Card key={scenario.id}>
                    <CardBody>
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <h3 className="text-sm font-semibold text-zinc-100">{scenario.name}</h3>
                          <p className="mt-0.5 text-xs text-zinc-400">
                            {scenario.definition.description ?? scenario.definition.expected_behavior}
                          </p>
                        </div>
                        <div className="flex shrink-0 gap-1.5">
                          <Badge tone={CATEGORY_TONES[scenario.category] ?? "zinc"}>{scenario.category.replace(/_/g, " ")}</Badge>
                          {scenario.is_builtin && <Badge>builtin</Badge>}
                        </div>
                      </div>
                      <div className="mt-3 flex items-center gap-3 text-xs text-zinc-500">
                        <span>{scenario.definition.steps.length} steps</span>
                        <span>{scenario.definition.checks?.length ?? 0} checks</span>
                        <span>budget {scenario.definition.latency_budget_ms ?? 5000} ms</span>
                        <button
                          className="ml-auto text-emerald-400 hover:underline"
                          onClick={() => setExpanded(expanded === scenario.id ? null : scenario.id)}
                          aria-expanded={expanded === scenario.id}
                        >
                          {expanded === scenario.id ? "Hide script" : "View script"}
                        </button>
                      </div>
                      {expanded === scenario.id && (
                        <div className="mt-3 space-y-1.5 rounded-lg border border-zinc-800 bg-zinc-950 p-3 font-mono text-[11px] leading-relaxed text-zinc-400">
                          {scenario.definition.steps.map((step, i) => (
                            <div key={i}>
                              <span className="text-emerald-400">
                                {step.type === "tool_failure" ? "⚑ inject tool failure" : step.type}
                              </span>
                              {step.content ? `: ${step.content}` : ""}
                            </div>
                          ))}
                          <div className="pt-1 text-zinc-500">
                            expected: {scenario.definition.expected_behavior}
                          </div>
                        </div>
                      )}
                    </CardBody>
                  </Card>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      <p className="mt-8 text-xs text-zinc-600">
        Start a benchmark from the{" "}
        <Link href="/runs" className="text-emerald-400 hover:underline">
          Test Runs
        </Link>{" "}
        page by selecting an agent and any of these scenarios.
      </p>
    </>
  );
}
