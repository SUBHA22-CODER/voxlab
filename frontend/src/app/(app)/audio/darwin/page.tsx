"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Dna,
  UploadSimple,
  Stop,
  ArrowsIn,
  Archive,
  CheckCircle,
  WarningCircle,
} from "@phosphor-icons/react";

import { DarwinAudio, Regressions } from "@/lib/audio-api";
import type {
  AudioPersona,
  DarwinAudioFinding,
  DarwinAudioRun,
  TransformSpec,
} from "@/lib/audio-types";
import {
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  EmptyState,
  Input,
  Label,
  PageHeader,
  SectionTitle,
  StatusBadge,
} from "@/components/ui";

/**
 * Darwin Audio Lab: evolves adversarial audio against a real speech engine,
 * then minimizes discovered failures to their smallest reproducible chain.
 * Live progress polls the real run row; findings come from the run's data.
 */

function ChainChips({ chain, tone }: { chain: TransformSpec[]; tone: "original" | "minimized" }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {chain.length === 0 && <span className="text-[11px] text-zinc-600">no transforms</span>}
      {chain.map((spec, i) => (
        <span
          key={i}
          title={`seed ${spec.seed} · ${JSON.stringify(spec.params)}`}
          className={`rounded-md border px-2 py-0.5 font-mono text-[10px] ${
            tone === "minimized"
              ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
              : "border-zinc-700/70 bg-zinc-800/60 text-zinc-400"
          }`}
        >
          {spec.operator}
        </span>
      ))}
    </div>
  );
}

function FindingCard({ finding }: { finding: DarwinAudioFinding }) {
  const [promoted, setPromoted] = useState(false);
  const [promoting, setPromoting] = useState(false);
  const gt = finding.metrics?.ground_truth;
  const minimized = (finding.minimized_genome?.transform_chain ?? []) as TransformSpec[];
  const original = (finding.genome?.transform_chain ?? []) as TransformSpec[];

  async function promote() {
    setPromoting(true);
    try {
      await Regressions.promoteFromFinding(finding.id);
      setPromoted(true);
    } finally {
      setPromoting(false);
    }
  }

  return (
    <Card>
      <CardHeader
        right={
          <div className="flex items-center gap-2">
            <Badge tone="red">{finding.persona_id.replace(/_/g, " ")}</Badge>
            <span className="font-mono text-xs text-zinc-400">
              failure {(finding.fitness * 100).toFixed(1)}%
            </span>
          </div>
        }
      >
        Discovered failure
      </CardHeader>
      <CardBody className="space-y-4">
        <div className="grid gap-3 md:grid-cols-2">
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-3">
            <p className="mb-1 text-[10px] font-medium uppercase tracking-wider text-zinc-600">
              Reference
            </p>
            <p className="text-sm leading-relaxed text-zinc-300">{finding.reference_transcript}</p>
          </div>
          <div className="rounded-lg border border-red-500/25 bg-red-500/5 p-3">
            <p className="mb-1 text-[10px] font-medium uppercase tracking-wider text-red-400/80">
              Engine heard
            </p>
            <p className="text-sm leading-relaxed text-red-200/90">{finding.failed_transcript}</p>
          </div>
        </div>

        {gt && (
          <div className="flex flex-wrap gap-x-5 gap-y-1 font-mono text-[11px] text-zinc-500">
            <span>WER {(gt.wer * 100).toFixed(1)}%</span>
            <span>CER {(gt.cer * 100).toFixed(1)}%</span>
            {gt.number_accuracy !== null && <span>numbers {(gt.number_accuracy * 100).toFixed(0)}%</span>}
            {gt.technical_vocab_accuracy !== null && (
              <span>vocab {(gt.technical_vocab_accuracy * 100).toFixed(0)}%</span>
            )}
          </div>
        )}

        <div className="space-y-2">
          <div className="flex items-center gap-2 text-[11px] text-zinc-500">
            <span className="w-20">Chain ({original.length})</span>
            <ChainChips chain={original} tone="original" />
          </div>
          <div className="flex items-center gap-2 text-[11px] text-zinc-400">
            <ArrowsIn className="h-3.5 w-3.5 text-emerald-500" aria-hidden />
            <span className="w-20">Minimized ({finding.minimized_chain_length})</span>
            <ChainChips chain={minimized} tone="minimized" />
          </div>
        </div>

        <div className="flex items-center justify-between">
          <span className="font-mono text-[10px] text-zinc-600">
            artifact {finding.audio_artifact_ref}
          </span>
          <Button size="sm" variant="secondary" onClick={promote} disabled={promoted || promoting}>
            {promoted ? (
              <CheckCircle className="h-3.5 w-3.5 text-emerald-500" aria-hidden />
            ) : (
              <Archive className="h-3.5 w-3.5" aria-hidden />
            )}
            {promoted ? "In regression corpus" : promoting ? "Adding…" : "Add to regressions"}
          </Button>
        </div>
      </CardBody>
    </Card>
  );
}

