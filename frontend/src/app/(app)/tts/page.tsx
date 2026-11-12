"use client";

import { useEffect, useState } from "react";
import { SpeakerHigh, Play, Lightning, Sparkle, Clock, CheckCircle } from "@phosphor-icons/react";
import {
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  Input,
  Label,
  PageHeader,
} from "@/components/ui";

const VOICE_LANGUAGE_MAP: Record<string, string> = {
  Nalini: "hi-IN",
  Vikrant: "hi-IN",
  Deepak: "hi-IN",
  Bhavna: "hi-IN",
  Mehuli: "bn-IN",
  Oviya: "ta-IN",
  Kavin: "ta-IN",
  Saanvi: "te-IN",
  Pranav: "te-IN",
  Radhika: "kn-IN",
  Trupti: "mr-IN",
  Tanvi: "en-IN",
  Zayan: "en-IN",
};

const TTS_PRESETS = [
  {
    label: "Hindi Greetings",
    language: "hi-IN",
    voice: "Nalini",
    text: "नमस्ते, वॉक्सलैब में आपका स्वागत है। हम वॉयस एआई की विश्वसनीयता का परीक्षण करते हैं।",
  },
  {
    label: "Tamil Banking Query",
    language: "ta-IN",
    voice: "Oviya",
    text: "வணக்கம், உங்கள் கணக்கு இருப்பு விவரங்களை இப்போது சரிபார்க்கிறோம்.",
  },
  {
    label: "Bengali Customer Support",
    language: "bn-IN",
    voice: "Mehuli",
    text: "নমস্কার, আপনার অর্ডার সম্পর্কিত তথ্যের জন্য অপেক্ষা করার জন্য ধন্যবাদ।",
  },
  {
    label: "Telugu Order Update",
    language: "te-IN",
    voice: "Saanvi",
    text: "నమస్కారం, మీ ఆర్డర్ విజయవంతంగా డెలివరీ చేయబడింది.",
  },
  {
    label: "Indian English Voice",
    language: "en-IN",
    voice: "Tanvi",
    text: "Welcome to VoxLab reliability testing platform. Your voice agent pipeline is currently fully operational.",
  },
];

