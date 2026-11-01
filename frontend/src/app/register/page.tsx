"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight } from "@phosphor-icons/react";
import { useAuth } from "@/lib/auth-context";
import { Button, Input, Label } from "@/components/ui";
import { BrandMark } from "@/components/brand";

export default function RegisterPage() {
  const { register } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await register(email, password);
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
      setBusy(false);
    }
  }

  return (
    <main className="relative flex min-h-[100dvh] items-center justify-center overflow-hidden px-4">
      <div aria-hidden className="pointer-events-none absolute inset-0">
        <div className="absolute -top-40 left-1/2 h-[26rem] w-[44rem] -translate-x-1/2 rounded-full bg-emerald-500/[0.09] blur-[130px]" />
        <div className="absolute -bottom-48 left-1/4 h-80 w-96 rounded-full bg-teal-500/[0.05] blur-[110px]" />
      </div>

      <div className="rise relative w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center gap-4">
          <div className="drop-shadow-[0_0_24px_rgb(52_211_153/0.25)]">
            <BrandMark size={44} />
          </div>
          <div className="text-center">
            <p className="text-lg font-semibold tracking-tight">
              Vox<span className="text-emerald-400">Lab</span>
            </p>
            <p className="mt-1 text-sm text-zinc-500">Create your developer account</p>
          </div>
        </div>

        <div className="rounded-xl border border-white/[0.07] bg-zinc-900/60 p-6 shadow-[0_2px_6px_rgb(0_0_0/0.4),0_24px_64px_rgb(0_0_0/0.45),inset_0_1px_0_0_rgb(255_255_255/0.06)] backdrop-blur-xl">
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
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="new-password"
                required
              />
              <p className="mt-1.5 text-[11px] text-zinc-600">At least 8 characters.</p>
            </div>
            {error && (
              <p role="alert" className="rounded-lg border border-red-500/25 bg-red-500/10 px-3 py-2 text-xs text-red-300">
                {error}
              </p>
            )}
            <Button type="submit" className="w-full" disabled={busy}>
              {busy ? "Creating account…" : "Create account"}
              {!busy && <ArrowRight size={14} weight="bold" />}
            </Button>
          </form>
        </div>

        <p className="mt-5 text-center text-xs text-zinc-600">
          Already registered?{" "}
          <Link href="/login" className="text-emerald-400 transition-colors hover:text-emerald-300">
            Sign in
          </Link>
        </p>
      </div>
    </main>
  );
}
