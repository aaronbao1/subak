"use client";
import type { CSSProperties, ReactNode } from "react";
import { cn } from "@/lib/utils";
import { EFFECT_TEXT } from "@/components/shared/tone";
import { riseAt } from "./count-up";

/* Small inline marks for the Teams and People views. Shape at rest; the exact value lives beside or in a title. */

const pctOf = (n: number, d: number) => (d > 0 ? Math.max(0, Math.min(100, (n / d) * 100)) : 0);

/**
 * Bullet bar: track = allocation, fill = spent, tick = projected full-period total.
 * Projected spend past today shows as a faint extension; only the part beyond the allocation wears --destructive.
 * Without an allocation there is no track: a dashed outline marks the missing limit.
 */
export function BulletBar({
  allocation, spent, projected, color = "var(--foreground)", size = "sm", grow, delay = 0, title, className,
}: {
  allocation?: number;
  spent: number;
  projected?: number;
  /** Fill color, usually the team's identity color. */
  color?: string;
  size?: "sm" | "md";
  /** Run the one-time grow-from-left entrance. */
  grow?: boolean;
  delay?: number;
  title?: string;
  className?: string;
}) {
  const domain = Math.max(allocation ?? 0, projected ?? 0, spent) || 1;
  const track = allocation != null ? pctOf(allocation, domain) : 100;
  const fill = pctOf(Math.min(spent, allocation ?? spent), domain);
  const spentOver = allocation != null && spent > allocation ? pctOf(spent - allocation, domain) : 0;
  const projEnd = projected != null ? pctOf(projected, domain) : undefined;
  const spentEnd = pctOf(spent, domain);
  const projUnder = projEnd != null && allocation != null ? Math.max(0, Math.min(projEnd, track) - spentEnd) : projEnd != null ? Math.max(0, projEnd - spentEnd) : 0;
  const projOverStart = Math.max(spentEnd, track);
  const projOver = projEnd != null && allocation != null && projEnd > projOverStart ? projEnd - projOverStart : 0;
  const h = size === "md" ? "h-2.5" : "h-1.5";
  const growStyle: CSSProperties = grow ? riseAt(delay) : {};
  const growClass = grow ? "animate-grow-x" : "";

  return (
    <div className={cn("relative w-full", size === "md" ? "py-1.5" : "py-1", className)} title={title} role={title ? "img" : undefined} aria-label={title}>
      <div className={cn("relative w-full", h)}>
        {/* Allocation track (or a dashed outline when there is none) */}
        <div
          className={cn("absolute inset-y-0 left-0 rounded-sm", allocation != null ? "bg-border" : "border border-dashed border-border-strong")}
          style={{ width: `${track}%` }}
        />
        <div className={cn("absolute inset-0", growClass)} style={growStyle}>
          {/* Spent, within the allocation */}
          <div className="absolute inset-y-0 left-0 rounded-l-sm" style={{ width: `${fill}%`, background: color }} />
          {/* Spent beyond the allocation */}
          {spentOver > 0 && <div className="absolute inset-y-0 bg-destructive" style={{ left: `${track}%`, width: `${spentOver}%` }} />}
          {/* Still expected, inside the allocation */}
          {projUnder > 0 && <div className="absolute inset-y-0 opacity-30" style={{ left: `${spentEnd}%`, width: `${projUnder}%`, background: color }} />}
          {/* Expected overrun */}
          {projOver > 0 && <div className="absolute inset-y-0 bg-destructive/40" style={{ left: `${projOverStart}%`, width: `${projOver}%` }} />}
        </div>
        {/* Projection tick */}
        {projEnd != null && (
          <div
            aria-hidden
            className={cn("absolute w-0.5 -translate-x-1/2 rounded-sm bg-foreground", size === "md" ? "-inset-y-1.5" : "-inset-y-1")}
            style={{ left: `${Math.min(99.5, Math.max(0.5, projEnd))}%` }}
          />
        )}
      </div>
    </div>
  );
}

/**
 * Legend swatches for a bullet bar; each value is the exact figure the mark encodes.
 * `note` is a small visible qualifier after the value (e.g. provenance), dotted-underlined when `title` explains it.
 */
export function BulletLegend({ items, size = "sm", className }: { items: { label: string; value: ReactNode; mark: "fill" | "track" | "tick"; color?: string; title?: string; muted?: boolean; note?: ReactNode }[]; size?: "sm" | "lg"; className?: string }) {
  return (
    <ul className={cn("flex flex-wrap items-baseline gap-x-5 gap-y-1.5 text-xs text-muted-foreground", className)}>
      {items.map((it) => (
        <li key={it.label} className="inline-flex items-baseline gap-2" title={it.title}>
          <span
            aria-hidden
            className={cn(
              "inline-block shrink-0 self-center",
              it.mark === "fill" && "size-2 rounded-[2px]",
              it.mark === "track" && "size-2 rounded-[2px] bg-border",
              it.mark === "tick" && "h-3 w-0.5 rounded-sm bg-foreground",
            )}
            style={it.mark === "fill" ? { background: it.color ?? "var(--foreground)" } : undefined}
          />
          <span>{it.label}</span>
          <span className={cn("num", size === "lg" ? "text-xl" : "text-sm", it.muted ? "text-muted-foreground" : "text-foreground")}>{it.value}</span>
          {it.note != null && (
            <span className={cn("text-[11px] text-muted-foreground", it.title && "cursor-help underline decoration-dotted decoration-muted-foreground/60 underline-offset-2")}>{it.note}</span>
          )}
        </li>
      ))}
    </ul>
  );
}

