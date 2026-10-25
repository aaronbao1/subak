import type { Unit } from "@/lib/contracts";

const compactFmt = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 });
const compactWhole = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 0 });
const standardFmt = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

/**
 * Explicit units, never mixed. Tokens are always compact ("85M", "12.4M") because exact token counts
 * are noise for finance; the word "tokens" is appended unless the caller asked for the compact form.
 */
export function formatAmount(n: number, unit: Unit, opts: { compact?: boolean } = {}) {
  if (unit === "tokens") {
    const v = Math.abs(n) >= 1_000 ? compactFmt.format(n) : standardFmt.format(n);
    return opts.compact ? v : `${v} tokens`;
  }
  const v = opts.compact ? compactWhole.format(n) : standardFmt.format(n);
  if (unit === "usd") return `$${v}`;
  return `${v} cr`;
}

/** Short unit name for table captions: "USD", "tokens", "credits". */
export function unitLabel(unit: Unit) {
  return unit === "usd" ? "USD" : unit;
}

/** Noun for a unit, for headings like "Daily tokens by team". */
export function unitNoun(unit: Unit) {
  return unit === "tokens" ? "tokens" : unit === "credits" ? "credits" : "spend";
}

export function pct(n: number, d: number) {
  if (!d) return 0;
  return (n / d) * 100;
}

export function formatPct(n: number) {
  return `${n >= 0 ? "" : "-"}${Math.abs(n).toFixed(0)}%`;
}
