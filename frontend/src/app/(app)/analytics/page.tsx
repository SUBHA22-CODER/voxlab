"use client";

import { useCallback, useEffect, useState } from "react";
import {
  ChartLine,
  Database,
  ShieldCheck,
  WarningCircle,
  Dna,
  Play,
} from "@phosphor-icons/react";

import { Analytics, AudioEngines, Security } from "@/lib/audio-api";
import type {
  DatasetInfo,
  DriftComparisonView,
  DriftSnapshotView,
  EngineInfo,
  RobustnessReport,
  SecurityHealth,
} from "@/lib/audio-types";
import {
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  EmptyState,
  PageHeader,
  SectionTitle,
  Select,
} from "@/components/ui";

/**
 * Analytics (VoxLab 2.5): robustness heatmap, model drift tracking, and
 * system health — every number from real backend data.
 */

function WerCell({ stat }: { stat: { count: number; mean_wer: number | null } }) {
  const wer = stat.mean_wer;
  const tone =
    wer === null
      ? "text-zinc-600"
      : wer >= 0.5
        ? "text-red-400"
        : wer >= 0.2
          ? "text-amber-400"
          : "text-emerald-400";
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 px-3 py-2.5">
      <p className={`font-mono text-lg ${tone}`}>
        {wer === null ? "N/A" : `${(wer * 100).toFixed(1)}%`}
      </p>
      <p className="mt-0.5 text-[11px] text-zinc-500">
        {stat.count} finding{stat.count === 1 ? "" : "s"}
      </p>
    </div>
  );
}