export default function DarwinAudioPage() {
  const [personas, setPersonas] = useState<AudioPersona[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [reference, setReference] = useState("");
  const [population, setPopulation] = useState(4);
  const [generations, setGenerations] = useState(2);
  const [threshold, setThreshold] = useState(0.4);
  const [run, setRun] = useState<DarwinAudioRun | null>(null);
  const [findings, setFindings] = useState<DarwinAudioFinding[]>([]);
  const [runs, setRuns] = useState<DarwinAudioRun[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadRuns = useCallback(() => {
    DarwinAudio.listRuns()
      .then(setRuns)
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    DarwinAudio.personas()
      .then((list) => {
        setPersonas(list);
        setSelected(list.slice(0, 4).map((p) => p.id));
      })
      .catch((err: Error) => setError(err.message));
    loadRuns();
  }, [loadRuns]);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  useEffect(() => stopPolling, [stopPolling]);

  function watchRun(runId: number) {
    stopPolling();
    pollRef.current = setInterval(async () => {
      try {
        const current = await DarwinAudio.getRun(runId);
        setRun(current);
        if (["completed", "failed", "cancelled"].includes(current.status)) {
          stopPolling();
          const found = await DarwinAudio.findings(runId).catch(() => []);
          setFindings(found);
          loadRuns();
        }
      } catch {
        stopPolling();
      }
    }, 1500);
  }

  async function start() {
    if (!file || !reference.trim()) return;
    setBusy(true);
    setError(null);
    setFindings([]);
    try {
      const created = await DarwinAudio.evolve({
        file,
        referenceTranscript: reference,
        engineId: "whisper_local",
        language: "en",
        populationSize: population,
        generations,
        topK: 2,
        seed: 42,
        failureThreshold: threshold,
        personas: selected,
      });
      setRun(created);
      watchRun(created.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start run");
    } finally {
      setBusy(false);
    }
  }

  async function cancel() {
    if (!run) return;
    try {
      const cancelled = await DarwinAudio.cancelRun(run.id);
      setRun(cancelled);
      stopPolling();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Cancel failed");
    }
  }

  const running = run !== null && ["queued", "running"].includes(run.status);
  const stats = (run?.stats ?? {}) as Record<string, number | string | boolean>;

  return (
    <div>
      <PageHeader
        title="Darwin Audio Lab"
        subtitle="Evolutionary adversarial testing for speech engines: mutate real audio, find real transcription failures, minimize them to the smallest reproducible chain."
      />

      <div className="grid gap-5 lg:grid-cols-[380px_1fr]">
        <div className="space-y-5">
          <Card>
            <CardHeader>Seed audio</CardHeader>
            <CardBody className="space-y-3">
              <div
                role="button"
                tabIndex={0}
                aria-label="Upload seed audio"
                onClick={() => fileInput.current?.click()}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") fileInput.current?.click();
                }}
                className="flex cursor-pointer flex-col items-center gap-1.5 rounded-xl border border-dashed border-zinc-800 bg-zinc-900/40 px-4 py-6 text-center transition-colors hover:border-zinc-700"
              >
                <UploadSimple className="h-5 w-5 text-zinc-500" aria-hidden />
                {file ? (
                  <p className="max-w-full truncate text-sm text-zinc-200">{file.name}</p>
                ) : (
                  <p className="text-[13px] text-zinc-400">Drop the clean seed recording</p>
                )}
                <input
                  ref={fileInput}
                  type="file"
                  accept=".wav,.mp3,.flac,.ogg,.webm,audio/*"
                  className="hidden"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                />
              </div>
              <div>
                <Label htmlFor="reference-transcript">Reference transcript</Label>
                <textarea
                  id="reference-transcript"
                  rows={3}
                  value={reference}
                  onChange={(e) => setReference(e.target.value)}
                  placeholder="Exactly what the seed audio says"
                  className="w-full rounded-lg border border-zinc-800 bg-zinc-900/70 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-emerald-500/60 focus:outline-none focus:ring-2 focus:ring-emerald-500/20"
                />
              </div>
            </CardBody>
          </Card>

          <Card>
            <CardHeader right={<span className="text-[11px] text-zinc-600">{selected.length} selected</span>}>
              Attack personas
            </CardHeader>
            <CardBody className="space-y-1.5">
              {personas.map((p) => {
                const active = selected.includes(p.id);
                return (
                  <button
                    key={p.id}
                    type="button"
                    aria-pressed={active}
                    onClick={() =>
                      setSelected((prev) =>
                        prev.includes(p.id) ? prev.filter((x) => x !== p.id) : [...prev, p.id],
                      )
                    }
                    className={`w-full rounded-lg border px-3 py-2 text-left transition-colors ${
                      active
                        ? "border-emerald-500/40 bg-emerald-500/10"
                        : "border-zinc-800 bg-zinc-900/40 hover:border-zinc-700"
                    }`}
                  >
                    <span className="flex items-center justify-between gap-2">
                      <span className={`text-[13px] font-medium ${active ? "text-emerald-200" : "text-zinc-300"}`}>
                        {p.name}
                      </span>
                      {p.is_content_persona && <Badge>content</Badge>}
                    </span>
                    <span className="mt-0.5 block text-[11px] leading-snug text-zinc-500">
                      {p.description}
                    </span>
                  </button>
                );
              })}
            </CardBody>
          </Card>

          <Card>
            <CardHeader>Budget</CardHeader>
            <CardBody className="grid grid-cols-3 gap-3">
              <div>
                <Label htmlFor="population-input">Population</Label>
                <Input
                  id="population-input"
                  type="number"
                  min={2}
                  max={20}
                  value={population}
                  onChange={(e) => setPopulation(Number(e.target.value))}
                />
              </div>
              <div>
                <Label htmlFor="generations-input">Generations</Label>
                <Input
                  id="generations-input"
                  type="number"
                  min={1}
                  max={20}
                  value={generations}
                  onChange={(e) => setGenerations(Number(e.target.value))}
                />
              </div>
              <div>
                <Label htmlFor="threshold-input">Threshold</Label>
                <Input
                  id="threshold-input"
                  type="number"
                  min={0}
                  max={1}
                  step={0.05}
                  value={threshold}
                  onChange={(e) => setThreshold(Number(e.target.value))}
                />
              </div>
              <p className="col-span-3 text-[11px] leading-snug text-zinc-600">
                population × generations is hard-capped at 60 transcription sessions by the engine.
              </p>
            </CardBody>
          </Card>

          <div className="flex gap-2">
            <Button onClick={start} disabled={!file || !reference.trim() || busy || running} className="flex-1">
              <Dna className="h-4 w-4" aria-hidden />
              {busy ? "Starting…" : "Evolve"}
            </Button>
            {running && (
              <Button variant="danger" onClick={cancel}>
                <Stop className="h-4 w-4" aria-hidden />
                Stop
              </Button>
            )}
          </div>
          {error && (
            <p role="alert" className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">
              {error}
            </p>
          )}
        </div>

        <div className="space-y-5">
          {run && (
            <Card>
              <CardHeader
                right={
                  <div className="flex items-center gap-2">
                    <StatusBadge status={run.status} />
                    <span className="font-mono text-xs text-zinc-400">{run.progress}%</span>
                  </div>
                }
              >
                Run #{run.id}
              </CardHeader>
              <CardBody className="space-y-3">
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-zinc-800">
                  <div
                    className="h-full rounded-full bg-emerald-500 transition-[width] duration-700"
                    style={{ width: `${run.progress}%` }}
                  />
                </div>
                <div className="flex flex-wrap gap-x-6 gap-y-1 font-mono text-[11px] text-zinc-500">
                  <span>
                    sessions {String(stats.sessions_executed ?? 0)}/{String(stats.planned_evaluations ?? "?")}
                  </span>
                  <span>best failure {String(stats.best_failure_score ?? "0")}</span>
                  <span>findings {String(stats.findings ?? 0)}</span>
                  {typeof stats.wall_time_seconds === "number" && (
                    <span>{stats.wall_time_seconds.toFixed(1)}s wall</span>
                  )}
                </div>
                {run.error && (
                  <p className="flex items-start gap-1.5 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-300">
                    <WarningCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
                    {run.error}
                  </p>
                )}
              </CardBody>
            </Card>
          )}

          <div>
            <SectionTitle>Discovered failures</SectionTitle>
            {findings.length === 0 ? (
              <Card>
                <EmptyState
                  icon={<Dna className="h-6 w-6" aria-hidden />}
                  title={run ? (running ? "Evolving…" : "No failures above threshold") : "No run yet"}
                  hint={
                    running
                      ? "The engine is mutating your seed audio and transcribing every generation."
                      : "Start an evolution run: Darwin will hunt for audio that breaks the speech engine, then minimize each failure."
                  }
                />
              </Card>
            ) : (
              <div className="space-y-4">
                {findings.map((f) => (
                  <FindingCard key={f.id} finding={f} />
                ))}
              </div>
            )}
          </div>

          {runs.length > 0 && (
            <div>
              <SectionTitle>Run history</SectionTitle>
              <Card>
                <CardBody className="divide-y divide-zinc-800/70">
                  {runs.slice(0, 8).map((r) => (
                    <button
                      key={r.id}
                      type="button"
                      onClick={() => {
                        setRun(r);
                        if (["completed", "failed", "cancelled"].includes(r.status)) {
                          DarwinAudio.findings(r.id).then(setFindings).catch(() => undefined);
                        } else {
                          watchRun(r.id);
                        }
                      }}
                      className="flex w-full items-center justify-between py-2.5 text-left first:pt-0 last:pb-0"
                    >
                      <span className="text-sm text-zinc-300">Run #{r.id}</span>
                      <span className="flex items-center gap-3">
                        <span className="font-mono text-[11px] text-zinc-600">
                          {String((r.stats as Record<string, number>).findings ?? 0)} findings
                        </span>
                        <StatusBadge status={r.status} />
                      </span>
                    </button>
                  ))}
                </CardBody>
              </Card>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
