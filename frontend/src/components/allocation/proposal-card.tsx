"use client";
import { ArrowUpRight } from "lucide-react";
import type { AllocationProposal, Team } from "@/lib/contracts";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { AllocationLines, EnvelopeLine, KindBadge, kindExplanation, kindLabel, ProposalStatusBadge } from "./proposal-bits";

/** Compact proposal inside an assistant message. Finance opens the full review from here. */
export function ProposalCard({ proposal, teams, onReview, className }: { proposal: AllocationProposal; teams: Team[]; onReview: (id: string) => void; className?: string }) {
  const open = proposal.status === "proposed";
  const footnote =
    proposal.status === "failed" && proposal.failureReason ? proposal.failureReason
    : proposal.status === "applied" ? "Applied. The receipt is in Decisions."
    : proposal.status === "rejected" ? "Rejected. Allocations unchanged."
    : proposal.status === "revised" ? "Superseded by a newer proposal."
    : proposal.status === "stale" ? "Budgets changed since this was prepared."
    : "Nothing is saved until you apply it.";

  return (
    <div
      className={cn(
        "rounded-xl border border-border bg-card transition-opacity duration-300",
        proposal.status === "revised" && "opacity-70",
        className,
      )}
    >
      <div className="flex items-start justify-between gap-3 p-4">
        <div className="min-w-0 space-y-1.5">
          <div className="flex flex-wrap items-center gap-1.5">
            <KindBadge kind={proposal.kind} />
            <ProposalStatusBadge status={proposal.status} />
          </div>
          <div className="text-sm leading-snug font-medium">{kindLabel(proposal)}</div>
          <div className="text-xs leading-snug text-muted-foreground">{kindExplanation(proposal.kind)}</div>
        </div>
      </div>

      <div className="border-t border-border px-4 py-3">
        <EnvelopeLine before={proposal.totalBefore} after={proposal.totalAfter} unit={proposal.unit} kind={proposal.kind} />
      </div>
      <AllocationLines lines={proposal.lines} unit={proposal.unit} teams={teams} kind={proposal.kind} className="border-t border-border px-4" />

      <div className="flex items-center justify-between gap-3 border-t border-border px-4 py-3">
        <span className={cn("min-w-0 text-xs leading-snug text-muted-foreground", proposal.status === "failed" && "text-destructive")}>{footnote}</span>
        <Button size="sm" variant={open ? "default" : "ghost"} onClick={() => onReview(proposal.id)} className="shrink-0">
          {open ? "Review" : "Details"} <ArrowUpRight data-icon="inline-end" className={cn(!open && "text-muted-foreground")} strokeWidth={1.5} />
        </Button>
      </div>
    </div>
  );
}
