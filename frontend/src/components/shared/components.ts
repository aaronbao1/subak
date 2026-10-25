import type { CostComponent } from "@/lib/contracts";

/** One color per cost component, used identically in the team stacked bars and the overview tiles. */
export const COMPONENT_COLOR: Record<CostComponent, string> = {
  subscription: "var(--chart-1)",
  extra_usage: "var(--chart-2)",
  api: "var(--chart-5)",
  /** Informational, not billed: neutral and drawn dashed wherever it appears. */
  included_usage: "var(--chart-other)",
};

/** Saturday or Sunday, read from the ISO date so the local timezone cannot shift it. */
export function isWeekend(date: string): boolean {
  const d = new Date(`${date}T00:00:00Z`).getUTCDay();
  return d === 0 || d === 6;
}

/** Shared SVG hatch for weekend columns; render once inside a chart's <defs>. */
export const WEEKEND_PATTERN_ID = "weekend-hatch";