export default function TimbreTTSLabPage() {
  const [text, setText] = useState(TTS_PRESETS[0].text);
  const [voice, setVoice] = useState(TTS_PRESETS[0].voice);
  const [language, setLanguage] = useState(TTS_PRESETS[0].language);
  const [speed, setSpeed] = useState(1.0);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [latency, setLatency] = useState<number | null>(null);
  const [duration, setDuration] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const API_URL = (
    process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001"
  ).replace(/\/+$/, "");

  function loadPreset(preset: typeof TTS_PRESETS[0]) {
    setText(preset.text);
    setVoice(preset.voice);
    setLanguage(preset.language);
    setAudioUrl(null);
  }

  async function handleSynthesize() {
    if (!text.trim()) return;
    setLoading(true);
    setError(null);

    const token = typeof window !== "undefined" ? localStorage.getItem("voxlab_token") : null;
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const started = performance.now();
    try {
      const res = await fetch(`${API_URL}/api/v1/indic/tts/synthesize`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          text,
          voice,
          language,
          speed,
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
        throw new Error(errData.detail || "Synthesis request failed");
      }

      const elapsed = (performance.now() - started) / 1000;
      setLatency(elapsed);

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      setAudioUrl(url);

      const durHeader = res.headers.get("X-Duration-Seconds");
      if (durHeader) setDuration(parseFloat(durHeader));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "TTS synthesis failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Timbre TTS Speech Synthesis Lab"
        subtitle="Official Gnani AI Timbre Text-to-Speech (v2.5 / v3.0) with expressive Indian regional voices."
        actions={
          <Badge tone="green">
            <SpeakerHigh className="mr-1 inline h-3.5 w-3.5" />
            Timbre Expressive Voices
          </Badge>
        }
      />

      {error && (
        <div className="rounded-lg border border-amber-500/20 bg-amber-500/10 p-4 text-xs text-amber-300">
          <p className="font-semibold">Notice: {error}</p>
          <p className="mt-1 text-zinc-400">
            Live Timbre synthesis requires <code>GNANI_ENABLED=true</code> and <code>GNANI_API_KEY</code> configured on the backend.
          </p>
        </div>
      )}

      {/* Presets */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Lightning size={16} className="text-amber-400" />
            <span className="font-semibold text-zinc-100">Indic Speech Synthesis Presets</span>
          </div>
        </CardHeader>
        <CardBody>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
            {TTS_PRESETS.map((p, idx) => (
              <button
                key={idx}
                onClick={() => loadPreset(p)}
                className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-3 text-left transition hover:border-zinc-700 hover:bg-zinc-800/40"
              >
                <div className="text-xs font-semibold text-zinc-200">{p.label}</div>
                <div className="mt-1 flex items-center gap-1 text-[11px] text-zinc-500">
                  <span>{p.voice}</span> • <span>{p.language}</span>
                </div>
              </button>
            ))}
          </div>
        </CardBody>
      </Card>

      {/* Synthesis controls */}
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Sparkle size={16} className="text-emerald-400" />
              <span className="font-semibold text-zinc-100">Speech Generator Configuration</span>
            </div>
          </CardHeader>
          <CardBody className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label htmlFor="voice-select">Voice</Label>
                <select
                  id="voice-select"
                  value={voice}
                  onChange={(e) => {
                    const selected = e.target.value;
                    setVoice(selected);
                    if (VOICE_LANGUAGE_MAP[selected]) {
                      setLanguage(VOICE_LANGUAGE_MAP[selected]);
                    }
                  }}
                  className="w-full rounded-md border border-zinc-800 bg-zinc-950 px-3 py-2 text-xs text-zinc-200"
                >
                  <option value="Nalini">Nalini (Hindi Female - Expressive)</option>
                  <option value="Vikrant">Vikrant (Hindi Male - Conversational)</option>
                  <option value="Deepak">Deepak (Hindi Male - Clear)</option>
                  <option value="Bhavna">Bhavna (Hindi Female - Friendly)</option>
                  <option value="Mehuli">Mehuli (Bengali Female)</option>
                  <option value="Oviya">Oviya (Tamil Female)</option>
                  <option value="Kavin">Kavin (Tamil Male)</option>
                  <option value="Saanvi">Saanvi (Telugu Female)</option>
                  <option value="Pranav">Pranav (Telugu Male)</option>
                  <option value="Radhika">Radhika (Kannada Female)</option>
                  <option value="Trupti">Trupti (Marathi Female)</option>
                  <option value="Tanvi">Tanvi (Indian English Female)</option>
                  <option value="Zayan">Zayan (Indian English Male)</option>
                </select>
              </div>

              <div>
                <Label htmlFor="speed-slider">Speed: {speed.toFixed(1)}x</Label>
                <input
                  id="speed-slider"
                  type="range"
                  min="0.5"
                  max="2.0"
                  step="0.1"
                  value={speed}
                  onChange={(e) => setSpeed(parseFloat(e.target.value))}
                  className="mt-2 w-full accent-emerald-500"
                />
              </div>
            </div>

            <div>
              <Label htmlFor="tts-text">Input Text for Speech Synthesis</Label>
              <textarea
                id="tts-text"
                rows={4}
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Enter text to synthesize into high-fidelity Indian speech..."
                className="w-full rounded-md border border-zinc-800 bg-zinc-950 p-3 text-xs text-zinc-200 focus:border-emerald-500 focus:outline-none"
              />
            </div>

            <Button
              onClick={handleSynthesize}
              disabled={loading || !text.trim()}
              className="w-full"
            >
              {loading ? "Generating Speech Stream..." : "Generate Audio with Timbre TTS"}
            </Button>
          </CardBody>
        </Card>

        {/* Audio Output */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <SpeakerHigh size={16} className="text-emerald-400" />
              <span className="font-semibold text-zinc-100">Audio Playback & Latency Metrics</span>
            </div>
          </CardHeader>
          <CardBody className="space-y-4">
            {audioUrl ? (
              <div className="space-y-4">
                <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4 text-center">
                  <audio controls autoPlay src={audioUrl} className="w-full" />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-3">
                    <span className="text-[11px] font-medium text-zinc-500">Generation Latency</span>
                    <div className="mt-1 flex items-baseline gap-1 text-2xl font-bold text-emerald-400">
                      {latency ? `${(latency * 1000).toFixed(0)}` : "—"}
                      <span className="text-xs font-normal text-zinc-500">ms</span>
                    </div>
                  </div>

                  <div className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-3">
                    <span className="text-[11px] font-medium text-zinc-500">Audio Duration</span>
                    <div className="mt-1 flex items-baseline gap-1 text-2xl font-bold text-teal-400">
                      {duration ? `${duration.toFixed(2)}` : "—"}
                      <span className="text-xs font-normal text-zinc-500">sec</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2 text-xs text-emerald-400">
                  <CheckCircle size={16} weight="fill" />
                  Synthesized with {voice} ({language}) via Gnani Timbre
                </div>
              </div>
            ) : (
              <div className="flex h-48 flex-col items-center justify-center text-center text-xs text-zinc-500">
                <SpeakerHigh size={32} className="mb-2 text-zinc-700" />
                Select a preset and click &quot;Generate Audio with Timbre TTS&quot; to synthesize audio.
              </div>
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}

