"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth-context";
import { Spinner } from "@/components/ui";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: "▦" },
  { href: "/playground", label: "Playground", icon: "🎙" },
  { href: "/agents", label: "Agents", icon: "🤖" },
  { href: "/scenarios", label: "Scenarios", icon: "⚡" },
  { href: "/runs", label: "Test Runs", icon: "📊" },
];

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner label="Loading VoxLab…" />
      </div>
    );
  }
  if (!user) return null;

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-56 shrink-0 flex-col border-r border-zinc-800 bg-zinc-950">
        <div className="px-5 py-5">
          <Link href="/dashboard" className="text-lg font-bold tracking-tight">
            Vox<span className="text-emerald-400">Lab</span>
          </Link>
          <p className="mt-0.5 text-[11px] uppercase tracking-widest text-zinc-600">
            Developer workspace
          </p>
        </div>
        <nav className="flex-1 space-y-1 px-3" aria-label="Main navigation">
          {NAV.map((item) => {
            const active = pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors ${
                  active
                    ? "bg-emerald-500/10 font-medium text-emerald-400"
                    : "text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200"
                }`}
              >
                <span aria-hidden className="text-xs">
                  {item.icon}
                </span>
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="border-t border-zinc-800 px-4 py-4">
          <p className="truncate text-xs text-zinc-400">{user.email}</p>
          <button
            onClick={logout}
            className="mt-1.5 text-xs text-zinc-500 transition-colors hover:text-zinc-300"
          >
            Sign out
          </button>
        </div>
      </aside>
      <main className="min-w-0 flex-1 overflow-x-hidden px-8 py-8">{children}</main>
    </div>
  );
}
