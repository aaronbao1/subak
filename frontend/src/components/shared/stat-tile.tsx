"use client";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { useCountUp } from "@/components/shared/motion";

/**
 * One stat scale for the whole app. Label above (mono eyebrow), number in mono, caption below.
 *   hero      56px  — exactly one per view (the overview's total spend)
 *   primary   32px  — page-level tiles (team header, totals rows)
 *   secondary 24px  — section tiles (cost components, teams totals)
 *   compact   20px  — panels and drawers
 */
export type StatSize = "hero" | "primary" | "secondary" | "compact";
export type StatTone = "neutral" | "over" | "close" | "under";

const SIZE: Record<StatSize, string> = {
  hero: "text-5xl md:text-[56px]",
  primary: "text-[28px] md:text-[32px]",
  secondary: "text-2xl",
  compact: "text-xl",
};
const TONE: Record<StatTone, string> = {
  neutral: "text-muted-foreground",
  over: "text-destructive",
  close: "text-warning",
  under: "text-success",
};

export interface StatTileProps {
  label: ReactNode;
  value: ReactNode;
  size?: StatSize;
  /** Muted when the value is a placeholder like "No projection". */
  muted?: boolean;
  /** Small line under the number: a delta, a coverage note, a date. */
  caption?: ReactNode;
  /** Tone colors the caption's dot and text only, never the number. */
  tone?: StatTone;
  /** Badge or tag rendered beside the label. */
  aside?: ReactNode;
  /** Wrap in a bordered card; off when the tile sits inside a panel's grid. */
  card?: boolean;
  className?: string;
  /**
   * When `value` is a number, count it up on mount (900ms) and tick to each new value.
   * Pair with `format` to render the counted number; defaults to a rounded plain number.
   */
  animate?: boolean;
  /** Formats the counted number when `animate` is on, e.g. `(n) => formatAmount(n, unit)`. */
  format?: (n: number) => ReactNode;
}

export function StatTile({ label, value, size = "secondary", muted, caption, tone = "neutral", aside, card, className, animate, format }: StatTileProps) {
  const shown = animate && typeof value === "number" ? <CountingValue value={value} format={format} /> : typeof value === "number" && format ? format(value) : value;
  return (
    <div className={cn("min-w-0", card && "rounded-xl border border-border bg-card p-4", className)}>
      <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
        <span className="eyebrow truncate">{label}</span>
        {aside}
      </div>
      <div className={cn("num mt-2 truncate font-medium leading-none", muted ? "text-muted-foreground" : "text-foreground", muted && size === "hero" ? "text-2xl" : SIZE[size])}>
        {shown}
      </div>
      {caption && (
        <div className={cn("mt-1.5 flex min-w-0 items-center gap-1.5 text-[11px] leading-tight md:text-xs", TONE[tone])}>
          {tone !== "neutral" && <span className="size-1 shrink-0 rounded-full bg-current" aria-hidden />}
          <span className="min-w-0">{caption}</span>
        </div>
      )}
    </div>
  );
}

/**
 * Counts to `value`; the final figure is laid out invisibly underneath so the tile's width never shifts while digits grow.
 */
function CountingValue({ value, format = (n) => String(Math.round(n)) }: { value: number; format?: (n: number) => ReactNode }) {
  const n = useCountUp(value);
  return (
    <span className="relative inline-block">
      <span className="invisible" aria-hidden>{format(value)}</span>
      <span className="absolute inset-0">{format(n)}</span>
    </span>
  );
}

/** Page heading: h2 step (28px, weight 500) with an optional one-line description. */
export function PageTitle({ title, description, actions, className }: { title: ReactNode; description?: ReactNode; actions?: ReactNode; className?: string }) {
  return (
    <div className={cn("flex flex-wrap items-start justify-between gap-x-6 gap-y-3", className)}>
      <div className="min-w-0 max-w-[640px]">
        <h1 className="text-[24px] leading-[1.15] font-medium md:text-[28px]">{title}</h1>
        {description && <p className="mt-1.5 text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}
