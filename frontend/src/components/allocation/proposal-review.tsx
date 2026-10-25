"use client";
import { useState } from "react";
import { AlertTriangle, Ban, Check, ChevronRight, History, X } from "lucide-react";
import type { Decision } from "@/lib/contracts";
import { useAppStore } from "@/lib/store";
import { formatAmount } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { fmtDate, fmtDateTime } from "@/components/team/labels";
import { AllocationTable, KindLabel, kindLabel, PairedBars, ProposalStatusBadge, Reveal, TotalBar } from "./proposal-bits";

interface Props {
  proposalId?: string;
  onClose: () => void;
}

type Phase =
  | { kind: "idle" }
  | { kind: "pending"; action: "apply" | "reject" | "dismiss" }
  | { kind: "applied"; decision: Decision }
  | { kind: "rejected"; dismissed: boolean }
  | { kind: "error"; message: string };

/**
 * Full review of one proposal. Apply / Reject / Revise, or Dismiss for a stale or failed one. Success only after the
 * DataClient confirms; the button is disabled while pending so a double-click cannot apply twice.
 */
export function ProposalReview({ proposalId, onClose }: Props) {
  // Keyed by proposal id so local phase/note reset whenever a different proposal is opened.
  return <ReviewBody key={proposalId ?? "none"} proposalId={proposalId} onClose={onClose} />;
}

