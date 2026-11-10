"use client";

import { useEffect, useRef, useState } from "react";
import { Waveform, UploadSimple, Play, ArrowsLeftRight } from "@phosphor-icons/react";

import { AudioEngines, AudioTranscribe } from "@/lib/audio-api";
import type { EngineInfo, TranscriptionResult } from "@/lib/audio-types";
import { AudioMetricBars } from "@/components/audio/metric-bars";
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

      <div className="grid gap-5 lg:grid-cols-[400px_1fr]">
        <div className="space-y-5">
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

          <Card>
            <CardHeader>Reference transcript (optional)</CardHeader>
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
          {!result && !busy && (
            <Card>
              <EmptyState
                icon={<Waveform className="h-6 w-6" aria-hidden />}
                title="No transcription yet"
                hint="Upload a clip and press Transcribe. Add a reference transcript to unlock accuracy metrics."
              />
            </Card>
          )}

          {busy && (
            <Card>
              <CardBody className="space-y-3">
                <div className="h-4 w-40 animate-pulse rounded bg-zinc-800" />
                <div className="h-3 w-full animate-pulse rounded bg-zinc-800/70" />
                <div className="h-3 w-4/5 animate-pulse rounded bg-zinc-800/70" />
                <div className="h-3 w-3/5 animate-pulse rounded bg-zinc-800/70" />
              </CardBody>
            </Card>
          )}

          {result && (
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
        </div>
      </div>
    </div>
  );
}
