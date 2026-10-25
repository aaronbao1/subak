import type { Forecast } from "@/lib/contracts";

/**
 * Team status (on track / watch / likely over / no projection) lives in `@/components/team/labels`
 * (`teamStatus`, `StatusChip`) so the overview and /teams read the same rule and the same chip.
 * This module keeps only the projection arithmetic.
 */

/** Full-period projected total for a forecast. `remaining` basis is added to spent; `full_period` never is. */
export function projectedTotals(
  forecast: Forecast | undefined,
  spent: number,
): { projected?: number; low?: number; high?: number } {
  if (!forecast || forecast.status !== "available" || typeof forecast.projected !== "number") return {};
  const add = forecast.basis === "remaining" ? spent : 0;
  return {
    projected: forecast.projected + add,
    low: typeof forecast.low === "number" ? forecast.low + add : undefined,
    high: typeof forecast.high === "number" ? forecast.high + add : undefined,
  };
}
