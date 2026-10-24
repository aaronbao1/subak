import type { Forecast } from "@/lib/contracts";

/**
 * Restrained team status for the overview. "Likely over" only when the full-period projection
 * exceeds the allocation; "Watch" when it lands within 10% below it. Anything without an
 * available projection is "No projection" — never a guess.
 */
export type TeamStatus = "on_track" | "watch" | "likely_over" | "no_projection";

export const STATUS_META: Record<TeamStatus, { label: string; className: string }> = {
  on_track: { label: "On track", className: "bg-muted text-muted-foreground" },
  watch: { label: "Watch", className: "bg-amber-500/10 text-amber-700 dark:text-amber-400" },
  likely_over: { label: "Likely over", className: "bg-destructive/10 text-destructive" },
  no_projection: { label: "No projection", className: "border border-dashed border-border text-muted-foreground" },
};

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

export function teamStatus(allocated: number | undefined, projected: number | undefined): TeamStatus {
  if (typeof projected !== "number" || typeof allocated !== "number") return "no_projection";
  if (projected > allocated) return "likely_over";
  if (projected >= allocated * 0.9) return "watch";
  return "on_track";
}
