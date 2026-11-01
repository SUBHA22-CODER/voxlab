"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, ChartBar, Lightning, Pulse, TrendUp } from "@phosphor-icons/react";
import { useAuth } from "@/lib/auth-context";
import { Button, Input, Label } from "@/components/ui";
import { BrandMark } from "@/components/brand";

const WAVEFORM = [
  0.3, 0.55, 0.8, 0.5, 0.95, 0.65, 1.0, 0.45, 0.75, 0.55, 0.9, 0.4, 0.7, 1.0, 0.5, 0.85, 0.6,
  0.4, 0.95, 0.5, 0.75, 0.6, 1.0, 0.45, 0.8, 0.55, 0.9, 0.35,
];

const FEATURES = [
  {
    icon: Pulse,
    title: "Stress-test scenarios",
    text: "Interruptions, API failures, Hinglish, memory probes - shipped built in",
  },
  {
    icon: ChartBar,
    title: "Turn-level tracing",
    text: "STT, LLM, tools and TTS timed separately for every single turn",
  },
  {
    icon: TrendUp,
    title: "Benchmarks you can trust",
    text: "Transparent weighted scores, comparable across runs and agents",
  },
];

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("demo@voxlab.dev");
  const [password, setPassword] = useState("demo1234");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function signIn(emailValue: string, passwordValue: string) {
    setBusy(true);
    setError(null);
    try {
      await login(emailValue, passwordValue);
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
      setBusy(false);
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void signIn(email, password);
  }

  return (
    <main className="grid min-h-[100dvh] lg:grid-cols-2">
      {/* Brand panel */}
      <section className="relative hidden flex-col justify-between overflow-hidden border-r border-zinc-800/60 bg-zinc-950/70 p-12 xl:p-16">
        <div aria-hidden className="pointer-events-none absolute inset-0">
          <div className="absolute -left-24 -top-32 h-96 w-96 rounded-full bg-emerald-500/[0.12] blur-[130px]" />
          <div className="absolute bottom-0 right-0 h-80 w-80 rounded-full bg-teal-500/[0.06] blur-[110px]" />
        </div>

        <div className="rise relative flex items-center gap-3">
          <BrandMark size={34} />
          <span className="text-[15px] font-semibold tracking-tight">
            Vox<span className="text-emerald-400">Lab</span>
          </span>
        </div>

        <div className="rise rise-1 relative max-w-lg">
          <h1 className="text-[36px] font-semibold leading-[1.12] tracking-[-0.025em] text-zinc-50">
            Know if your voice agent survives{" "}
            <span className="bg-gradient-to-r from-emerald-300 to-teal-200 bg-clip-text text-transparent">
              real conversations
            </span>
            .
          </h1>
          <p className="mt-5 text-[15px] leading-relaxed text-zinc-400">
            VoxLab runs hostile scenarios against your agent, traces the exact turn
            where it breaks, and proves when a fix actually works.
          </p>

          <div className="relative mt-10">
            <div aria-hidden className="absolute inset-x-0 top-1/2 h-px bg-zinc-800/80" />
            <div className="relative flex h-20 items-center gap-[6px]">
              {WAVEFORM.map((h, i) => (
                <span
                  key={i}
                  aria-hidden
                  className="eq-bar w-2 shrink-0 rounded-full bg-gradient-to-t from-emerald-600/40 to-emerald-300 shadow-[0_0_14px_rgb(52_211_153/0.3)]"
                  style={{
                    height: `${h * 100}%`,
                    animationDelay: `${i * 0.08}s`,
                    animationDuration: `${1.3 + (i % 5) * 0.22}s`,
                  }}
                />
              ))}
            </div>
          </div>

          <ul className="mt-10 space-y-5">
            {FEATURES.map(({ icon: Icon, title, text }) => (
              <li key={title} className="flex items-start gap-3.5">
                <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-zinc-800 bg-zinc-900/80 text-emerald-400">
                  <Icon size={15} weight="duotone" />
                </span>
                <div>
                  <p className="text-[13px] font-medium text-zinc-200">{title}</p>
                  <p className="mt-0.5 text-xs leading-relaxed text-zinc-500">{text}</p>
                </div>
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
            <div className="my-4 flex items-center gap-3" aria-hidden>
              <span className="h-px flex-1 bg-zinc-800" />
              <span className="text-[10px] uppercase tracking-wider text-zinc-600">or</span>
              <span className="h-px flex-1 bg-zinc-800" />
            </div>
            <Button
              variant="secondary"
              className="w-full"
              disabled={busy}
              onClick={() => void signIn("demo@voxlab.dev", "demo1234")}
            >
              <Lightning size={13} weight="fill" />
              Explore with the demo account
            </Button>
          </div>

          <p className="mt-5 text-center text-xs text-zinc-600">
            No account?{" "}
            <Link href="/register" className="text-emerald-400 transition-colors hover:text-emerald-300">
              Register
            </Link>
          </p>
        </div>
      </section>
    </main>
  );
}
