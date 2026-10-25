"use client";
import type { CSSProperties, ReactNode } from "react";
import { riseDelay, useCountUp } from "@/components/shared/motion";
import { cn } from "@/lib/utils";

/** A number that counts up on mount and ticks to each new value, with the final width reserved so rows never shift. */
export function CountUp({ value, format }: { value: number; format: (n: number) => string }) {
  const n = useCountUp(value);
  return (
    <span className="relative inline-block">
      <span className="invisible" aria-hidden>{format(value)}</span>
      <span className="absolute inset-0 text-right">{format(n)}</span>
    </span>
  );
}

export interface StackSegment {
  key: string;
  value: number;
  color: string;
  /** Drawn as a dashed outline (informational, not billed). */
  dashed?: boolean;
  title?: string;
}

/** One thin stacked bar of shares, 2px surface gap between segments, growing from the left. */
export function StackedBar({ segments, className }: { segments: StackSegment[]; className?: string }) {
  const total = segments.reduce((s, x) => s + Math.max(0, x.value), 0);
  if (total <= 0) return <div className={cn("h-1.5 w-full rounded-sm bg-muted", className)} aria-hidden />;
  return (
    <div className={cn("flex h-1.5 w-full gap-0.5 overflow-hidden rounded-sm", className)} aria-hidden>
      {segments.filter((x) => x.value > 0).map((x, i) => (
        <div
          key={x.key} title={x.title}
          className={cn("animate-grow-x h-full rounded-[1px]", x.dashed && "border border-dashed")}
          style={{ ...riseDelay(i), width: `${(x.value / total) * 100}%`, ...(x.dashed ? { borderColor: x.color } : { background: x.color }) }}
        />
      ))}
    </div>
  );
}

/** label · bar · value. The bar is scaled to `max`; the value column is right-aligned mono. */
export function BarRow({
  label, value, max, color, dashed, valueNode, trailing, title, index = 0, muted, className,
}: {
  label: ReactNode;
  value: number;
  max: number;
  color: string;
  dashed?: boolean;
  valueNode: ReactNode;
  trailing?: ReactNode;
  title?: string;
  index?: number;
  muted?: boolean;
  className?: string;
}) {
  const width = max > 0 ? Math.max(value > 0 ? 1.5 : 0, (value / max) * 100) : 0;
  const fill: CSSProperties = dashed ? { borderColor: color } : { background: color };
  return (
    <li className={cn("grid grid-cols-[minmax(0,10rem)_minmax(0,1fr)_auto] items-center gap-3 py-1.5 text-xs", className)} title={title}>
      <span className={cn("flex min-w-0 items-center gap-2 truncate", muted ? "text-muted-foreground" : "text-foreground/80")}>{label}</span>
      <span className="h-1.5 w-full overflow-hidden rounded-sm bg-muted" aria-hidden>
        <span className={cn("animate-grow-x block h-full rounded-[1px]", dashed && "border border-dashed")} style={{ ...riseDelay(index), width: `${width}%`, ...fill }} />
      </span>
      <span className="flex items-baseline justify-end gap-2">
        <span className={cn("num min-w-14 text-right", muted ? "text-muted-foreground" : "text-foreground")}>{valueNode}</span>
        {trailing}
      </span>
    </li>
  );
}
