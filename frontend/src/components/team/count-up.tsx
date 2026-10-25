"use client";
import type { Unit } from "@/lib/contracts";
import { formatAmount, formatPct } from "@/lib/format";
import { riseDelay, useCountUp } from "@/components/shared/motion";

/**
 * Stat values that count up on load (900ms, ease-out cubic) and re-tick when the value changes.
 * Each is a leaf so the per-frame re-render stays inside the number, not the page. Pass the result as
 * a StatTile `value`; formatting goes through `formatAmount` / `formatPct` so units stay explicit.
 */
export function CountUpAmount({ value, unit, delay, compact }: { value: number; unit: Unit; delay?: number; compact?: boolean }) {
  const v = useCountUp(value, { delay });
  return <>{formatAmount(v, unit, { compact })}</>;
}

export function CountUpPct({ value, delay }: { value: number; delay?: number }) {
  const v = useCountUp(value, { delay });
  return <>{formatPct(v)}</>;
}

/** `riseDelay` in milliseconds rather than sequence steps, for rows that follow a section's own delay. */
export const riseAt = (ms: number) => riseDelay(ms, 1);

/**
 * Per-row stagger that spreads evenly so a long table never pushes the last row past the budget:
 * 30ms a row up to `cap` ms of total stagger (16 rows → 20ms a row).
 */
export const rowStep = (count: number, cap = 300, step = 30) => Math.min(step, cap / Math.max(1, count - 1));
