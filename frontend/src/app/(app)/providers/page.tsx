"use client";

import { useEffect, useState } from "react";
import {
  CheckCircle,
  Warning,
  XCircle,
  Globe,
  Microphone,
  SpeakerHigh,
  ArrowsLeftRight,
  Lightning,
} from "@phosphor-icons/react";
import {
  Badge,
  Card,
  CardBody,
  CardHeader,
  PageHeader,
} from "@/components/ui";

interface ProviderCapabilities {
  [key: string]: boolean | number | string | string[];
}

interface ProviderHealth {
  status: string;
  stt_model: string;
  tts_model: string;
  base_url: string;
  has_api_key: boolean;
  supported_languages_count: number;
  detail: string;
}

interface Provider {
  id: string;
  name: string;
  category: string;
  status: string;
  capabilities: ProviderCapabilities;
  models?: {
    stt: string;
    tts: string;
  };
  health?: ProviderHealth;
  description: string;
  attribution: string;
}

interface LocalEngine {
  engine_id: string;
  display_name: string;
  installed: boolean;
  version?: string;
  model?: string;
}

export default function ProvidersPage() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [localEngines, setLocalEngines] = useState<LocalEngine[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const API_URL = (
    process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001"
  ).replace(/\/+$/, "");

  useEffect(() => {
    const token =
      typeof window !== "undefined"
        ? localStorage.getItem("voxlab_token")
        : null;
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (token) headers["Authorization"] = `Bearer ${token}`;

    fetch(`${API_URL}/api/v1/providers`, { headers })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data) => {
        if (data.providers) setProviders(data.providers);
        if (data.local_speech_engines) setLocalEngines(data.local_speech_engines);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [API_URL]);

  function statusIcon(status: string) {
    if (status === "active" || status === "healthy")
      return <CheckCircle size={18} weight="fill" className="text-emerald-400" />;
    if (status === "unconfigured")
      return <Warning size={18} weight="fill" className="text-amber-400" />;
    return <XCircle size={18} weight="fill" className="text-red-400" />;
  }

  function statusBadge(status: string) {
    const tones: Record<string, "green" | "amber" | "red" | "zinc"> = {
      active: "green",
      healthy: "green",
      unconfigured: "amber",
      error: "red",
    };
    return (
      <Badge tone={tones[status] || "zinc"}>
        {status.toUpperCase()}
      </Badge>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Provider Dashboard"
        subtitle="Real-time status and capabilities of all integrated speech and dictation providers."
        actions={
          <Badge tone="green">
            <ArrowsLeftRight className="mr-1 inline h-3.5 w-3.5" />
            {providers.length} Provider{providers.length !== 1 ? "s" : ""} •{" "}
            {localEngines.filter((e) => e.installed).length} Local Engine
            {localEngines.filter((e) => e.installed).length !== 1 ? "s" : ""}
          </Badge>
        }
      />

      {error && (
        <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-4 text-xs text-red-300">
          {error}
        </div>
      )}

      {loading ? (
        <div className="py-16 text-center text-sm text-zinc-500">
          Loading provider status...
        </div>
      ) : (
        <>
          {/* Cloud providers */}
          <div className="grid gap-6 lg:grid-cols-2">
            {providers.map((p) => (
              <Card key={p.id}>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {statusIcon(p.status)}
                      <span className="font-semibold text-zinc-100">
                        {p.name}
                      </span>
                    </div>
                    {statusBadge(p.status)}
                  </div>
                </CardHeader>
                <CardBody className="space-y-4">
                  <p className="text-xs text-zinc-400">{p.description}</p>

                  {p.models && (
                    <div className="grid grid-cols-2 gap-3">
                      <div className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-3">
                        <div className="flex items-center gap-1.5">
                          <Microphone
                            size={14}
                            className="text-emerald-400"
                          />
                          <span className="text-[11px] font-medium text-zinc-500">
                            STT Model
                          </span>
                        </div>
                        <div className="mt-1 text-sm font-semibold text-zinc-200">
                          {p.models.stt}
                        </div>
                      </div>
                      <div className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-3">
                        <div className="flex items-center gap-1.5">
                          <SpeakerHigh
                            size={14}
                            className="text-teal-400"
                          />
                          <span className="text-[11px] font-medium text-zinc-500">
                            TTS Model
                          </span>
                        </div>
                        <div className="mt-1 text-sm font-semibold text-zinc-200">
                          {p.models.tts}
                        </div>
                      </div>
                    </div>
                  )}

                  {p.health && (
                    <div className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-3 text-xs">
                      <div className="flex items-center gap-1.5 font-semibold text-zinc-300">
                        <Lightning size={12} className="text-amber-400" />
                        Health Check
                      </div>
                      <div className="mt-2 space-y-1 text-zinc-400">
                        <div>
                          API Key:{" "}
                          {p.health.has_api_key ? (
                            <span className="text-emerald-400">Configured</span>
                          ) : (
                            <span className="text-red-400">Missing</span>
                          )}
                        </div>
                        <div>
                          Languages: {p.health.supported_languages_count}
                        </div>
                        <div className="text-[11px] text-zinc-500">
                          {p.health.detail}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Capabilities */}
                  <div className="flex flex-wrap gap-1.5">
                    {Object.entries(p.capabilities)
                      .filter(
                        ([, v]) =>
                          typeof v === "boolean" && v === true
                      )
                      .map(([key]) => (
                        <Badge
                          key={key}
                          tone="zinc"
                        >
                          {key.replace(/_/g, " ")}
                        </Badge>
                      ))}
                  </div>

                  <div className="text-[11px] text-zinc-600">
                    {p.attribution}
                  </div>
                </CardBody>
              </Card>
            ))}
          </div>

          {/* Local engines */}
          {localEngines.length > 0 && (
            <Card>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Globe size={16} className="text-teal-400" />
                  <span className="font-semibold text-zinc-100">
                    Local Speech Engines
                  </span>
                </div>
              </CardHeader>
              <CardBody>
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {localEngines.map((e) => (
                    <div
                      key={e.engine_id}
                      className="flex items-center justify-between rounded-lg border border-zinc-800 bg-zinc-950/60 p-3"
                    >
                      <div>
                        <div className="text-xs font-semibold text-zinc-200">
                          {e.display_name}
                        </div>
                        <div className="mt-0.5 text-[11px] text-zinc-500">
                          {e.model || e.engine_id}
                          {e.version ? ` v${e.version}` : ""}
                        </div>
                      </div>
                      {e.installed ? (
                        <CheckCircle
                          size={16}
                          weight="fill"
                          className="text-emerald-400"
                        />
                      ) : (
                        <XCircle
                          size={16}
                          weight="fill"
                          className="text-zinc-600"
                        />
                      )}
                    </div>
                  ))}
                </div>
              </CardBody>
            </Card>
          )}
        </>
      )}
    </div>
  );
}

