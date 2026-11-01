"use client";

import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";

type ButtonVariant = "primary" | "secondary" | "danger" | "ghost";
type ButtonSize = "sm" | "md";

const buttonStyles: Record<ButtonVariant, string> = {
  primary:
    "bg-emerald-500 text-zinc-950 hover:bg-emerald-400 disabled:bg-emerald-500/40 disabled:text-zinc-950/50 shadow-[0_1px_0_0_rgb(255_255_255/0.15)_inset]",
  secondary:
    "bg-zinc-800/80 text-zinc-100 hover:bg-zinc-700/80 border border-zinc-700/80",
  danger: "bg-red-500/90 text-white hover:bg-red-500",
  ghost: "bg-transparent text-zinc-400 hover:bg-zinc-800/60 hover:text-zinc-200",
};

const buttonSizes: Record<ButtonSize, string> = {
  sm: "h-8 px-3 text-xs gap-1.5",
  md: "h-9.5 px-4 text-sm gap-2",
};

export function Button({
  variant = "primary",
  size = "md",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; size?: ButtonSize }) {
  return (
    <button
      className={`inline-flex select-none items-center justify-center rounded-lg font-medium transition-all duration-150 active:translate-y-px active:scale-[0.99] disabled:cursor-not-allowed disabled:active:translate-y-0 ${buttonStyles[variant]} ${buttonSizes[size]} ${className}`}
      {...props}
    />
  );
}

const fieldStyles =
  "w-full rounded-lg border border-zinc-800 bg-zinc-900/70 px-3 text-sm text-zinc-100 placeholder:text-zinc-600 transition-colors hover:border-zinc-700 focus:border-emerald-500/60 focus:outline-none focus:ring-2 focus:ring-emerald-500/20";

export function Input({ className = "", ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={`${fieldStyles} h-9.5 ${className}`} {...props} />;
}

export function Textarea({ className = "", ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={`${fieldStyles} py-2 ${className}`} {...props} />;
}

export function Select({ className = "", ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={`${fieldStyles} h-9.5 ${className}`} {...props} />;
}

export function Label({ children, htmlFor }: { children: ReactNode; htmlFor?: string }) {
  return (
    <label htmlFor={htmlFor} className="mb-1.5 block text-[11px] font-medium uppercase tracking-wider text-zinc-500">
      {children}
    </label>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={`rounded-xl border border-zinc-800/80 bg-zinc-900/40 shadow-[0_1px_2px_rgb(0_0_0/0.3)] ${className}`}
    >
      {children}
    </div>
  );
}

export function CardHeader({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`border-b border-zinc-800/80 px-5 py-3.5 text-sm font-medium text-zinc-200 ${className}`}>
      {children}
    </div>
  );
}

export function CardBody({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`p-5 ${className}`}>{children}</div>;
}

type BadgeTone = "green" | "red" | "amber" | "zinc" | "blue";

const badgeTones: Record<BadgeTone, string> = {
  green: "text-emerald-400 border-emerald-500/25 bg-emerald-500/10",
  red: "text-red-400 border-red-500/25 bg-red-500/10",
  amber: "text-amber-400 border-amber-500/25 bg-amber-500/10",
  zinc: "text-zinc-400 border-zinc-600/40 bg-zinc-500/10",
  blue: "text-sky-400 border-sky-500/25 bg-sky-500/10",
};

export function Badge({
  tone = "zinc",
  children,
  dot = false,
  pulse = false,
}: {
  tone?: BadgeTone;
  children: ReactNode;
  dot?: boolean;
  pulse?: boolean;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-medium ${badgeTones[tone]}`}
    >
      {dot && <span aria-hidden className={`h-1.5 w-1.5 rounded-full bg-current ${pulse ? "live-dot" : ""}`} />}
      {children}
    </span>
  );
}

const STATUS_TONES: Record<string, { tone: BadgeTone; pulse?: boolean }> = {
  completed: { tone: "green" },
  passed: { tone: "green" },
  connected: { tone: "green" },
  failed: { tone: "red" },
  unreachable: { tone: "red" },
  running: { tone: "amber", pulse: true },
  queued: { tone: "zinc" },
  untested: { tone: "zinc" },
  cancelled: { tone: "zinc" },
};

export function StatusBadge({ status }: { status: string }) {
  const entry = STATUS_TONES[status] ?? { tone: "blue" as BadgeTone };
  return (
    <Badge tone={entry.tone} dot pulse={entry.pulse}>
      {status}
    </Badge>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div aria-hidden className={`skeleton ${className}`} />;
}

export function EmptyState({
  icon,
  title,
  hint,
  action,
}: {
  icon?: ReactNode;
  title: string;
  hint?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 px-6 py-16 text-center">
      {icon && (
        <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-zinc-800 bg-zinc-900 text-zinc-500">
          {icon}
        </div>
      )}
      <div>
        <p className="text-sm font-medium text-zinc-300">{title}</p>
        {hint && <p className="mx-auto mt-1 max-w-sm text-xs leading-relaxed text-zinc-500">{hint}</p>}
      </div>
      {action}
    </div>
  );
}

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-7 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-[22px] font-semibold tracking-tight text-zinc-50">{title}</h1>
        {subtitle && <p className="mt-1 max-w-2xl text-sm leading-relaxed text-zinc-400">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}

/** Section heading without the eyebrow-cliché; weight + size carry hierarchy. */
export function SectionTitle({ children, right }: { children: ReactNode; right?: ReactNode }) {
  return (
    <div className="mb-3 flex items-center justify-between">
      <h2 className="text-sm font-semibold text-zinc-200">{children}</h2>
      {right}
    </div>
  );
}