function BucketGrid({
  title,
  buckets,
}: {
  title: string;
  buckets: Record<string, { count: number; mean_wer: number | null }>;
}) {
  const entries = Object.entries(buckets);
  return (
    <div>
      <SectionTitle>{title}</SectionTitle>
      {entries.length === 0 ? (
        <p className="text-xs leading-snug text-zinc-600">
          No tested conditions in this axis yet — run the Darwin Audio Lab to
          populate it.
        </p>
      ) : (
        <div className="grid gap-2 sm:grid-cols-3">
          {entries.map(([label, stat]) => (
            <div key={label}>
              <p className="mb-1 text-[11px] text-zinc-500">{label.replace(/_/g, " ")}</p>
              <WerCell stat={stat} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function AnalyticsPage() {
  const [robustness, setRobustness] = useState<RobustnessReport | null>(null);
  const [datasets, setDatasets] = useState<DatasetInfo[]>([]);
  const [dataset, setDataset] = useState<string>("");
  const [engines, setEngines] = useState<EngineInfo[]>([]);
  const [engineId, setEngineId] = useState("whisper_local");
  const [snapshots, setSnapshots] = useState<DriftSnapshotView[]>([]);
  const [comparison, setComparison] = useState<DriftComparisonView | null>(null);
  const [health, setHealth] = useState<SecurityHealth | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const loadAnalytics = useCallback(() => {
    Analytics.robustness().then(setRobustness).catch((err: Error) => setError(err.message));
    Security.health().then(setHealth).catch(() => undefined);
  }, []);

  const loadDatasets = useCallback(() => {
    Analytics.listDatasets()
      .then((list) => {
        setDatasets(list);
        if (list.length && !dataset) setDataset(list[0].name);
      })
      .catch(() => undefined);
  }, [dataset]);

  const loadSnapshots = useCallback(() => {
    if (!dataset) return;
    Analytics.listSnapshots(dataset)
      .then(setSnapshots)
      .catch(() => undefined);
  }, [dataset]);

  useEffect(() => {
    loadAnalytics();
    loadDatasets();
    AudioEngines.list()
      .then((list) => {
        setEngines(list);
        const installed = list.find((e) => e.installed);
        if (installed) setEngineId(installed.engine_id);
      })
      .catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    loadSnapshots();
  }, [loadSnapshots]);

  async function createSnapshot() {
    if (!dataset) return;
    setBusy(true);
    setError(null);
    try {
      await Analytics.createSnapshot(dataset, engineId);
      loadSnapshots();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Snapshot failed");
    } finally {
      setBusy(false);
    }
  }

  async function compareWithPrevious() {
    if (snapshots.length < 2) return;
    setError(null);
    try {
      const baseline = snapshots[1]; // list is newest-first
      const current = snapshots[0];
      const result = await Analytics.compare(dataset, baseline.id, current.id);
      setComparison(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Comparison failed");
    }
  }

  return (
    <div>
      <PageHeader
        title="Analytics"
        subtitle="Robustness heatmap, model drift tracking, and system health — aggregated from stored evaluation results only."
      />

      {error && (
        <p role="alert" className="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">
          {error}
        </p>
      )}

      {/* --- Robustness heatmap (Phase 5) --- */}
      <div className="mb-6">
        <SectionTitle right={robustness ? <Badge>{robustness.total_findings} findings</Badge> : undefined}>
          Robustness heatmap
        </SectionTitle>
        {!robustness ? (
          <Card>
            <EmptyState icon={<ChartLine className="h-6 w-6" aria-hidden />} title="Loading…" />
          </Card>
        ) : robustness.total_findings === 0 ? (
          <Card>
            <EmptyState
              icon={<Dna className="h-6 w-6" aria-hidden />}
              title="No audio findings yet"
              hint={robustness.note}
            />
          </Card>
        ) : (
          <div className="space-y-5">
            <BucketGrid title="By attack persona" buckets={robustness.by_persona} />
            <BucketGrid title="By background noise level" buckets={robustness.by_noise_level} />
            <BucketGrid title="By speaking speed" buckets={robustness.by_speaking_speed} />
            <BucketGrid title="By clip duration" buckets={robustness.by_duration} />
          </div>
        )}
      </div>

      {/* --- Model drift (Phase 6) --- */}
      <div className="mb-6">
        <SectionTitle>Model drift tracking</SectionTitle>
        <div className="grid gap-4 lg:grid-cols-[340px_1fr]">
          <Card>
            <CardHeader>Fixed benchmark dataset</CardHeader>
            <CardBody className="space-y-3">
              {datasets.length === 0 ? (
                <p className="text-xs leading-snug text-zinc-600">
                  No dataset found. Build one:
                  <code className="mt-1 block font-mono text-[10px] text-zinc-500">
                    python scripts/build_benchmark_dataset.py --name core-en-v1
                  </code>
                </p>
              ) : (
                <Select
                  aria-label="Benchmark dataset"
                  value={dataset}
                  onChange={(e) => setDataset(e.target.value)}
                >
                  {datasets.map((d) => (
                    <option key={d.name} value={d.name}>
                      {d.name} ({d.case_count} cases)
                    </option>
                  ))}
                </Select>
              )}
              <Select
                aria-label="Benchmark engine"
                value={engineId}
                onChange={(e) => setEngineId(e.target.value)}
              >
                {engines.filter((e) => e.installed).map((e) => (
                  <option key={e.engine_id} value={e.engine_id}>
                    {e.engine_id}
                  </option>
                ))}
              </Select>
              <Button onClick={createSnapshot} disabled={!dataset || busy} className="w-full">
                <Play className="h-4 w-4" aria-hidden />
                {busy ? "Evaluating…" : "Create snapshot"}
              </Button>
              {snapshots.length >= 2 && (
                <Button variant="secondary" onClick={compareWithPrevious} className="w-full">
                  Compare latest two
                </Button>
              )}
            </CardBody>
          </Card>

          <div className="space-y-4">
            {snapshots.length === 0 ? (
              <Card>
                <EmptyState
                  icon={<Database className="h-6 w-6" aria-hidden />}
                  title="No snapshots yet"
                  hint="Create a snapshot to store an immutable evaluation of the fixed dataset with the current model version."
                />
              </Card>
            ) : (
              <Card>
                <CardHeader>Snapshots (newest first)</CardHeader>
                <CardBody className="divide-y divide-zinc-800/70">
                  {snapshots.slice(0, 6).map((s) => (
                    <div key={s.id} className="flex items-center justify-between py-2 first:pt-0 last:pb-0">
                      <span className="font-mono text-xs text-zinc-400">#{s.id}</span>
                      <span className="text-xs text-zinc-500">
                        {s.engine} · {s.model_version || "?"}
                      </span>
                      <span className="font-mono text-sm text-zinc-200">
                        WER {(s.mean_wer * 100).toFixed(1)}%
                      </span>
                      <span className="font-mono text-[11px] text-zinc-600">
                        {new Date(s.created_at).toLocaleString()}
                      </span>
                    </div>
                  ))}
                </CardBody>
              </Card>
            )}

            {comparison && (
              <Card>
                <CardHeader
                  right={
                    comparison.significant === null ? (
                      <Badge>no significance claim</Badge>
                    ) : comparison.regression_detected ? (
                      <Badge tone="red">regression detected</Badge>
                    ) : (
                      <Badge tone="green">no regression</Badge>
                    )
                  }
                >
                  Drift comparison
                </CardHeader>
                <CardBody className="space-y-3">
                  <div className="grid grid-cols-3 gap-3 text-center">
                    <div>
                      <p className="text-[11px] text-zinc-500">WER delta</p>
                      <p className={`font-mono text-lg ${(comparison.deltas.wer ?? 0) > 0 ? "text-red-400" : "text-emerald-400"}`}>
                        {comparison.deltas.wer === null ? "N/A" : `${(comparison.deltas.wer * 100).toFixed(2)}%`}
                      </p>
                    </div>
                    <div>
                      <p className="text-[11px] text-zinc-500">95% CI</p>
                      <p className="font-mono text-sm text-zinc-300">
                        {comparison.wer_ci_95[0] === null
                          ? "N/A"
                          : `[${(comparison.wer_ci_95[0] * 100).toFixed(2)}%, ${(comparison.wer_ci_95[1] ?? 0) * 100 > 0 ? (comparison.wer_ci_95[1]! * 100).toFixed(2) + "%" : ""}]`}
                      </p>
                    </div>
                    <div>
                      <p className="text-[11px] text-zinc-500">Paired cases</p>
                      <p className="font-mono text-sm text-zinc-300">{comparison.paired_cases}</p>
                    </div>
                  </div>
                  <p className="text-[11px] leading-snug text-zinc-600">{comparison.note}</p>
                </CardBody>
              </Card>
            )}
          </div>
        </div>
      </div>

      {/* --- Security & system health (Phase 1 surfaces) --- */}
      <div>
        <SectionTitle>System health</SectionTitle>
        {!health ? (
          <Card>
            <EmptyState icon={<ShieldCheck className="h-6 w-6" aria-hidden />} title="Loading…" />
          </Card>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Card>
              <CardBody>
                <p className="text-[11px] text-zinc-500">Database</p>
                <p className={`mt-1 font-mono text-sm ${health.database.reachable ? "text-emerald-400" : "text-red-400"}`}>
                  {health.database.reachable ? "reachable" : "unreachable"}
                </p>
                <p className="mt-1 text-[11px] text-zinc-600">{health.database.revoked_tokens} revoked tokens</p>
              </CardBody>
            </Card>
            <Card>
              <CardBody>
                <p className="text-[11px] text-zinc-500">Auth</p>
                <p className="mt-1 font-mono text-sm text-zinc-200">JWT + revocation</p>
                <p className="mt-1 text-[11px] text-zinc-600">
                  demo bypass removed · {health.auth.rate_limit_rules.length} rate-limit rules
                </p>
              </CardBody>
            </Card>
            <Card>
              <CardBody>
                <p className="text-[11px] text-zinc-500">Audio retention</p>
                <p className="mt-1 font-mono text-sm text-zinc-200">
                  {health.retention.audio_retention_days === 0 ? "keep forever" : `${health.retention.audio_retention_days} days`}
                </p>
              </CardBody>
            </Card>
            <Card>
              <CardBody>
                <p className="text-[11px] text-zinc-500">Engines installed</p>
                <p className="mt-1 font-mono text-sm text-zinc-200">
                  {health.engines.filter((e) => e.installed).map((e) => e.engine_id).join(", ") || "none"}
                </p>
                {health.engines.some((e) => !e.installed) && (
                  <p className="mt-1 flex items-center gap-1 text-[11px] text-amber-400">
                    <WarningCircle className="h-3 w-3" aria-hidden />
                    {health.engines.filter((e) => !e.installed).map((e) => e.engine_id).join(", ")} not installed
                  </p>
                )}
              </CardBody>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}
