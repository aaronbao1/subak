import type { ContextItem, EffectMagnitude, EvidenceCategory, Unit } from "@/lib/contracts";
import { formatAmount } from "@/lib/format";
import { fmtDate } from "@/components/team/labels";
import { SOURCE_META, primarySource } from "@/components/context/source-brand";
import type { CategoryFilter, EffectFilter, ScopeFilter } from "./derive";

export const CATEGORY_LABEL: Record<EvidenceCategory, string> = {
  project: "Project",
  staffing: "Staffing",
  policy: "Policy",
  pricing: "Pricing",
  model: "Model",
  macro: "Macro",
};

export const SCOPE_FILTER_LABEL: Record<ScopeFilter, string> = { all: "All", company: "Company", team: "Team", person: "Person" };
export const EFFECT_FILTER_LABEL: Record<EffectFilter, string> = { all: "All", increase: "Increases", decrease: "Decreases" };
export const CATEGORY_FILTER_LABEL: Record<CategoryFilter, string> = { all: "All", ...CATEGORY_LABEL };

/** Real minus sign and an explicit plus, so a delta never reads as a plain amount. */
export function signedAmount(n: number, unit: Unit, opts: { compact?: boolean } = {}) {
  const abs = formatAmount(Math.abs(n), unit, opts);
  if (n === 0) return abs;
  return `${n > 0 ? "+" : "−"}${abs}`;
}

export function signedPct(n: number) {
  const abs = `${Math.abs(n).toFixed(Math.abs(n) % 1 === 0 ? 0 : 1)}%`;
  if (n === 0) return abs;
  return `${n > 0 ? "+" : "−"}${abs}`;
}

/**
 * The stated size of an effect as finance would write it: "−60% · 3 people at their last-week rate".
 * Returns undefined when nothing was stated, so the caller can show "size not stated" instead of silence.
 */
export function magnitudeText(m: EffectMagnitude | undefined, unit: Unit): string | undefined {
  if (!m) return undefined;
  const parts: string[] = [];
  if (typeof m.pct === "number") parts.push(signedPct(m.pct));
  if (typeof m.amount === "number") parts.push(signedAmount(m.amount, unit));
  if (m.basis) parts.push(m.basis);
  return parts.length ? parts.join(" · ") : undefined;
}

/** "Oct 27 – Dec 31", "Oct 27 onward", "until Dec 31", or undefined when undated. */
export function dateRangeText(item: Pick<ContextItem, "effectiveFrom" | "effectiveTo">): string | undefined {
  const from = item.effectiveFrom ? fmtDate(item.effectiveFrom) : undefined;
  const to = item.effectiveTo ? fmtDate(item.effectiveTo) : undefined;
  if (from && to) return `${from} – ${to}`;
  if (from) return `${from} onward`;
  if (to) return `until ${to}`;
  return undefined;
}

/**
 * Who said it. The contract's `attribution` wins; otherwise it is read off the lead source the way the reader
 * would recognise it: "Priya N. in #research" for a message, "Product Roadmap Update" for a document.
 */
export function attributionText(item: ContextItem): string | undefined {
  if (item.attribution) return item.attribution;
  const lead = item.sources[0];
  if (!lead) return undefined;
  const medium = SOURCE_META[primarySource(item)].medium;
  if (medium === "message" && lead.author) return lead.locator ? `${lead.author} in ${lead.locator}` : lead.author;
  if (lead.author) return `${lead.author}, ${lead.title}`;
  return lead.title;
}
