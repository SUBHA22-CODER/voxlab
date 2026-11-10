"use client";

import { useRef, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";

type ButtonVariant = "primary" | "secondary" | "danger" | "ghost";
type ButtonSize = "sm" | "md";

const buttonStyles: Record<ButtonVariant, string> = {
  primary:
    "bg-emerald-500 text-zinc-950 hover:bg-emerald-400 disabled:bg-emerald-500/40 disabled:text-zinc-950/50 shadow-[0_1px_0_0_rgb(255_255_255/0.2)_inset,0_4px_12px_rgb(16_185_129/0.25)]",
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
      className={`inline-flex select-none items-center justify-center rounded-lg font-medium transition-all duration-150 active:translate-y-px active:scale-[0.99] disabled:cursor-not-allowed disabled:active:translate-y-0 disabled:shadow-none ${buttonStyles[variant]} ${buttonSizes[size]} ${className}`}
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

/** Elevated panel with inner top light. Pass `spotlight` for pointer glow. */
export function Card({
  children,
  className = "",
  spotlight = false,
}: {
  children: ReactNode;
  className?: string;
  spotlight?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);

  function onPointerMove(e: React.PointerEvent<HTMLDivElement>) {
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    el.style.setProperty("--mx", `${e.clientX - rect.left}px`);
    el.style.setProperty("--my", `${e.clientY - rect.top}px`);
  }

  return (
    <div
      ref={ref}
      onPointerMove={spotlight ? onPointerMove : undefined}
      className={`surface rounded-xl border border-zinc-800/70 ${spotlight ? "spotlight" : ""} ${className}`}
    >
      {children}
    </div>
  );
}

export function CardHeader({
  children,
  className = "",
  right,
}: {
  children: ReactNode;
  className?: string;
  right?: ReactNode;
}) {
  return (
    <div className={`flex items-center justify-between gap-3 border-b border-zinc-800/60 px-5 py-3.5 text-sm font-medium text-zinc-200 ${className}`}>
      {children}
      {right}
    </div>
  );
}

export function CardBody({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`p-5 ${className}`}>{children}</div>;
}

type BadgeTone = "green" | "red" | "amber" | "zinc" | "blue";

const badgeTones: Record<BadgeTone, string> = {
  green: "text-emerald-300 border-emerald-500/25 bg-emerald-500/[0.08]",
  red: "text-red-300 border-red-500/25 bg-red-500/[0.08]",
  amber: "text-amber-300 border-amber-500/25 bg-amber-500/[0.08]",
  zinc: "text-zinc-400 border-zinc-600/40 bg-zinc-500/[0.08]",
  blue: "text-sky-300 border-sky-500/25 bg-sky-500/[0.08]",
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
        <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-zinc-800 bg-zinc-900/80 text-zinc-500 shadow-[inset_0_1px_0_0_rgb(255_255_255/0.05)]">
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
    <div className="rise mb-7 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-[24px] font-semibold leading-tight tracking-[-0.02em] text-zinc-50">{title}</h1>
        {subtitle && <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-zinc-400">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}

/** Section heading; weight + size carry hierarchy. */
export function SectionTitle({ children, right }: { children: ReactNode; right?: ReactNode }) {
  return (
    <div className="mb-3 flex items-center justify-between">
      <h2 className="text-sm font-semibold text-zinc-200">{children}</h2>
      {right}
    </div>
  );
}