function ReviewBody({ proposalId, onClose }: Props) {
  const { proposals, teams, spending, applyProposal, rejectProposal, refreshBudgets, askAssistant } = useAppStore();
  const proposal = proposalId ? proposals.find((p) => p.id === proposalId) : undefined;
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });
  const [note, setNote] = useState("");

  const busy = phase.kind === "pending";
  const canAct = proposal?.status === "proposed" && !busy;
  // A stale or failed proposal cannot be applied; dismissing it records a rejection so the history explains it.
  const canDismiss = (proposal?.status === "stale" || proposal?.status === "failed") && !busy && phase.kind === "idle";

  async function onApply() {
    if (!proposal || !canAct) return;
    setPhase({ kind: "pending", action: "apply" });
    try {
      const decision = await applyProposal(proposal.id, note.trim() || undefined);
      setPhase({ kind: "applied", decision });
    } catch (e) {
      await refreshBudgets(); // pick up stale/failed status set by the backend
      setPhase({ kind: "error", message: e instanceof Error ? e.message : "The change was not saved." });
    }
  }

  async function onReject(dismiss = false) {
    if (!proposal || (dismiss ? !canDismiss : !canAct)) return;
    setPhase({ kind: "pending", action: dismiss ? "dismiss" : "reject" });
    try {
      await rejectProposal(proposal.id);
      setPhase({ kind: "rejected", dismissed: dismiss });
    } catch (e) {
      setPhase({ kind: "error", message: e instanceof Error ? e.message : "Could not record the rejection." });
    }
  }

  function onRevise() {
    onClose();
    askAssistant("Revise this proposal: ");
  }

  const spentFor = (teamId: string) => spending.filter((r) => r.teamId === teamId).reduce((s, r) => s + r.amount, 0);
  const reviewed = (teamId: string) => proposal?.forecastsReviewed?.find((f) => f.teamId === teamId);
  const projectedFor = (teamId: string) => {
    const f = reviewed(teamId);
    return f?.status === "available" && typeof f.projected === "number" ? f.projected : undefined;
  };
  const closed = phase.kind === "applied" || phase.kind === "rejected";

  return (
    <Dialog open={!!proposalId} onOpenChange={(o) => { if (!o && !busy) onClose(); }}>
      <DialogContent className="max-h-[92dvh] gap-5 overflow-y-auto rounded-2xl border border-border bg-card p-6 sm:max-w-2xl">
        {!proposal ? (
          <DialogHeader>
            <DialogTitle>Proposal not found</DialogTitle>
            <DialogDescription>It may have been removed when the dataset changed.</DialogDescription>
          </DialogHeader>
        ) : (
          <>
            <DialogHeader className="gap-2 pr-8">
              <div className="flex flex-wrap items-center gap-2">
                <KindLabel kind={proposal.kind} />
                <ProposalStatusBadge status={phase.kind === "pending" ? "pending" : proposal.status} />
              </div>
              <DialogTitle className="leading-tight">{kindLabel(proposal)}</DialogTitle>
              <DialogDescription className="text-xs">
                <span className="num">{fmtDateTime(proposal.createdAt)}</span>
                {proposal.revisesProposalId && " · revises an earlier proposal"}
              </DialogDescription>
            </DialogHeader>

            {phase.kind === "applied" && <Receipt decision={phase.decision} />}
            {phase.kind === "rejected" && (
              <Banner tone="muted" icon={<X strokeWidth={1.5} />} title={phase.dismissed ? "Dismissed · allocations unchanged" : "Rejected · allocations unchanged"} />
            )}
            {phase.kind === "error" && (
              <Banner tone="destructive" icon={<AlertTriangle strokeWidth={1.5} />} title="Not applied · allocations unchanged">
                {phase.message}
              </Banner>
            )}
            {phase.kind === "idle" && proposal.status === "stale" && (
              <Banner tone="warn" icon={<History strokeWidth={1.5} />} title="Budgets changed since this was prepared" />
            )}
            {phase.kind === "idle" && proposal.status === "failed" && (
              <Banner tone="destructive" icon={<Ban strokeWidth={1.5} />} title="Refused · allocations unchanged">
                {proposal.failureReason}
              </Banner>
            )}

            {phase.kind !== "applied" && (
              <>
                <TotalBar before={proposal.totalBefore} after={proposal.totalAfter} unit={proposal.unit} kind={proposal.kind} />
                <PairedBars lines={proposal.lines} unit={proposal.unit} teams={teams} kind={proposal.kind} projection={projectedFor} />
                <Reveal show="Show table" hide="Hide table">
                  <AllocationTable
                    lines={proposal.lines}
                    unit={proposal.unit}
                    teams={teams}
                    kind={proposal.kind}
                    extra={[
                      { header: "Spent", cell: (l) => <span className="text-muted-foreground">{formatAmount(spentFor(l.teamId), proposal.unit)}</span> },
                      {
                        header: "Projection reviewed",
                        cell: (l) => {
                          const f = reviewed(l.teamId);
                          const proj = projectedFor(l.teamId);
                          if (proj === undefined || !f) return <span className="font-sans text-muted-foreground">{f?.unavailableReason ?? "None"}</span>;
                          return <span className={proj > l.after ? "text-destructive" : "text-muted-foreground"}>{formatAmount(proj, f.unit)}</span>;
                        },
                      },
                    ]}
                  />
                </Reveal>

                <section className="space-y-1.5">
              <h3 className="eyebrow">Why</h3>
              <p className="text-sm leading-relaxed text-foreground/80">{proposal.rationale}</p>
            </section>

            {proposal.citations.length > 0 && (
              <details className="group">
                <summary className="flex h-8 w-fit cursor-pointer list-none items-center gap-1.5 rounded-sm text-xs text-muted-foreground transition-colors duration-300 select-none hover:text-foreground [&::-webkit-details-marker]:hidden">
                  <ChevronRight className="size-4 transition-transform group-open:rotate-90" aria-hidden strokeWidth={1.5} />
                  <span>Evidence</span>
                  <span className="num text-xs text-muted-foreground">{proposal.citations.length}</span>
                </summary>
                <ul className="mt-1 divide-y divide-border border-l border-border pl-3">
                  {proposal.citations.map((c, i) => (
                    <li key={`${c.documentId}-${i}`} className="py-2.5 text-xs">
                      <div className="flex flex-wrap items-baseline gap-x-1.5 gap-y-0.5">
                        <span className="font-medium text-foreground">{c.title}</span>
                        {c.locator && <span className="text-muted-foreground">{c.locator}</span>}
                        {c.date && <span className="num text-muted-foreground">· {fmtDate(c.date, { year: true })}</span>}
                      </div>
                      {c.excerpt && <blockquote className="mt-1.5 border-l border-border-strong pl-2.5 leading-relaxed text-muted-foreground">“{c.excerpt}”</blockquote>}
                    </li>
                  ))}
                </ul>
              </details>
            )}
            </>)}

            {canAct && (
              <div className="space-y-2">
                <label htmlFor="decision-note" className="eyebrow block">
                  Note <span className="normal-case tracking-normal">(optional)</span>
                </label>
                <Textarea id="decision-note" value={note} onChange={(e) => setNote(e.target.value)} placeholder="For the record" className="min-h-16 text-sm" />
              </div>
            )}

            <DialogFooter className="mt-0">
              {closed ? (
                <Button variant="ghost" onClick={onClose}>Done</Button>
              ) : proposal.status === "stale" || proposal.status === "failed" ? (
                <>
                  <Button variant="link" onClick={onRevise} disabled={busy} className="sm:mr-auto">Ask for a refreshed proposal</Button>
                  <Button variant="ghost" onClick={onClose} disabled={busy}>Close</Button>
                  <Button onClick={() => void onReject(true)} disabled={!canDismiss} className="min-w-20">
                    {busy && phase.action === "dismiss" ? "Recording…" : "Dismiss"}
                  </Button>
                </>
              ) : proposal.status !== "proposed" ? (
                <Button variant="ghost" onClick={onClose}>Close</Button>
              ) : (
                <>
                  <Button variant="link" onClick={onRevise} disabled={busy} className="sm:mr-auto">Revise</Button>
                  <Button variant="ghost" onClick={() => void onReject(false)} disabled={!canAct}>
                    {busy && phase.action === "reject" ? "Recording…" : "Reject"}
                  </Button>
                  <Button onClick={onApply} disabled={!canAct} className="min-w-20">
                    {busy && phase.action === "apply" ? "Applying…" : "Apply"}
                  </Button>
                </>
              )}
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

function Banner({ tone, icon, title, children }: { tone: "ok" | "muted" | "warn" | "destructive"; icon: React.ReactNode; title: React.ReactNode; children?: React.ReactNode }) {
  return (
    <div
      role="status"
      className={cn(
        "flex gap-3 rounded-md border px-4 py-3 text-sm",
        tone === "ok" && "border-success/30 bg-success/10",
        tone === "muted" && "border-border bg-popover",
        tone === "warn" && "border-warning/30 bg-warning/10",
        tone === "destructive" && "border-destructive/30 bg-destructive/10",
      )}
    >
      <span
        aria-hidden
        className={cn(
          "mt-px shrink-0 [&>svg]:size-4",
          tone === "ok" && "text-success",
          tone === "warn" && "text-warning",
          tone === "destructive" && "text-destructive",
          tone === "muted" && "text-muted-foreground",
        )}
      >
        {icon}
      </span>
      <div className="min-w-0 space-y-0.5">
        <div className="leading-5 font-medium">{title}</div>
        {children && <div className="text-xs leading-relaxed text-muted-foreground">{children}</div>}
      </div>
    </div>
  );
}

/** Receipt shown after the backend confirms: one line (what, when, who), the paired bars, details collapsed. */
export function Receipt({ decision }: { decision: Decision }) {
  const teams = useAppStore((s) => s.teams);
  const projected = (teamId: string) => {
    const f = decision.forecastsReviewed?.find((x) => x.teamId === teamId);
    return f?.status === "available" && typeof f.projected === "number" ? f.projected : undefined;
  };
  // The why stays visible at rest: the note, else the rationale, one muted line (full text in the tooltip and details).
  const why = decision.note?.trim() || decision.rationale?.trim();
  return (
    <div className="space-y-4">
      <Banner
        tone="ok"
        icon={<Check strokeWidth={1.5} />}
        title={<>Applied <span className="num font-normal text-muted-foreground">· {fmtDateTime(decision.appliedAt)} · {decision.appliedBy}</span></>}
      >
        {why && <p className="line-clamp-1" title={why}>{why}</p>}
      </Banner>
      <PairedBars lines={decision.lines} unit={decision.unit} teams={teams} kind={decision.kind} projection={projected} />
      <Reveal show="Show details" hide="Hide details">
        <div className="space-y-3 text-sm">
          <AllocationTable lines={decision.lines} unit={decision.unit} teams={teams} kind={decision.kind} />
          {decision.note && <p className="text-muted-foreground italic">“{decision.note}”</p>}
          {decision.rationale && <p className="leading-relaxed text-foreground/80">{decision.rationale}</p>}
        </div>
      </Reveal>
    </div>
  );
}
