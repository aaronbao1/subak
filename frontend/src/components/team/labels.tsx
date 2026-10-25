"use client";
import type { ReactNode } from "react";
import type { Budget, ClaimType, ContextKind, CostComponent, Forecast, Provenance, SpendingRecord } from "@/lib/contracts";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { billableAmount, sumMoney } from "@/lib/finance-summary";

/** One color per cost component, shared with the overview tiles. */
export { COMPONENT_COLOR } from "@/components/shared/components";

/* ------------------------------------------------------------------ */
/* Cost components                                                     */
/* ------------------------------------------------------------------ */

/** Fixed stacking order: fixed fees at the bottom, variable charges on top. */
export const COMPONENT_ORDER: CostComponent[] = ["subscription", "included_usage", "extra_usage", "api", "unpriced_usage"];

export const COMPONENT_LABEL: Record<CostComponent, string> = {
  subscription: "Subscription",
  included_usage: "Included usage",
  extra_usage: "Extra usage",
  api: "API",
  unpriced_usage: "Unpriced usage",
};

/* ------------------------------------------------------------------ */
/* Provenance                                                          */
/* ------------------------------------------------------------------ */

export const PROVENANCE_LABEL: Record<Provenance, string> = {
  reported_charge: "Reported charge",
  estimate: "Estimate",
  usage_only: "Usage only",
  measured: "Measured usage",
  simulated: "Usage value",
};

const PROVENANCE_TITLE: Record<Provenance, string> = {
  reported_charge: "Amount billed by the provider",
  estimate: "Estimated; not a bill",
  usage_only: "Usage recorded without a charge amount",
  measured: "Observed usage valued using the supplied pricing",
  simulated: "Usage value from the loaded dataset",
};

/** Small inline chip next to an amount. Border style carries the provenance so it survives without color. */
export function ProvenanceBadge({ provenance, className }: { provenance: Provenance; className?: string }) {
  return (
    <span
      title={PROVENANCE_TITLE[provenance]}
      className={cn(
        "inline-flex h-5 shrink-0 items-center rounded-sm border px-1.5 text-[11px] leading-none whitespace-nowrap",
        provenance === "reported_charge" && "border-border-strong text-foreground/80",
        (provenance === "estimate" || provenance === "simulated") && "border-dashed border-border-strong text-muted-foreground",
        provenance === "measured" && "border-border-strong text-muted-foreground",
        provenance === "usage_only" && "border-dotted border-border-strong text-muted-foreground",
        className,
      )}
    >
      {PROVENANCE_LABEL[provenance]}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* Context labels                                                      */
/* ------------------------------------------------------------------ */

export const CLAIM_LABEL: Record<ClaimType, string> = {
  stated_plan: "Stated plan",
  observed_event: "Observed event",
  interpretation: "Interpretation",
};

export const EFFECT_LABEL = {
  increase: "Expected to increase spend",
  decrease: "Expected to decrease spend",
  neutral: "Neutral effect",
  unknown: "Effect unknown",
} as const;

export const CONFIDENCE_LABEL = {
  high: "High confidence",
  medium: "Medium confidence",
  low: "Low confidence",
} as const;

/** Kind of a context item or the company document behind it. */
export const KIND_LABEL: Record<ContextKind, string> = {
  plan: "Plan",
  project_doc: "Project document",
  research_note: "Research note",
  correspondence: "Correspondence",
};

/* ------------------------------------------------------------------ */
/* Tags                                                                */
/* ------------------------------------------------------------------ */

/** Neutral spec badge for qualifiers such as "scenario" or "remaining basis". */
export function Tag({ children, title, className }: { children: ReactNode; title?: string; className?: string }) {
  return (
    <Badge variant="outline" title={title} className={cn("text-muted-foreground", className)}>
      {children}
    </Badge>
  );
}

/* ------------------------------------------------------------------ */
/* Team status                                                         */
/* ------------------------------------------------------------------ */

export type TeamStatus = "on_track" | "watch" | "likely_over" | "no_projection";

export const STATUS_LABEL: Record<TeamStatus, string> = {
  on_track: "On track",
  watch: "Watch",
  likely_over: "Likely over",
  no_projection: "No projection",
};

const STATUS_VARIANT = {
  on_track: "success",
  watch: "warning",
  likely_over: "destructive",
  no_projection: "outline",
} as const;

/**
 * Likely over only when the projected full-period total exceeds the allocation.
 * Watch when the projection is within 10% under the allocation or the high end of the range exceeds it.
 */
export function teamStatus(budget: Budget | undefined, forecast: Forecast | undefined, spent: number): TeamStatus {
  if (!forecast || forecast.status !== "available" || forecast.projected == null) return "no_projection";
  if (!budget) return "no_projection";
  const total = forecast.basis === "remaining" ? spent + forecast.projected : forecast.projected;
  if (total > budget.allocated) return "likely_over";
  const high = forecast.basis === "remaining" ? spent + (forecast.high ?? forecast.projected) : (forecast.high ?? forecast.projected);
  if (total >= budget.allocated * 0.9 || high > budget.allocated) return "watch";
  return "on_track";
}

/** Spec status badge: 1px tinted border and text in --success / --warning / --destructive, never a filled background. */
export function StatusChip({ status, className }: { status: TeamStatus; className?: string }) {
  return (
    <Badge variant={STATUS_VARIANT[status]} className={cn("gap-1.5", status === "no_projection" && "text-muted-foreground", className)}>
      <span aria-hidden className={cn("size-1.5 rounded-full bg-current", status === "no_projection" && "bg-muted-foreground")} />
      {STATUS_LABEL[status]}
    </Badge>
  );
}

/* ------------------------------------------------------------------ */
/* Spend helpers                                                       */
/* ------------------------------------------------------------------ */

export function spentToDate(records: SpendingRecord[]) {
  return sumMoney(records.map(billableAmount));
}

export function teamRecords(spending: SpendingRecord[], teamId: string) {
  return spending.filter((r) => r.teamId === teamId);
}

export function teamUnit(budget: Budget | undefined, records: SpendingRecord[]) {
  return budget?.unit ?? records[0]?.unit ?? "usd";
}

/* ------------------------------------------------------------------ */
/* Dates                                                               */
/* ------------------------------------------------------------------ */

/** Date-only ISO strings are rendered in UTC so they never shift a day. */
export function fmtDate(iso: string | undefined, opts: { year?: boolean } = {}) {
  if (!iso) return "";
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00Z` : iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat("en-US", {
    month: "short", day: "numeric", ...(opts.year ? { year: "numeric" } : {}), timeZone: "UTC",
  }).format(d);
}

/** Timestamps render in the reader's local time with a short zone name; a date-only string stays a UTC date. */
export function fmtDateTime(iso: string) {
  if (!iso) return "";
  if (iso.length === 10) return fmtDate(iso, { year: true });
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat("en-US", {
    month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit", timeZoneName: "short",
  }).format(d);
}
