"use client";

import { useEffect, useState } from "react";
import {
  Globe,
  CheckCircle,
  Lightning,
  ArrowsLeftRight,
  ShieldCheck,
  Tag,
  Hash,
} from "@phosphor-icons/react";
import {
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  Input,
  Label,
  PageHeader,
  Select,
} from "@/components/ui";

interface IndicLanguage {
  code: string;
  name: string;
  native_name: string;
  script: string;
  supports_stt: boolean;
  supports_tts: boolean;
  default_voice: string;
  code_switch_variant?: string;
}

interface BenchmarkItem {
  id: string;
  language: string;
  category: string;
  reference_transcript: string;
  description: string;
  expected_entities?: string[];
  expected_numbers?: string[];
  english_loanwords?: string[];
}

interface EvaluationReport {
  raw_wer: number;
  raw_cer: number;
  normalized_wer: number;
  normalized_cer: number;
  code_switch_ratio: number;
  loanword_accuracy: number | null;
  entity_accuracy: number | null;
  details: {
    raw_substitutions: number;
    raw_deletions: number;
    raw_insertions: number;
    norm_substitutions: number;
    norm_deletions: number;
    norm_insertions: number;
  };
}

export default function IndicSpeechLabPage() {
  const [languages, setLanguages] = useState<IndicLanguage[]>([]);
  const [benchmarks, setBenchmarks] = useState<BenchmarkItem[]>([]);
  const [selectedLang, setSelectedLang] = useState("hi-IN");
  const [reference, setReference] = useState("");
  const [hypothesis, setHypothesis] = useState("");
  const [report, setReport] = useState<EvaluationReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const API_URL = (
    process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001"
  ).replace(/\/+$/, "");

  useEffect(() => {
    const token = typeof window !== "undefined" ? localStorage.getItem("voxlab_token") : null;
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;

    fetch(`${API_URL}/api/v1/indic/languages`, { headers })
      .then((r) => r.json())
      .then((data) => {
        if (data.languages) setLanguages(data.languages);
      })
      .catch((err) => setError(err.message));

    fetch(`${API_URL}/api/v1/indic/benchmarks`, { headers })
      .then((r) => r.json())
      .then((data) => {
        if (data.items) {
          setBenchmarks(data.items);
          if (data.items.length > 0) {
            setReference(data.items[1].reference_transcript); // Hinglish default
            setHypothesis(data.items[1].reference_transcript.replace("refund", "refand"));
          }
        }
      })
      .catch((err) => setError(err.message));
  }, [API_URL]);

  function loadBenchmark(id: string) {
    const item = benchmarks.find((b) => b.id === id);
    if (item) {
      setReference(item.reference_transcript);
      setHypothesis(item.reference_transcript);
      setSelectedLang(item.language);
      setReport(null);
    }
  }

  async function handleEvaluate() {
    if (!reference.trim()) return;
    setLoading(true);
    setError(null);

    const token = typeof window !== "undefined" ? localStorage.getItem("voxlab_token") : null;
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;

    try {
      const res = await fetch(`${API_URL}/api/v1/indic/evaluate`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          reference,
          hypothesis,
        }),
      });
      if (!res.ok) throw new Error(`Evaluation failed with status ${res.status}`);
      const data = await res.json();
      setReport(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Evaluation failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Indic Speech Lab"
        subtitle="Dual-layer verbatim & normalized reliability benchmarking for 12+ Indian languages and code-switching dialects (Gnani AI Prisma STT)."
        actions={
          <Badge tone="green">
            <Globe className="mr-1 inline h-3.5 w-3.5" />
            12 Indic Languages & Code-Switching
          </Badge>
        }
      />

      {error && (
        <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-4 text-xs text-red-300">
          {error}
        </div>
      )}

      {/* Preset benchmark scenarios */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Lightning size={16} className="text-amber-400" />
            <span className="font-semibold text-zinc-100">Reproducible Indic Benchmark Presets</span>
          </div>
        </CardHeader>
        <CardBody className="space-y-3">
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            {benchmarks.map((b) => (
              <button
                key={b.id}
                onClick={() => loadBenchmark(b.id)}
                className="flex flex-col items-start rounded-lg border border-zinc-800 bg-zinc-900/40 p-3 text-left transition hover:border-zinc-700 hover:bg-zinc-800/40"
              >
                <div className="flex w-full items-center justify-between text-xs font-semibold text-zinc-200">
                  <span>{b.id}</span>
                  <Badge tone="zinc">{b.category.toUpperCase()}</Badge>
                </div>
                <p className="mt-1 line-clamp-2 text-xs text-zinc-400">{b.description}</p>
              </button>
            ))}
          </div>
        </CardBody>
      </Card>

      {/* Test Form */}
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <ArrowsLeftRight size={16} className="text-emerald-400" />
              <span className="font-semibold text-zinc-100">Test Utterance & Hypothesis</span>
            </div>
          </CardHeader>
          <CardBody className="space-y-4">
            <div>
              <Label htmlFor="lang-select">Target Indic Language</Label>
              <select
                id="lang-select"
                value={selectedLang}
                onChange={(e) => setSelectedLang(e.target.value)}
                className="w-full rounded-md border border-zinc-800 bg-zinc-950 px-3 py-2 text-xs text-zinc-200"
              >
                {languages.map((l) => (
                  <option key={l.code} value={l.code}>
                    {l.name} ({l.native_name}) — {l.script}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <Label htmlFor="ref-text">Ground-Truth Reference Transcript</Label>
              <textarea
                id="ref-text"
                rows={3}
                value={reference}
                onChange={(e) => setReference(e.target.value)}
                placeholder="Enter verified reference in Devanagari, regional script, or Hinglish..."
                className="w-full rounded-md border border-zinc-800 bg-zinc-950 p-3 text-xs text-zinc-200 focus:border-emerald-500 focus:outline-none"
              />
            </div>

            <div>
              <Label htmlFor="hyp-text">ASR Recognized Hypothesis Transcript</Label>
              <textarea
                id="hyp-text"
                rows={3}
                value={hypothesis}
                onChange={(e) => setHypothesis(e.target.value)}
                placeholder="Enter or paste model hypothesis to score..."
                className="w-full rounded-md border border-zinc-800 bg-zinc-950 p-3 text-xs text-zinc-200 focus:border-emerald-500 focus:outline-none"
              />
            </div>

            <Button
              onClick={handleEvaluate}
              disabled={loading || !reference.trim()}
              className="w-full"
            >
              {loading ? "Computing Indic Metrics..." : "Evaluate Transcription"}
            </Button>
          </CardBody>
        </Card>

        {/* Evaluation Results */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <ShieldCheck size={16} className="text-emerald-400" />
              <span className="font-semibold text-zinc-100">Dual-Layer Benchmark Report</span>
            </div>
          </CardHeader>
          <CardBody className="space-y-4">
            {report ? (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-3">
                    <span className="text-[11px] font-medium text-zinc-500">Indic-Normalized WER</span>
                    <div className="mt-1 flex items-baseline gap-2">
                      <span className="text-2xl font-bold text-emerald-400">
                        {(report.normalized_wer * 100).toFixed(1)}%
                      </span>
                      <span className="text-xs text-zinc-500">
                        (Raw: {(report.raw_wer * 100).toFixed(1)}%)
                      </span>
                    </div>
                  </div>

                  <div className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-3">
                    <span className="text-[11px] font-medium text-zinc-500">Indic-Normalized CER</span>
                    <div className="mt-1 flex items-baseline gap-2">
                      <span className="text-2xl font-bold text-teal-400">
                        {(report.normalized_cer * 100).toFixed(1)}%
                      </span>
                      <span className="text-xs text-zinc-500">
                        (Raw: {(report.raw_cer * 100).toFixed(1)}%)
                      </span>
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-3">
                    <span className="text-[11px] font-medium text-zinc-500">Code-Switch Ratio</span>
                    <div className="mt-1 text-lg font-semibold text-amber-400">
                      {(report.code_switch_ratio * 100).toFixed(1)}% Latin
                    </div>
                  </div>

                  <div className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-3">
                    <span className="text-[11px] font-medium text-zinc-500">Loanword Accuracy</span>
                    <div className="mt-1 text-lg font-semibold text-blue-400">
                      {report.loanword_accuracy !== null
                        ? `${(report.loanword_accuracy * 100).toFixed(1)}%`
                        : "N/A"}
                    </div>
                  </div>
                </div>

                <div className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-3 text-xs text-zinc-400">
                  <span className="font-semibold text-zinc-300">Detailed Alignment Operations:</span>
                  <div className="mt-2 grid grid-cols-3 gap-2 text-center text-[11px]">
                    <div className="rounded bg-zinc-900 p-1.5">
                      <span className="text-red-400 font-semibold">{report.details.norm_substitutions}</span> Substitutions
                    </div>
                    <div className="rounded bg-zinc-900 p-1.5">
                      <span className="text-amber-400 font-semibold">{report.details.norm_deletions}</span> Deletions
                    </div>
                    <div className="rounded bg-zinc-900 p-1.5">
                      <span className="text-blue-400 font-semibold">{report.details.norm_insertions}</span> Insertions
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex h-48 flex-col items-center justify-center text-center text-xs text-zinc-500">
                <Globe size={32} className="mb-2 text-zinc-700" />
                Select a benchmark preset or enter text and click &quot;Evaluate Transcription&quot; to see the dual-layer report.
              </div>
            )}

            <div className="rounded-lg border border-emerald-500/10 bg-emerald-500/[0.04] p-3 text-[11px] text-zinc-400 leading-relaxed">
              <span className="font-semibold text-emerald-400">Why Indic Normalization Matters:</span>
              <p className="mt-1">
                Standard Western WER punishes Indic models unfairly for script variations: Devanagari numerals (१२३ vs 123),
                Dandas (। vs .), and Unicode NFC decomposition. VoxLab provides both raw and normalized metrics for scientific accuracy.
              </p>
            </div>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}