/** 24px trend line. The last point is the newest; a final partial day is drawn dashed. */
export function Sparkline({ values, partialLast, color = "currentColor", className, title }: { values: number[]; partialLast?: boolean; color?: string; className?: string; title?: string }) {
  if (values.length < 2) return <span className={cn("inline-block h-6 w-16 text-xs text-muted-foreground", className)} title={title}>—</span>;
  const W = 64, H = 24, P = 2;
  const max = Math.max(...values), min = Math.min(0, ...values);
  const x = (i: number) => (i / (values.length - 1)) * W;
  const y = (v: number) => H - P - ((v - min) / (max - min || 1)) * (H - P * 2);
  const pts = values.map((v, i) => `${x(i).toFixed(2)},${y(v).toFixed(2)}`);
  const solid = partialLast ? pts.slice(0, -1) : pts;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className={cn("h-6 w-16 shrink-0 overflow-visible", className)} role={title ? "img" : undefined} aria-label={title} aria-hidden={title ? undefined : true}>
      {title && <title>{title}</title>}
      <polyline points={solid.join(" ")} fill="none" stroke={color} strokeWidth={1.5} strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
      {partialLast && (
        <polyline points={pts.slice(-2).join(" ")} fill="none" stroke={color} strokeWidth={1.5} strokeDasharray="2 2" strokeLinecap="round" opacity={0.6} vectorEffect="non-scaling-stroke" />
      )}
    </svg>
  );
}

/** Thin 4px meter for a share (0..1) with the number beside it. Missing shows a dash, never an empty bar. */
export function ShareMeter({ share, color = "var(--foreground)", label, className, grow, delay = 0 }: { share?: number; color?: string; label?: string; className?: string; grow?: boolean; delay?: number }) {
  if (share == null) return <span className={cn("text-muted-foreground", className)} title="No comparable team projection">—</span>;
  const w = Math.max(0, Math.min(100, share * 100));
  return (
    <span className={cn("inline-flex items-center justify-end gap-2", className)}>
      <span aria-hidden className="h-1 w-14 shrink-0 overflow-hidden rounded-sm bg-border">
        <span className={cn("block h-full rounded-sm", grow ? "animate-grow-x" : "")} style={{ width: `${w}%`, background: color, opacity: 0.8, ...(grow ? riseAt(delay) : {}) }} />
      </span>
      <span className="num w-9 text-right text-foreground">{label ?? `${Math.round(w)}%`}</span>
    </span>
  );
}

/** Change between two values as ▲/▼ and a percent. Past ±15%, a rise reads in --warning and a fall in --success (shared/tone). */
export function DeltaChip({ value, className, title = "Average daily spend, this week vs last week" }: { value?: number; className?: string; title?: string }) {
  if (value === undefined || !Number.isFinite(value)) return <span className={cn("text-muted-foreground", className)} title="Not enough complete days to compare">—</span>;
  const pct = Math.round(value * 100);
  const arrow = pct > 0 ? "▲" : pct < 0 ? "▼" : "";
  return (
    <span
      title={title}
      className={cn(
        "num inline-flex items-center gap-1 whitespace-nowrap",
        value > 0.15 ? EFFECT_TEXT.increase : value < -0.15 ? EFFECT_TEXT.decrease : "text-foreground/80",
        className,
      )}
    >
      {arrow && <span aria-hidden className="text-[9px] leading-none">{arrow}</span>}
      <span>{pct === 0 ? "0%" : `${Math.abs(pct)}%`}</span>
      <span className="sr-only">{pct > 0 ? "up" : pct < 0 ? "down" : "flat"}</span>
    </span>
  );
}

/** Daily totals for the last `days` dates that have records, oldest first; `partialLast` when the newest is incomplete. */
export function dailySeries(records: { date: string; amount: number; complete: boolean }[], days = 14) {
  const by = new Map<string, { total: number; complete: boolean }>();
  for (const r of records) {
    const d = by.get(r.date) ?? { total: 0, complete: true };
    d.total += r.amount;
    if (!r.complete) d.complete = false;
    by.set(r.date, d);
  }
  const dates = [...by.keys()].sort().slice(-days);
  return { values: dates.map((d) => by.get(d)!.total), partialLast: dates.length > 0 && !by.get(dates[dates.length - 1])!.complete, from: dates[0], to: dates[dates.length - 1] };
}
