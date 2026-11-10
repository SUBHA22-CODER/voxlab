"use client";

import { useEffect, useRef, useState } from "react";
import { ChartLine, UploadSimple, Trophy, Info } from "@phosphor-icons/react";

import { AudioEngines, Benchmarks } from "@/lib/audio-api";
import type { AudioBenchmark, BenchmarkEngineResult, EngineInfo } from "@/lib/audio-types";
import { Badge, Button, Card, CardBody, CardHeader, EmptyState, Input, Label, PageHeader, SectionTitle } from "@/components/ui";

/**
 * Multi-engine benchmark: identical audio, identical reference, identical
 * normalization for every engine. Unavailable engines are reported as
 * not_installed; nothing is fabricated.
 */

function werOf(result: BenchmarkEngineResult): string {
  const wer = result.metrics?.ground_truth.wer;
  return wer === null || wer === undefined ? "N/A" : `${(wer * 100).toFixed(1)}%`;
}

function rtfOf(result: BenchmarkEngineResult): string {
  const rtf = result.metrics?.ground_truth.realtime_factor;
  return rtf === null || rtf === undefined ? "N/A" : rtf.toFixed(3);
}

export default function BenchmarksPage() {
  const [engines, setEngines] = useState<EngineInfo[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [reference, setReference] = useState("");
  const [label, setLabel] = useState("");
  const [result, setResult] = useState<AudioBenchmark | null>(null);
  const [history, setHistory] = useState<AudioBenchmark[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    AudioEngines.list()
      .then((list) => {
        setEngines(list);
        setSelected(list.filter((e) => e.installed).map((e) => e.engine_id));
      })
      .catch((err: Error) => setError(err.message));
    Benchmarks.list()
      .then(setHistory)
      .catch(() => undefined);
  }, []);

  async function run() {
    if (!file || selected.length === 0) return;
    setBusy(true);
    setError(null);
    try {
      const response = await Benchmarks.run({
        file,
        engines: selected.join(","),
        referenceTranscript: reference || undefined,
        label: label || undefined,
      });
      setResult(response);
      Benchmarks.list()
        .then(setHistory)
        .catch(() => undefined);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Benchmark failed");
    } finally {
      setBusy(false);
    }
  }

  const okResults = result?.engine_results.filter((r) => r.status === "ok") ?? [];
  const best = okResults.length > 1
    ? okResults.reduce((a, b) => {
        const wa = a.metrics?.ground_truth.wer;
        const wb = b.metrics?.ground_truth.wer;
        if (wa === null || wa === undefined) return b;
        if (wb === null || wb === undefined) return a;
        return wb < wa ? b : a;
      })
    : null;

  return (
    <div>
      <PageHeader
        title="Engine Benchmarks"
        subtitle="Run the same audio through every installed engine under identical conditions and compare accuracy, latency, and real-time factor."
      />

      <div className="grid gap-5 lg:grid-cols-[380px_1fr]">
        <div className="space-y-5">
          <Card>
            <CardHeader>Benchmark input</CardHeader>
            <CardBody className="space-y-3">
              <div
                role="button"
                tabIndex={0}
                aria-label="Upload benchmark audio"
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
                  <p className="text-[13px] text-zinc-400">Drop the audio clip</p>
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
                <Label htmlFor="bench-reference">Reference transcript (optional)</Label>
                <textarea
                  id="bench-reference"
                  rows={3}
                  value={reference}
                  onChange={(e) => setReference(e.target.value)}
                  placeholder="Required for WER/CER comparison"
                  className="w-full rounded-lg border border-zinc-800 bg-zinc-900/70 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-emerald-500/60 focus:outline-none focus:ring-2 focus:ring-emerald-500/20"
                />
              </div>
              <div>
                <Label htmlFor="bench-label">Label</Label>
                <Input
                  id="bench-label"
                  placeholder="e.g. noisy kitchen sample"
                  value={label}
                  onChange={(e) => setLabel(e.target.value)}
                />
              </div>
            </CardBody>
          </Card>

          <Card>
            <CardHeader right={<span className="text-[11px] text-zinc-600">{selected.length} selected</span>}>
              Engines
            </CardHeader>
            <CardBody className="space-y-1.5">
              {engines.map((e) => {
                const active = selected.includes(e.engine_id);
                return (
                  <button
                    key={e.engine_id}
                    type="button"
                    aria-pressed={active}
                    disabled={!e.installed}
                    onClick={() =>
                      setSelected((prev) =>
                        prev.includes(e.engine_id)
                          ? prev.filter((x) => x !== e.engine_id)
                          : [...prev, e.engine_id],
                      )
                    }
                    className={`flex w-full items-center justify-between rounded-lg border px-3 py-2 text-left transition-colors ${
                      active
                        ? "border-emerald-500/40 bg-emerald-500/10"
                        : "border-zinc-800 bg-zinc-900/40 hover:border-zinc-700"
                    } ${!e.installed ? "cursor-not-allowed opacity-50" : ""}`}
                  >
                    <span className={`text-[13px] font-medium ${active ? "text-emerald-200" : "text-zinc-300"}`}>
                      {e.engine_id}
                    </span>
                    {!e.installed && <Badge>not installed</Badge>}
                  </button>
                );
              })}
            </CardBody>
          </Card>

          <Button onClick={run} disabled={!file || selected.length === 0 || busy} className="w-full">
            <ChartLine className="h-4 w-4" aria-hidden />
            {busy ? "Benchmarking…" : "Run benchmark"}
          </Button>
          {error && (
            <p role="alert" className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">
              {error}
            </p>
          )}
        </div>

        <div className="space-y-5">
          {!result && (
            <Card>
              <EmptyState
                icon={<ChartLine className="h-6 w-6" aria-hidden />}
                title="No benchmark yet"
                hint="Upload one clip, pick engines, and get a side-by-side comparison measured under identical conditions."
              />
            </Card>
          )}

          {result && (
            <Card>
              <CardHeader right={<span className="font-mono text-[11px] text-zinc-500">{result.audio_duration_seconds.toFixed(2)}s clip</span>}>
                {result.label || "Benchmark"}
              </CardHeader>
              <CardBody className="space-y-3">
                {result.engine_results.map((r) => (
                  <div
                    key={r.engine}
                    className={`rounded-lg border p-3 ${
                      r.status === "ok"
                        ? "border-zinc-800 bg-zinc-900/50"
                        : "border-amber-500/25 bg-amber-500/5"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="flex items-center gap-2 text-sm font-medium text-zinc-200">
                        {r.engine}
                        {best && best.engine === r.engine && (
                          <span className="flex items-center gap-1 text-[11px] text-emerald-400">
                            <Trophy className="h-3.5 w-3.5" aria-hidden /> best WER
                          </span>
                        )}
                      </span>
                      {r.status !== "ok" && (
                        <span className="text-[11px] text-amber-300">{r.status}</span>
                      )}
                    </div>
                    {r.status === "ok" && (
                      <>
                        <p className="mt-1.5 text-sm leading-relaxed text-zinc-300">{r.text}</p>
                        <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 font-mono text-[11px] text-zinc-500">
                          <span>WER {werOf(r)}</span>
                          <span>RTF {rtfOf(r)}</span>
                          <span>{((r.processing_time_seconds ?? 0) * 1000).toFixed(0)} ms</span>
                          {r.model && <span>{r.model}</span>}
                        </div>
                      </>
                    )}
                    {r.status !== "ok" && r.error && (
                      <p className="mt-1 text-[11px] leading-snug text-zinc-500">{r.error}</p>
                    )}
                  </div>
                ))}
                <p className="flex items-start gap-1.5 text-[11px] leading-snug text-zinc-600">
                  <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
                  Identical audio, reference, and normalization for every engine. N/A means the
                  metric does not apply (e.g. no reference provided).
                </p>
              </CardBody>
            </Card>
          )}

          {history.length > 0 && (
            <div>
              <SectionTitle>History</SectionTitle>
              <Card>
                <CardBody className="divide-y divide-zinc-800/70">
                  {history.slice(0, 8).map((b) => (
                    <button
                      key={b.id}
                      type="button"
                      onClick={() => setResult(b)}
                      className="flex w-full items-center justify-between py-2.5 text-left first:pt-0 last:pb-0"
                    >
                      <span className="truncate text-sm text-zinc-300">{b.label || `Benchmark #${b.id}`}</span>
                      <span className="font-mono text-[11px] text-zinc-600">
                        {b.engine_results.length} engines
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
