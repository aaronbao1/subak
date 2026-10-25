"use client";
import { useState } from "react";
import { AlertTriangle, Ban, Check, ChevronRight, FileText, History, X } from "lucide-react";
import type { Decision } from "@/lib/contracts";
import { useAppStore } from "@/lib/store";
import { formatAmount, unitLabel } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { fmtDate, fmtDateTime, PlaceholderBadge } from "@/components/team/labels";
import { Delta, EnvelopeLine, KindBadge, kindLabel, ProposalStatusBadge, teamColor, teamName } from "./proposal-bits";

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

const TH = "eyebrow h-10 px-4 text-left align-middle whitespace-nowrap";
const TD = "px-4 align-middle";

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
  const anyPlaceholder = proposal?.forecastsReviewed?.some((f) => f.origin === "placeholder") ?? false;
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
              <div className="flex flex-wrap items-center gap-1.5">
                <KindBadge kind={proposal.kind} />
                <ProposalStatusBadge status={phase.kind === "pending" ? "pending" : proposal.status} />
              </div>
              <DialogTitle className="leading-tight">{kindLabel(proposal)}</DialogTitle>
              <DialogDescription className="text-xs leading-relaxed">
                {proposal.kind === "add_budget"
                  ? "New funding is added to the total allocation. No team loses allocation."
                  : "Money moves between teams. The total allocation does not change."}
                {" "}Prepared <span className="num">{fmtDateTime(proposal.createdAt)}</span>.
                {proposal.revisesProposalId && " Revises an earlier proposal."}
              </DialogDescription>
            </DialogHeader>

            {/* Outcome banners */}
            {phase.kind === "applied" && <Receipt decision={phase.decision} />}
            {phase.kind === "rejected" && (
              <Banner tone="muted" icon={<X strokeWidth={1.5} />} title={phase.dismissed ? "Dismissed and recorded" : "Rejected and recorded"}>
                Allocations are unchanged. The {phase.dismissed ? "dismissal" : "rejection"} is in the decision history.
              </Banner>
            )}
            {phase.kind === "error" && (
              <Banner tone="destructive" icon={<AlertTriangle strokeWidth={1.5} />} title="Not applied">
                {phase.message} Allocations are unchanged.
              </Banner>
            )}
            {phase.kind === "idle" && proposal.status === "stale" && (
              <Banner tone="warn" icon={<History strokeWidth={1.5} />} title="Budgets changed since this was prepared">
                Ask the assistant for a refreshed proposal, or dismiss this one to record that it was not used.
              </Banner>
            )}
            {phase.kind === "idle" && proposal.status === "failed" && (
              <Banner tone="destructive" icon={<Ban strokeWidth={1.5} />} title="Refused by the backend">
                {proposal.failureReason ?? "The backend refused this change."} Allocations are unchanged.
              </Banner>
            )}

            <EnvelopeLine before={proposal.totalBefore} after={proposal.totalAfter} unit={proposal.unit} kind={proposal.kind} />

            <div className="overflow-hidden rounded-xl border border-border">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border-strong">
                      <th scope="col" className={TH}>Team <span className="normal-case tracking-normal">({unitLabel(proposal.unit)})</span></th>
                      <th scope="col" className={cn(TH, "text-right")}>Before</th>
                      <th scope="col" className={cn(TH, "text-right")}>After</th>
                      <th scope="col" className={cn(TH, "text-right")}>Change</th>
                      <th scope="col" className={cn(TH, "hidden text-right sm:table-cell")}>Spent</th>
                      <th scope="col" className={cn(TH, "hidden text-right sm:table-cell")}>Projection reviewed</th>
                    </tr>
                  </thead>
                  <tbody>
                    {proposal.lines.map((l) => {
                      const d = l.after - l.before;
                      const f = reviewed(l.teamId);
                      const proj = f?.status === "available" && typeof f.projected === "number" ? f.projected : undefined;
                      const projection = proj !== undefined && f ? (
                        <span className={cn("num", proj > l.after ? "text-destructive" : "text-muted-foreground")} title={proj > l.after ? "Projected spend exceeds the new allocation" : undefined}>
                          {formatAmount(proj, f.unit, { compact: true })}
                        </span>
                      ) : (
                        <span className="text-xs text-muted-foreground">{f?.unavailableReason ?? "None"}</span>
                      );
                      return (
                        <tr key={l.teamId} className={cn("h-12 border-b border-border transition-colors duration-300 last:border-0 hover:bg-popover", d === 0 && "text-muted-foreground")}>
                          <td className={TD}>
                            <span className="flex items-center gap-2">
                              <span aria-hidden className="size-1.5 shrink-0 rounded-full" style={{ background: teamColor(teams, l.teamId) }} />
                              <span className="truncate">{teamName(teams, l.teamId)}</span>
                            </span>
                            <span className="mt-0.5 block pl-3.5 text-xs text-muted-foreground sm:hidden">
                              Projection reviewed · {projection}
                            </span>
                          </td>
                          <td className={cn(TD, "num text-right text-muted-foreground")}>{formatAmount(l.before, proposal.unit, { compact: true })}</td>
                          <td className={cn(TD, "num text-right", d !== 0 && "font-medium")}>{formatAmount(l.after, proposal.unit, { compact: true })}</td>
                          <td className={cn(TD, "text-right text-xs whitespace-nowrap")}><Delta n={d} unit={proposal.unit} kind={proposal.kind} compact /></td>
                          <td className={cn(TD, "num hidden text-right text-muted-foreground sm:table-cell")}>{formatAmount(spentFor(l.teamId), proposal.unit, { compact: true })}</td>
                          <td className={cn(TD, "hidden text-right sm:table-cell")}>{projection}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            {anyPlaceholder && (
              <p className="-mt-2 flex items-center gap-2 text-xs leading-relaxed text-muted-foreground">
                <PlaceholderBadge className="shrink-0" />
                Projections reviewed here are shared placeholder numbers, not the output of the forecasting service.
              </p>
            )}

            <section className="space-y-1.5">
              <h3 className="eyebrow">Why</h3>
              <p className="text-sm leading-relaxed text-foreground/80">{proposal.rationale}</p>
            </section>

            {proposal.citations.length > 0 && (
              <details className="group rounded-xl border border-border">
                <summary className="flex h-10 cursor-pointer list-none items-center gap-2 px-4 text-sm select-none [&::-webkit-details-marker]:hidden">
                  <ChevronRight className="size-4 text-muted-foreground transition-transform group-open:rotate-90" aria-hidden strokeWidth={1.5} />
                  <FileText className="size-4 text-muted-foreground" aria-hidden strokeWidth={1.5} />
                  <span>Evidence</span>
                  <span className="num text-xs text-muted-foreground">{proposal.citations.length}</span>
                  <span className="ml-auto text-xs text-muted-foreground group-open:hidden">Show</span>
                  <span className="ml-auto hidden text-xs text-muted-foreground group-open:inline">Hide</span>
                </summary>
                <ul className="divide-y divide-border border-t border-border">
                  {proposal.citations.map((c, i) => (
                    <li key={`${c.documentId}-${i}`} className="px-4 py-3 text-xs">
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

            {canAct && (
              <div className="space-y-2">
                <label htmlFor="decision-note" className="eyebrow block">
                  Note for the record <span className="normal-case tracking-normal">(optional)</span>
                </label>
                <Textarea id="decision-note" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Why finance is applying this" className="min-h-16 text-sm" />
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

function Banner({ tone, icon, title, children }: { tone: "ok" | "muted" | "warn" | "destructive"; icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <div
      role="status"
      className={cn(
        "flex gap-3 rounded-md border p-4 text-sm",
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
        <div className="text-xs leading-relaxed text-muted-foreground">{children}</div>
      </div>
    </div>
  );
}

/** Receipt shown after the backend confirms. What changed, when, who. */
export function Receipt({ decision }: { decision: Decision }) {
  const teams = useAppStore((s) => s.teams);
  const changed = decision.lines.filter((l) => l.after !== l.before);
  return (
    <Banner tone="ok" icon={<Check strokeWidth={1.5} />} title="Applied and saved">
      <span className="text-foreground/80">
        {changed.length === 0
          ? "No allocation changed."
          : changed.map((l, i) => (
              <span key={l.teamId}>
                {i > 0 && <span className="text-muted-foreground"> · </span>}
                {teamName(teams, l.teamId)} <Delta n={l.after - l.before} unit={decision.unit} kind={decision.kind} />
              </span>
            ))}
      </span>
      <br />
      <span className="num">{fmtDateTime(decision.appliedAt)}</span> by {decision.appliedBy}
      {decision.note ? <> · <span className="italic">“{decision.note}”</span></> : null}
    </Banner>
  );
}
