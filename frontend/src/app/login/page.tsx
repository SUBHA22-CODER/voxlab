"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, ChartBar, Pulse, TrendUp } from "@phosphor-icons/react";
import { useAuth } from "@/lib/auth-context";
import { Button, Input, Label } from "@/components/ui";
import { BrandMark } from "@/components/brand";

const WAVEFORM = [
  0.35, 0.7, 0.45, 0.9, 0.6, 1.0, 0.5, 0.8, 0.4, 0.95, 0.55, 0.75, 0.3, 0.85, 0.5, 0.7, 0.45,
  0.9, 0.6, 0.4, 0.8, 0.35, 0.65, 0.95, 0.5, 0.75, 0.4, 0.85,
];

const FEATURES = [
  {
    icon: Pulse,
    text: "Scenario stress tests: interruptions, API failures, Hinglish, memory probes",
  },
  {
    icon: ChartBar,
    text: "Every conversation traced turn by turn with pipeline-level timings",
  },
  {
    icon: TrendUp,
    text: "Transparent weighted benchmarks you can compare across runs",
  },
];

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("demo@voxlab.dev");
  const [password, setPassword] = useState("demo1234");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
      setBusy(false);
    }
  }

  return (
    <main className="grid min-h-[100dvh] lg:grid-cols-2">
      {/* Brand panel */}
      <section className="relative hidden flex-col justify-between overflow-hidden border-r border-zinc-800/60 bg-zinc-950/60 p-12 lg:flex">
        <div aria-hidden className="pointer-events-none absolute inset-0">
          <div className="absolute -left-24 -top-32 h-96 w-96 rounded-full bg-emerald-500/[0.1] blur-[120px]" />
          <div className="absolute bottom-0 right-0 h-72 w-72 rounded-full bg-teal-500/[0.06] blur-[100px]" />
        </div>

        <div className="rise relative flex items-center gap-3">
          <BrandMark size={34} />
          <span className="text-[15px] font-semibold tracking-tight">
            Vox<span className="text-emerald-400">Lab</span>
          </span>
        </div>

        <div className="rise rise-1 relative max-w-md">
          <h1 className="text-[34px] font-semibold leading-[1.15] tracking-[-0.02em] text-zinc-50">
            Know if your voice agent survives real conversations.
          </h1>
          <p className="mt-4 text-[15px] leading-relaxed text-zinc-400">
            Build voice agents. Break them. Benchmark them. VoxLab finds the exact
            turn where your agent falls apart, and proves when a fix works.
          </p>

          <div className="mt-9 flex h-14 items-end gap-[5px]" aria-hidden>
            {WAVEFORM.map((h, i) => (
              <span
                key={i}
                className="eq-bar w-1.5 shrink-0 rounded-full bg-gradient-to-t from-emerald-500/30 to-emerald-400/80"
                style={{
                  height: `${h * 100}%`,
                  animationDelay: `${i * 0.09}s`,
                  animationDuration: `${1.3 + (i % 5) * 0.22}s`,
                }}
              />
            ))}
          </div>

          <ul className="mt-9 space-y-3.5">
            {FEATURES.map(({ icon: Icon, text }) => (
              <li key={text} className="flex items-start gap-3 text-[13px] leading-relaxed text-zinc-400">
                <Icon size={16} weight="duotone" className="mt-0.5 shrink-0 text-emerald-400" />
                {text}
              </li>
            ))}
          </ul>
        </div>

        <p className="rise rise-2 relative text-[11px] text-zinc-600">
          Testing, debugging and reliability infrastructure for voice AI agents.
        </p>
      </section>

      {/* Form panel */}
      <section className="relative flex items-center justify-center overflow-hidden px-4">
        <div aria-hidden className="pointer-events-none absolute inset-0 lg:hidden">
          <div className="absolute -top-40 left-1/2 h-[26rem] w-[44rem] -translate-x-1/2 rounded-full bg-emerald-500/[0.09] blur-[130px]" />
        </div>

        <div className="rise relative w-full max-w-sm">
          <div className="mb-8 flex flex-col items-center gap-4 lg:hidden">
            <div className="drop-shadow-[0_0_24px_rgb(52_211_153/0.25)]">
              <BrandMark size={44} />
            </div>
            <div className="text-center">
              <p className="text-lg font-semibold tracking-tight">
                Vox<span className="text-emerald-400">Lab</span>
              </p>
              <p className="mt-1 text-sm text-zinc-500">The voice AI crash-test lab</p>
            </div>
          </div>

          <div className="rounded-xl border border-white/[0.07] bg-zinc-900/60 p-6 shadow-[0_2px_6px_rgb(0_0_0/0.4),0_24px_64px_rgb(0_0_0/0.45),inset_0_1px_0_0_rgb(255_255_255/0.06)] backdrop-blur-xl">
            <h2 className="text-base font-semibold text-zinc-100">Welcome back</h2>
            <p className="mb-5 mt-1 text-xs text-zinc-500">Sign in to your developer workspace.</p>
            <form onSubmit={onSubmit} className="space-y-4">
              <div>
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="email"
                  required
                />
              </div>
              <div>
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                  required
                />
              </div>
              {error && (
                <p
                  role="alert"
                  className="rounded-lg border border-red-500/25 bg-red-500/10 px-3 py-2 text-xs text-red-300"
                >
                  {error}
                </p>
              )}
              <Button type="submit" className="w-full" disabled={busy}>
                {busy ? "Signing in…" : "Sign in"}
                {!busy && <ArrowRight size={14} weight="bold" />}
              </Button>
            </form>
          </div>

          <p className="mt-5 text-center text-xs text-zinc-600">
            No account?{" "}
            <Link href="/register" className="text-emerald-400 transition-colors hover:text-emerald-300">
              Register
            </Link>
            <span className="mx-1.5 text-zinc-700">·</span>
            Demo: demo@voxlab.dev / demo1234
          </p>
        </div>
      </section>
    </main>
  );
}
