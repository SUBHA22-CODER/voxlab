"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import {
  ChartBar,
  ChartLine,
  Dna,
  Flask,
  Globe,
  Lightning,
  Microphone,
  Robot,
  SignOut,
  SpeakerHigh,
  SquaresFour,
  Stack,
  Waveform,
} from "@phosphor-icons/react";
import { useAuth } from "@/lib/auth-context";
import { Skeleton } from "@/components/ui";
import { BrandMark } from "@/components/brand";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: SquaresFour },
  { href: "/playground", label: "Playground", icon: Microphone },
  { href: "/audio", label: "Audio Lab", icon: Waveform },
  { href: "/benchmarks", label: "Benchmarks", icon: ChartLine },
  { href: "/analytics", label: "Analytics", icon: ChartBar },
  { href: "/agents", label: "Agents", icon: Robot },
  { href: "/scenarios", label: "Scenarios", icon: Lightning },
  { href: "/runs", label: "Test Runs", icon: ChartBar },
  { href: "/darwin", label: "Darwin Fuzzing", icon: Dna },
  { href: "/audio/darwin", label: "Darwin Audio", icon: Waveform },
  { href: "/regressions", label: "Regressions", icon: Flask },
  { href: "/indic", label: "Indic Speech Lab", icon: Globe },
  { href: "/tts", label: "TTS Lab", icon: SpeakerHigh },
  { href: "/providers", label: "Providers", icon: Stack },
];

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!loading && !user) router.replace("/register");
  }, [loading, user, router]);

  if (loading) {
    return (
      <div className="flex min-h-[100dvh]">
        <div className="hidden w-60 shrink-0 border-r border-zinc-800/60 p-5 lg:block">
          <Skeleton className="h-7 w-28" />
          <div className="mt-8 space-y-2">
            {["w-40", "w-36", "w-44", "w-32", "w-40"].map((w, i) => (
              <Skeleton key={i} className={`h-8 ${w}`} />
            ))}
          </div>
        </div>
        <div className="flex-1 p-8">
          <Skeleton className="h-8 w-56" />
          <Skeleton className="mt-2 h-4 w-80" />
          <div className="mt-8 grid gap-4 sm:grid-cols-3">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-24 rounded-xl" />
            ))}
          </div>
          <Skeleton className="mt-6 h-64 rounded-xl" />
        </div>
      </div>
    );
  }
  if (!user) return null;

  const initials = user.email.slice(0, 2).toUpperCase();

  return (
    <div className="flex min-h-[100dvh]">
      <aside className="sticky top-0 flex h-[100dvh] w-60 shrink-0 flex-col border-r border-zinc-800/60 bg-zinc-950/80">
        <div className="flex items-center gap-2.5 px-5 pb-6 pt-5">
          <Link href="/dashboard" aria-label="VoxLab home" className="flex items-center gap-2.5">
            <BrandMark />
            <span className="text-[15px] font-semibold tracking-tight text-zinc-100">
              Vox<span className="text-emerald-400">Lab</span>
            </span>
          </Link>
        </div>
        <nav className="flex-1 space-y-0.5 px-3" aria-label="Main navigation">
          {NAV.map((item) => {
            const active = pathname.startsWith(item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`flex items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] transition-colors duration-150 ${
                  active
                    ? "bg-emerald-500/10 font-medium text-emerald-300"
                    : "text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200"
                }`}
              >
                <Icon
                  size={16}
                  weight={active ? "fill" : "regular"}
                  className={active ? "text-emerald-400" : "text-zinc-500"}
                />
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="border-t border-zinc-800/60 p-3">
          <div className="flex items-center gap-2.5 rounded-lg px-2 py-2">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-zinc-800 text-[10px] font-semibold text-zinc-300">
              {initials}
            </span>
            <p className="min-w-0 flex-1 truncate text-xs text-zinc-400">{user.email}</p>
            <button
              onClick={logout}
              aria-label="Sign out"
              title="Sign out"
              className="rounded-md p-1.5 text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-zinc-300"
            >
              <SignOut size={14} />
            </button>
          </div>
        </div>
      </aside>
      <main className="min-w-0 flex-1 px-8 py-8 max-[768px]:px-4 max-[768px]:py-6">{children}</main>
    </div>
  );
}
