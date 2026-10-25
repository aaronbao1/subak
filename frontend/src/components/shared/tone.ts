/**
 * One color rule for the direction of a change, used everywhere: evidence effects, deltas, signed bars, chips.
 * Increase = warning (amber), decrease = success (green), neutral/unknown = muted. Red (destructive) is reserved for
 * "over the allotment", never for a plain increase.
 */
export type EffectDirection = "increase" | "decrease" | "neutral" | "unknown";

export const EFFECT_TEXT: Record<EffectDirection, string> = {
  increase: "text-warning",
  decrease: "text-success",
  neutral: "text-muted-foreground",
  unknown: "text-muted-foreground",
};

export const EFFECT_FILL: Record<EffectDirection, string> = {
  increase: "var(--warning)",
  decrease: "var(--success)",
  neutral: "var(--muted-foreground)",
  unknown: "var(--muted-foreground)",
};

/** Direction of a signed number. */
export const directionOf = (n: number): EffectDirection => (n > 0 ? "increase" : n < 0 ? "decrease" : "neutral");
