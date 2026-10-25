"use client";
import { ArrowUpRight } from "lucide-react";
import type { AllocationProposal, Team } from "@/lib/contracts";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { AllocationTable, KindLabel, PairedBars, ProposalStatusBadge, Reveal, TotalBar } from "./proposal-bits";

/** Compact proposal inside an assistant message. Finance opens the full review from here. */
export function ProposalCard({ proposal, teams, onReview, className }: { proposal: AllocationProposal; teams: Team[]; onReview: (id: string) => void; className?: string }) {
  const open = proposal.status === "proposed";

  return (
    <div
      className={cn(
        "space-y-4 rounded-xl border border-border bg-card p-4 transition-opacity duration-300",
        proposal.status === "revised" && "opacity-70",
        className,
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <KindLabel kind={proposal.kind} />
        <ProposalStatusBadge status={proposal.status} />
      </div>

      <TotalBar before={proposal.totalBefore} after={proposal.totalAfter} unit={proposal.unit} kind={proposal.kind} />
      <PairedBars lines={proposal.lines} unit={proposal.unit} teams={teams} kind={proposal.kind} limit={6} />

      {proposal.status === "failed" && proposal.failureReason && (
        <p className="text-xs leading-snug text-destructive">{proposal.failureReason}</p>
      )}

      <Reveal
        show="Show table"
        hide="Hide table"
        aside={
          <Button size="sm" variant={open ? "default" : "ghost"} onClick={() => onReview(proposal.id)} className="shrink-0">
            {open ? "Review" : "Details"} <ArrowUpRight data-icon="inline-end" className={cn(!open && "text-muted-foreground")} strokeWidth={1.5} />
          </Button>
        }
      >
        <AllocationTable lines={proposal.lines} unit={proposal.unit} teams={teams} kind={proposal.kind} />
      </Reveal>
    </div>
  );
}
