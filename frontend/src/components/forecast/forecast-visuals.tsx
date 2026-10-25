"use client";
import type { ReactNode } from "react";
import { formatAmount } from "@/lib/format";
import type { Unit } from "@/lib/contracts";
import { finite } from "@/components/dashboard/forecast-derive";
import { EFFECT_FILL, directionOf } from "@/components/shared/tone";

/** Explicit units always. Unknown units print their code instead of being coerced to USD. */
export function amount(v: unknown, unit: string, compact = false): string {
  const n = finite(v);
  if (n === undefined) return "Unavailable";
  const u = unit.toLowerCase();
  if (u === "usd" || u === "credits" || u === "tokens") return formatAmount(n, u as Unit, { compact });
  return `${new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(n)} ${unit}`;
}
export function exact(v: unknown, unit: string): string {
  const n = finite(v);
  return n === undefined ? "Unavailable" : `${new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(n)} ${unit.toUpperCase()}`;
}

/**
 * Scenario range drawn over a shared BulletBar. `domain` must match the bar's own scale
 * (max of allotment, projected, recorded); a range past it is clipped at the edge.
 */
export function RangeBand({ low, high, domain, children }: { low?: number; high?: number; domain: number; children: ReactNode }) {
  const at = (v: number) => Math.max(0, Math.min(100, (v / (domain || 1)) * 100));
  return <div className="relative">
    {children}
    {low !== undefined && high !== undefined && high > low && <div aria-hidden className="pointer-events-none absolute top-1 h-1.5 rounded-sm bg-chart-1/30" style={{ left: `${at(low)}%`, width: `${at(high) - at(low)}%` }} />}
  </div>;
}

/** Thin share meter, number beside it. */
export function Meter({ value, label, title }: { value?: number; label: ReactNode; title?: string }) {
  return <div className="flex items-center gap-3" title={title}>
    <div className="h-1 flex-1 overflow-hidden rounded-sm bg-muted">
      {value !== undefined && <div className="animate-grow-x h-full rounded-sm bg-foreground/60" style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%` }} />}
    </div>
    <span className="num shrink-0 text-xs text-foreground">{label}</span>
  </div>;
}

/** Interval width as ± share of the base, on a ±50% scale centered on zero. */
export function AccuracyMeter({ halfWidth, title }: { halfWidth?: number; title: string }) {
  const w = halfWidth === undefined ? 0 : Math.min(0.5, halfWidth);
  return <div className="flex items-center gap-3" title={title}>
    <div className="relative h-1 flex-1 rounded-sm bg-muted">
      {halfWidth !== undefined && <div className="absolute inset-y-0 rounded-sm bg-foreground/60" style={{ left: `${50 - w * 100}%`, width: `${w * 200}%` }} />}
      <div className="absolute -top-1 -bottom-1 left-1/2 w-px bg-muted-foreground" />
    </div>
    <span className="num shrink-0 text-xs text-foreground">{halfWidth === undefined ? "Not calibrated" : `±${Math.round(halfWidth * 100)}%`}</span>
  </div>;
}

/** Diverging bar around zero for one signed effect. */
export function SignedBar({ value, max }: { value?: number; max: number }) {
  if (value === undefined) return <div className="h-1 w-full rounded-sm border border-dashed border-border" />;
  const w = max ? Math.min(50, (Math.abs(value) / max) * 50) : 0;
  return <div className="relative h-1.5 w-full">
    <div className="absolute -top-0.5 -bottom-0.5 left-1/2 w-px bg-border-strong" />
    <div className="absolute inset-y-0 rounded-sm" style={{ background: EFFECT_FILL[directionOf(value)], ...(value >= 0 ? { left: "50%", width: `${w}%` } : { right: "50%", width: `${w}%` }) }} />
  </div>;
}

/** Columns for a short horizon; partial buckets are lighter. Exact values live in the title. */
/**
 * Short horizon as one compact row per period: label, bar scaled to the largest period, amount.
 * A partial period (the current week) is drawn lighter and labeled, so it never reads as a dip.
 */
export function ColumnStrip({ items, unit }: { items: Array<{ key: string; label: string; value?: number; partial?: boolean }>; unit: string }) {
  const max = Math.max(1, ...items.map(i => i.value ?? 0));
  return <ul className="space-y-1.5">
    {items.map((item, i) => <li key={item.key} className="grid grid-cols-[6.5rem_minmax(0,1fr)_4.5rem] items-center gap-3 text-xs" title={`${item.label}: ${exact(item.value, unit)}${item.partial ? " · partial week" : ""}`}>
      <span className="num truncate text-muted-foreground">{item.label}{item.partial && <span className="text-[10px]"> · so far</span>}</span>
      <span className="relative h-1.5 overflow-hidden rounded-sm bg-border">
        {item.value !== undefined && <span className={`animate-grow-x absolute inset-y-0 left-0 rounded-sm ${item.partial ? "bg-foreground/30" : "bg-foreground/70"}`} style={{ width: `${Math.max(1.5, (item.value / max) * 100)}%`, animationDelay: `${i * 60}ms` }} />}
      </span>
      <span className="num text-right text-foreground">{item.value === undefined ? "—" : amount(item.value, unit, true)}</span>
    </li>)}
  </ul>;
}

export function Swatch({ className, children }: { className: string; children: ReactNode }) {
  return <span className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground"><span className={`size-2 rounded-[2px] ${className}`} />{children}</span>;
}
