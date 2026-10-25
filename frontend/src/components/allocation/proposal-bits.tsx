"use client";
import type { AllocationLine, AllocationProposal, Decision, Team, Unit } from "@/lib/contracts";
import { Badge } from "@/components/ui/badge";
import { formatAmount } from "@/lib/format";
import { cn } from "@/lib/utils";
import { PlaceholderBadge } from "@/components/team/labels";

/* Shared pieces for proposals and receipts: kind label, status badge, total-allocation line, per-team lines. */

export function kindLabel(p: Pick<AllocationProposal, "kind" | "addedAmount" | "unit">) {
  return p.kind === "add_budget"
    ? `Adds ${formatAmount(p.addedAmount ?? 0, p.unit)} to the total allocation`
    : "Redistributes the existing allocation";
}

export function kindShort(kind: AllocationProposal["kind"]) {
  return kind === "add_budget" ? "Add budget" : "Redistribute";
}

export function kindExplanation(kind: AllocationProposal["kind"]) {
  return kind === "redistribute"
    ? "Total allocation stays the same; money moves between teams."
    : "New funding; no team loses allocation.";
}

export const STATUS_LABEL: Record<AllocationProposal["status"], string> = {
  proposed: "Awaiting review",
  pending: "Applying…",
  applied: "Applied",
  rejected: "Rejected",
  revised: "Revised",
  stale: "Stale",
  failed: "Failed",
};

/** Every state looks different: neutral for open, success / warning / destructive for applied / stale / failed, muted for closed. */
const STATUS_VARIANT: Record<AllocationProposal["status"], "default" | "outline" | "success" | "warning" | "destructive"> = {
  proposed: "default",
  pending: "default",
  applied: "success",
  rejected: "outline",
  revised: "outline",
  stale: "warning",
  failed: "destructive",
};

export function ProposalStatusBadge({ status, className }: { status: AllocationProposal["status"]; className?: string }) {
  return (
    <Badge
      variant={STATUS_VARIANT[status]}
      className={cn(
        "gap-1.5",
        status === "pending" && "border-dashed text-muted-foreground",
        status === "rejected" && "text-muted-foreground",
        status === "revised" && "border-dashed text-muted-foreground line-through decoration-muted-foreground",
        className,
      )}
    >
      {status === "pending" && <span aria-hidden className="size-1.5 animate-pulse rounded-full bg-current" />}
      {(status === "applied" || status === "stale" || status === "failed") && <span aria-hidden className="size-1.5 rounded-full bg-current" />}
      {STATUS_LABEL[status]}
    </Badge>
  );
}

/** "Add budget" / "Redistribute". The distinction is a product rule, so it is always present. */
export function KindBadge({ kind, className }: { kind: AllocationProposal["kind"]; className?: string }) {
  return (
    <Badge variant="default" className={className} title={kindExplanation(kind)}>
      {kindShort(kind)}
    </Badge>
  );
}

/** Tag for placeholder projections. Always visible where such a projection is cited. */
export function PlaceholderTag({ className }: { className?: string }) {
  return <PlaceholderBadge className={className} />;
}

export function signed(n: number, unit: Unit, opts: { compact?: boolean } = {}) {
  if (n === 0) return "no change";
  return `${n > 0 ? "+" : "−"}${formatAmount(Math.abs(n), unit, opts)}`;
}

/** Deltas use the status pair only: up is --success, down is --destructive, unchanged is muted. */
export function deltaClass(n: number) {
  return n > 0 ? "text-success" : n < 0 ? "text-destructive" : "text-muted-foreground";
}

/** Signed, colored delta in mono. */
export function Delta({ n, unit, className, compact }: { n: number; unit: Unit; className?: string; compact?: boolean }) {
  return <span className={cn("num", deltaClass(n), className)}>{signed(n, unit, { compact })}</span>;
}

export function teamName(teams: Team[], id: string) {
  return teams.find((t) => t.id === id)?.name ?? id;
}

export function teamColor(teams: Team[], id: string) {
  return teams.find((t) => t.id === id)?.color ?? "var(--muted-foreground)";
}

/** Total allocation before → after. For a redistribution the two numbers are equal and that is the point. */
export function EnvelopeLine({ before, after, unit, kind, className }: { before: number; after: number; unit: Unit; kind: AllocationProposal["kind"]; className?: string }) {
  return (
    <div className={cn("flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5", className)}>
      <span className="eyebrow">Total allocation</span>
      <span className="num flex items-baseline gap-1.5 text-sm">
        <span className="text-muted-foreground">{formatAmount(before, unit)}</span>
        <span aria-hidden className="text-muted-foreground">→</span>
        <span className="font-medium">{formatAmount(after, unit)}</span>
        {kind === "redistribute" ? (
          <span className="font-sans text-xs text-muted-foreground">unchanged</span>
        ) : (
          <Delta n={after - before} unit={unit} className="text-xs" />
        )}
      </span>
    </div>
  );
}

/**
 * Per-team before / after / delta rows. Teams with no change are muted so the eye lands on what moves.
 * Numbers use the compact form; the unit is stated once on the total-allocation line above.
 */
export function AllocationLines({ lines, unit, teams, className }: { lines: AllocationLine[]; unit: Unit; teams: Team[]; className?: string }) {
  const compact = { compact: true };
  return (
    <ul className={cn("divide-y divide-border text-sm", className)}>
      {lines.map((l) => {
        const d = l.after - l.before;
        return (
          <li key={l.teamId} className={cn("flex h-10 items-center justify-between gap-3", d === 0 && "text-muted-foreground")}>
            <span className="flex min-w-0 items-center gap-2">
              <span aria-hidden className="size-1.5 shrink-0 rounded-full" style={{ background: teamColor(teams, l.teamId) }} />
              <span className="truncate">{teamName(teams, l.teamId)}</span>
            </span>
            <span className="num flex shrink-0 items-baseline gap-1.5 text-right">
              <span className="text-muted-foreground">{formatAmount(l.before, unit, compact)}</span>
              <span aria-hidden className="text-muted-foreground">→</span>
              <span className={cn(d !== 0 && "font-medium")}>{formatAmount(l.after, unit, compact)}</span>
              <Delta n={d} unit={unit} compact className="inline-block min-w-[4rem] text-right text-xs" />
            </span>
          </li>
        );
      })}
    </ul>
  );
}

export function decisionTotals(d: Decision) {
  const before = d.lines.reduce((s, l) => s + l.before, 0);
  const after = d.lines.reduce((s, l) => s + l.after, 0);
  return { before, after };
}
