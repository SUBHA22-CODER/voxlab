"use client";

import { useEffect, useRef, useState } from "react";
import { Waveform, UploadSimple, Play, ArrowsLeftRight } from "@phosphor-icons/react";

import { AudioEngines, AudioTranscribe } from "@/lib/audio-api";
import type { EngineInfo, TranscriptionResult } from "@/lib/audio-types";
import { AudioMetricBars } from "@/components/audio/metric-bars";
import { AudioScoring } from "@/lib/audio-api";
import type { ManualScoreView } from "@/lib/audio-types";
import { WordDiff } from "@/components/audio/word-diff";
import type { SemanticErrorView } from "@/lib/audio-types";
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
  Select,
} from "@/components/ui";

/**
 * Audio Lab: upload a clip, transcribe it through a real engine, optionally
 * score it against a reference transcript. Every number shown comes from the
 * backend's metric engine; nothing is simulated.
 */

const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;

export default function AudioLabPage() {
  const [engines, setEngines] = useState<EngineInfo[]>([]);
  const [engineId, setEngineId] = useState("whisper_local");
  const [file, setFile] = useState<File | null>(null);
  const [reference, setReference] = useState("");
  const [entities, setEntities] = useState("");
  const [technicalVocab, setTechnicalVocab] = useState("");
  const [language, setLanguage] = useState("");
  const [result, setResult] = useState<TranscriptionResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [mode, setMode] = useState<"transcribe" | "wispr">("transcribe");
  const [wisprHypothesis, setWisprHypothesis] = useState("");
  const [wisprResult, setWisprResult] = useState<ManualScoreView | null>(null);
  const [wisprBusy, setWisprBusy] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    AudioEngines.list()
      .then((list) => {
        setEngines(list);
        const installed = list.find((e) => e.installed);
        if (installed) setEngineId(installed.engine_id);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  function pickFile(next: File | null) {
    setError(null);
    if (next && next.size > MAX_UPLOAD_BYTES) {
      setError("File exceeds the 25 MB upload limit.");
      return;
    }
    setFile(next);
    setResult(null);
  }

  async function scoreWispr() {
    if (!reference.trim() || !wisprHypothesis.trim()) return;
    setWisprBusy(true);
    setError(null);
    try {
      const response = await AudioScoring.score({
        reference,
        hypothesis: wisprHypothesis,
        label: "wispr-flow-pro",
        entities: entities ? entities.split(",").map((e) => e.trim()).filter(Boolean) : undefined,
        technical_vocab: technicalVocab ? technicalVocab.split(",").map((v) => v.trim()).filter(Boolean) : undefined,
      });
      setWisprResult(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Scoring failed");
    } finally {
      setWisprBusy(false);
    }
  }

  async function run() {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const response = await AudioTranscribe.transcribe({
        file,
        engineId,
        language: language || undefined,
        referenceTranscript: reference || undefined,
        entities: entities || undefined,
        technicalVocab: technicalVocab || undefined,
      });
      setResult(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Transcription failed");
    } finally {
      setBusy(false);
    }
  }

  const installedEngines = engines.filter((e) => e.installed);

  return (
    <div>
      <PageHeader
        title="Audio Lab"
        subtitle="Transcribe real audio through real speech engines and measure accuracy against a reference transcript."
      />

      <div className="mb-4 inline-flex rounded-lg border border-zinc-800 bg-zinc-900/60 p-1" role="tablist" aria-label="Input mode">
        <button
          type="button"
          role="tab"
          aria-selected={mode === "transcribe"}
          onClick={() => setMode("transcribe")}
          className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${mode === "transcribe" ? "bg-emerald-500/15 text-emerald-300" : "text-zinc-400 hover:text-zinc-200"}`}
        >
          Audio transcription
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mode === "wispr"}
          onClick={() => setMode("wispr")}
          className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${mode === "wispr" ? "bg-emerald-500/15 text-emerald-300" : "text-zinc-400 hover:text-zinc-200"}`}
        >
          Wispr Flow capture
        </button>
      </div>

      <div className="grid gap-5 lg:grid-cols-[400px_1fr]">
        <div className="space-y-5">
          {mode === "wispr" && (
          <Card>
            <CardHeader>Wispr Flow capture</CardHeader>
            <CardBody className="space-y-3">
              <ol className="list-inside list-decimal space-y-1 text-xs leading-relaxed text-zinc-400">
                <li>Type the reference text into the field below.</li>
                <li>Focus the capture box and dictate it with Wispr Flow (Pro) — it types at your cursor.</li>
                <li>Score it: the same WER / word-level / semantic layers as the engine leaderboard.</li>
              </ol>
              <div>
                <Label htmlFor="wispr-hypothesis">Wispr Flow output</Label>
                <textarea
                  id="wispr-hypothesis"
                  rows={4}
                  value={wisprHypothesis}
                  onChange={(e) => setWisprHypothesis(e.target.value)}
                  placeholder="Focus here and dictate with Wispr Flow…"
                  className="w-full rounded-lg border border-zinc-800 bg-zinc-900/70 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-emerald-500/60 focus:outline-none focus:ring-2 focus:ring-emerald-500/20"
                />
              </div>
              <Button onClick={scoreWispr} disabled={!reference.trim() || !wisprHypothesis.trim() || wisprBusy} className="w-full">
                {wisprBusy ? "Scoring…" : "Score Wispr Flow output"}
              </Button>
              <p className="text-[10px] leading-snug text-zinc-600">
                Human-in-the-loop benchmarking: your Pro dictation output is scored through the same
                deterministic metric layer as the engines. Nothing leaves your machine.
              </p>
            </CardBody>
          </Card>
          )}

          {mode === "transcribe" && (
          <Card>
            <CardHeader>Audio clip</CardHeader>
            <CardBody>
              <div
                role="button"
                tabIndex={0}
                aria-label="Upload audio file"
                onClick={() => fileInput.current?.click()}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") fileInput.current?.click();
                }}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragOver(true);
                }}
                onDragLeave={() => setDragOver(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragOver(false);
                  pickFile(e.dataTransfer.files[0] ?? null);
                }}
                className={`flex cursor-pointer flex-col items-center gap-2 rounded-xl border border-dashed px-4 py-8 text-center transition-colors ${
                  dragOver
                    ? "border-emerald-500/60 bg-emerald-500/5"
                    : "border-zinc-800 bg-zinc-900/40 hover:border-zinc-700"
                }`}
              >
                <UploadSimple className="h-6 w-6 text-zinc-500" aria-hidden />
                {file ? (
                  <>
                    <p className="max-w-full truncate text-sm font-medium text-zinc-200">{file.name}</p>
                    <p className="font-mono text-[11px] text-zinc-500">
                      {(file.size / 1024).toFixed(0)} KB
                    </p>
                  </>
                ) : (
                  <>
                    <p className="text-sm font-medium text-zinc-300">Drop audio or click to browse</p>
                    <p className="text-[11px] text-zinc-600">WAV, MP3, FLAC, OGG, WebM · up to 25 MB</p>
                  </>
                )}
                <input
                  ref={fileInput}
                  type="file"
                  accept=".wav,.mp3,.flac,.ogg,.webm,.m4a,audio/*"
                  className="hidden"
                  onChange={(e) => pickFile(e.target.files?.[0] ?? null)}
                />
              </div>
            </CardBody>
          </Card>
          )}

          {mode === "transcribe" && (
          <Card>
            <CardHeader>Engine</CardHeader>
            <CardBody className="space-y-3">
              <div>
                <Label htmlFor="engine-select">Speech engine</Label>
                <Select id="engine-select" value={engineId} onChange={(e) => setEngineId(e.target.value)}>
                  {installedEngines.length === 0 && <option value="">No engines installed</option>}
                  {installedEngines.map((e) => (
                    <option key={e.engine_id} value={e.engine_id}>
                      {e.engine_id}
                    </option>
                  ))}
                </Select>
                {installedEngines.length === 0 && (
                  <p className="mt-2 text-[11px] leading-snug text-zinc-600">
                    Install the speech extra on the backend:{" "}
                    <code className="font-mono text-zinc-500">pip install -r requirements-speech.txt</code>
                  </p>
                )}
              </div>
              <div>
                <Label htmlFor="language-input">Language hint (optional)</Label>
                <Input
                  id="language-input"
                  placeholder="en, de, hi… leave empty to auto-detect"
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                />
              </div>
            </CardBody>
          </Card>
          )}

          <Card>
            <CardHeader>{mode === "wispr" ? "Reference text" : "Reference transcript (optional)"}</CardHeader>
            <CardBody className="space-y-3">
              <div>
                <Label htmlFor="reference-input">What the audio should say</Label>
                <textarea
                  id="reference-input"
                  rows={3}
                  value={reference}
                  onChange={(e) => setReference(e.target.value)}
                  placeholder="Enables WER / CER / entity scoring"
                  className="w-full rounded-lg border border-zinc-800 bg-zinc-900/70 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 transition-colors hover:border-zinc-700 focus:border-emerald-500/60 focus:outline-none focus:ring-2 focus:ring-emerald-500/20"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label htmlFor="entities-input">Entities</Label>
                  <Input
                    id="entities-input"
                    placeholder="VoxLab, Sarah"
                    value={entities}
                    onChange={(e) => setEntities(e.target.value)}
                  />
                </div>
                <div>
                  <Label htmlFor="vocab-input">Technical vocab</Label>
                  <Input
                    id="vocab-input"
                    placeholder="kubernetes, API"
                    value={technicalVocab}
                    onChange={(e) => setTechnicalVocab(e.target.value)}
                  />
                </div>
              </div>
              <Button onClick={run} disabled={!file || busy || !engineId} className="w-full">
                <Play className="h-4 w-4" aria-hidden />
                {busy ? "Transcribing…" : "Transcribe"}
              </Button>
              {error && (
                <p role="alert" className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs leading-relaxed text-red-300">
                  {error}
                </p>
              )}
            </CardBody>
          </Card>
        </div>

        <div className="space-y-5">
          {mode === "transcribe" && !result && !busy && (
            <Card>
              <EmptyState
                icon={<Waveform className="h-6 w-6" aria-hidden />}
                title="No transcription yet"
                hint="Upload a clip and press Transcribe. Add a reference transcript to unlock accuracy metrics."
              />
            </Card>
          )}

          {mode === "transcribe" && busy && (
            <Card>
              <CardBody className="space-y-3">
                <div className="h-4 w-40 animate-pulse rounded bg-zinc-800" />
                <div className="h-3 w-full animate-pulse rounded bg-zinc-800/70" />
                <div className="h-3 w-4/5 animate-pulse rounded bg-zinc-800/70" />
                <div className="h-3 w-3/5 animate-pulse rounded bg-zinc-800/70" />
              </CardBody>
            </Card>
          )}

          {mode === "transcribe" && result && (
            <>
              <Card>
                <CardHeader
                  right={
                    <div className="flex items-center gap-2">
                      <Badge tone="green">{result.engine}</Badge>
                      {result.language && (
                        <Badge>
                          {result.language}
                          {result.language_probability !== null
                            ? ` ${(result.language_probability * 100).toFixed(0)}%`
                            : ""}
                        </Badge>
                      )}
                    </div>
                  }
                >
                  Transcription
                </CardHeader>
                <CardBody>
                  <p className="text-[15px] leading-relaxed text-zinc-100">
                    {result.text || (
                      <span className="text-zinc-500 italic">Empty transcription (no speech detected)</span>
                    )}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 font-mono text-[11px] text-zinc-500">
                    <span>audio {result.duration_seconds.toFixed(2)}s</span>
                    <span>processed in {(result.processing_time_seconds * 1000).toFixed(0)} ms</span>
                    <span>{result.segments.length} segments</span>
                  </div>
                </CardBody>
              </Card>

              {result.segments.length > 0 && (
                <Card>
                  <CardHeader>Segments</CardHeader>
                  <CardBody className="divide-y divide-zinc-800/70">
                    {result.segments.map((seg, i) => (
                      <div key={i} className="flex gap-3 py-2 first:pt-0 last:pb-0">
                        <span className="w-24 shrink-0 font-mono text-[11px] text-zinc-600">
                          {seg.start_seconds.toFixed(2)}s → {seg.end_seconds.toFixed(2)}s
                        </span>
                        <span className="text-sm text-zinc-300">{seg.text}</span>
                      </div>
                    ))}
                  </CardBody>
                </Card>
              )}

              {result.semantic && result.semantic.errors.length > 0 && (
                <Card>
                  <CardHeader
                    right={
                      <Badge tone={result.semantic.meaning_preserved ? "green" : "red"}>
                        {result.semantic.meaning_preserved ? "meaning preserved" : "meaning changed"}
                      </Badge>
                    }
                  >
                    Semantic error analysis
                  </CardHeader>
                  <CardBody className="space-y-2">
                    {result.semantic.errors.map((err: SemanticErrorView, i: number) => (
                      <div key={i} className="rounded-lg border border-zinc-800 bg-zinc-900/50 px-3 py-2">
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-mono text-[11px] text-zinc-400">{err.type.replace(/_/g, " ")}</span>
                          <Badge tone={err.severity === "critical" ? "red" : err.severity === "major" ? "amber" : "zinc"}>
                            {err.severity}
                          </Badge>
                        </div>
                        <p className="mt-1 text-xs leading-relaxed text-zinc-400">{err.description}</p>
                        {err.reference && <p className="mt-1 text-[11px] text-zinc-500">reference: {err.reference}</p>}
                        {err.hypothesis && <p className="text-[11px] text-zinc-500">transcript: {err.hypothesis}</p>}
                      </div>
                    ))}
                    <p className="text-[10px] text-zinc-600">
                      deterministic layer (ground truth). LLM judgment is opt-in via use_llm_judge and always labeled separately.
                    </p>
                  </CardBody>
                </Card>
              )}

              {result.alignment && (
                <Card>
                  <CardHeader>Word-level comparison</CardHeader>
                  <CardBody>
                    <WordDiff alignment={result.alignment} />
                  </CardBody>
                </Card>
              )}

              {result.metrics && (
                <Card>
                  <CardHeader
                    right={
                      <span className="flex items-center gap-1.5 text-[11px] text-zinc-500">
                        <ArrowsLeftRight className="h-3.5 w-3.5" aria-hidden /> vs reference
                      </span>
                    }
                  >
                    Accuracy metrics
                  </CardHeader>
                  <CardBody>
                    <AudioMetricBars metrics={result.metrics} />
                  </CardBody>
                </Card>
              )}
            </>
          )}

          {mode === "wispr" && (
            <>
              {!wisprResult && !wisprBusy && (
                <Card>
                  <EmptyState
                    icon={<Waveform className="h-6 w-6" aria-hidden />}
                    title="No Wispr Flow capture scored yet"
                    hint="Enter the reference text, dictate it with Wispr Flow into the capture box, then score. Output is measured with the exact same metric layer as the engines."
                  />
                </Card>
              )}
              {wisprBusy && (
                <Card>
                  <CardBody className="space-y-3">
                    <div className="h-4 w-40 animate-pulse rounded bg-zinc-800" />
                    <div className="h-3 w-full animate-pulse rounded bg-zinc-800/70" />
                    <div className="h-3 w-3/5 animate-pulse rounded bg-zinc-800/70" />
                  </CardBody>
                </Card>
              )}
              {wisprResult && (
                <>
                  <Card>
                    <CardHeader
                      right={<Badge tone="green">{wisprResult.label || "wispr-flow-pro"}</Badge>}
                    >
                      Wispr Flow dictation
                    </CardHeader>
                    <CardBody>
                      <p className="text-[15px] leading-relaxed text-zinc-100">{wisprResult.hypothesis}</p>
                      <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 font-mono text-[11px] text-zinc-500">
                        <span>vs {wisprResult.reference.slice(0, 60)}{wisprResult.reference.length > 60 ? "…" : ""}</span>
                      </div>
                    </CardBody>
                  </Card>

                  {wisprResult.semantic.errors.length > 0 && (
                    <Card>
                      <CardHeader
                        right={
                          <Badge tone={wisprResult.semantic.meaning_preserved ? "green" : "red"}>
                            {wisprResult.semantic.meaning_preserved ? "meaning preserved" : "meaning changed"}
                          </Badge>
                        }
                      >
                        Semantic error analysis
                      </CardHeader>
                      <CardBody className="space-y-2">
                        {wisprResult.semantic.errors.map((err, i) => (
                          <div key={i} className="rounded-lg border border-zinc-800 bg-zinc-900/50 px-3 py-2">
                            <div className="flex items-center justify-between gap-2">
                              <span className="font-mono text-[11px] text-zinc-400">{err.type.replace(/_/g, " ")}</span>
                              <Badge tone={err.severity === "critical" ? "red" : err.severity === "major" ? "amber" : "zinc"}>
                                {err.severity}
                              </Badge>
                            </div>
                            <p className="mt-1 text-xs leading-relaxed text-zinc-400">{err.description}</p>
                          </div>
                        ))}
                      </CardBody>
                    </Card>
                  )}

                  {wisprResult.alignment && (
                    <Card>
                      <CardHeader>Word-level comparison</CardHeader>
                      <CardBody>
                        <WordDiff alignment={wisprResult.alignment} />
                      </CardBody>
                    </Card>
                  )}

                  <Card>
                    <CardHeader>Accuracy metrics</CardHeader>
                    <CardBody>
                      <AudioMetricBars metrics={wisprResult.metrics} />
                    </CardBody>
                  </Card>
                </>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
