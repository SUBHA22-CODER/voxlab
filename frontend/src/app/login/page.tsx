"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight } from "@phosphor-icons/react";
import { useAuth } from "@/lib/auth-context";
import { Button, Card, CardBody, Input, Label } from "@/components/ui";
import { BrandMark } from "@/components/brand";

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
    <main className="relative flex min-h-[100dvh] items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center gap-3">
          <BrandMark size={40} />
          <div className="text-center">
            <p className="text-lg font-semibold tracking-tight">
              Vox<span className="text-emerald-400">Lab</span>
            </p>
            <p className="mt-0.5 text-sm text-zinc-500">The voice AI crash-test lab</p>
          </div>
        </div>

        <Card className="border-zinc-800 bg-zinc-900/70 shadow-[0_8px_40px_rgb(0_0_0/0.35)]">
          <CardBody className="p-6">
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
                <p role="alert" className="rounded-lg border border-red-500/25 bg-red-500/10 px-3 py-2 text-xs text-red-400">
                  {error}
                </p>
              )}
              <Button type="submit" className="w-full" disabled={busy}>
                {busy ? "Signing in…" : "Sign in"}
                {!busy && <ArrowRight size={14} weight="bold" />}
              </Button>
            </form>
          </CardBody>
        </Card>

        <p className="mt-5 text-center text-xs text-zinc-600">
          No account?{" "}
          <Link href="/register" className="text-emerald-400 transition-colors hover:text-emerald-300">
            Register
          </Link>
          <span className="mx-1.5 text-zinc-700">·</span>
          Demo: demo@voxlab.dev / demo1234
        </p>
      </div>
    </main>
  );
}
