"use client";
import type { Budget, ClaimType, CostComponent, Forecast, Provenance, SpendingRecord, Team } from "@/lib/contracts";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

/* ------------------------------------------------------------------ */
/* Cost components                                                     */
/* ------------------------------------------------------------------ */

/** Fixed stacking order: fixed fees at the bottom, variable charges on top. */
export const COMPONENT_ORDER: CostComponent[] = ["subscription", "included_usage", "extra_usage", "api"];

export const COMPONENT_LABEL: Record<CostComponent, string> = {
  subscription: "Subscription",
  included_usage: "Included usage",
  extra_usage: "Extra usage",
  api: "API",
};

/** CSS variables set by TeamSpendChart's scoped style block (validated categorical slots 1-4). */
export const COMPONENT_COLOR_VAR: Record<CostComponent, string> = {
  subscription: "var(--comp-subscription)",
  included_usage: "var(--comp-included)",
  extra_usage: "var(--comp-extra)",
  api: "var(--comp-api)",
};

/* ------------------------------------------------------------------ */
/* Provenance                                                          */
/* ------------------------------------------------------------------ */

export const PROVENANCE_LABEL: Record<Provenance, string> = {
  reported_charge: "Reported charge",
  estimate: "Estimate",
  usage_only: "Usage only",
};

const PROVENANCE_TITLE: Record<Provenance, string> = {
  reported_charge: "Amount billed by the provider",
  estimate: "Estimated; not a bill",
  usage_only: "Usage recorded without a charge amount",
};

export function ProvenanceBadge({ provenance, className }: { provenance: Provenance; className?: string }) {
  return (
    <Badge
      variant="outline"
      title={PROVENANCE_TITLE[provenance]}
      className={cn(
        "text-[10px] font-normal",
        provenance === "reported_charge" && "border-foreground/30 text-foreground",
        provenance === "estimate" && "border-dashed text-muted-foreground",
        provenance === "usage_only" && "border-dotted text-muted-foreground",
        className,
      )}
    >
      {PROVENANCE_LABEL[provenance]}
    </Badge>
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

export function StatusChip({ status, className }: { status: TeamStatus; className?: string }) {
  return (
    <Badge variant="outline" className={cn("gap-1.5 font-normal", status === "no_projection" && "text-muted-foreground", className)}>
      <span
        aria-hidden
        className={cn(
          "size-1.5 rounded-full",
          status === "on_track" && "bg-emerald-600/80",
          status === "watch" && "bg-amber-500/90",
          status === "likely_over" && "bg-destructive/80",
          status === "no_projection" && "bg-muted-foreground/40",
        )}
      />
      {STATUS_LABEL[status]}
    </Badge>
  );
}

/* ------------------------------------------------------------------ */
/* Spend helpers                                                       */
/* ------------------------------------------------------------------ */

export function spentToDate(records: SpendingRecord[]) {
  return records.reduce((s, r) => s + r.amount, 0);
}

export function teamRecords(spending: SpendingRecord[], teamId: string) {
  return spending.filter((r) => r.teamId === teamId);
}

export function teamUnit(team: Team | undefined, budget: Budget | undefined, records: SpendingRecord[]) {
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

export function fmtDateTime(iso: string) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat("en-US", {
    month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit", timeZone: "UTC", timeZoneName: "short",
  }).format(d);
}
