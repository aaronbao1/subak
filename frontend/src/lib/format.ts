import type { Unit } from "@/lib/contracts";

export function formatAmount(n: number, unit: Unit, opts: { compact?: boolean } = {}) {
  const nf = new Intl.NumberFormat("en-US", {
    notation: opts.compact ? "compact" : "standard",
    maximumFractionDigits: unit === "usd" ? 0 : 0,
  });
  if (unit === "usd") return `$${nf.format(n)}`;
  if (unit === "tokens") return `${nf.format(n)} tok`;
  return `${nf.format(n)} cr`;
}

export function pct(n: number, d: number) {
  if (!d) return 0;
  return (n / d) * 100;
}

export function formatPct(n: number) {
  return `${n >= 0 ? "" : "-"}${Math.abs(n).toFixed(0)}%`;
}
