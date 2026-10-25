"use client";
import { displayCopy, displaySourceText } from "@/lib/display-copy";
import { useRef, useState } from "react";
import { AlertTriangle, Ban, Check, ChevronRight, FileText, History, X } from "lucide-react";
import type { AllocationProposal, Decision, Team, Unit } from "@/lib/contracts";
import { useAppStore } from "@/lib/store";
import { unitLabel } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { fmtDate, fmtDateTime } from "@/components/team/labels";
import { deltaClass, KindBadge, ProposalStatusBadge, teamColor, teamName } from "./proposal-bits";

interface Props {
  proposalId?: string;
  onClose: () => void;
}

/** Review one proposal. The store retains mutation outcomes across dialog visits. */
export function ProposalReview({ proposalId, onClose }: Props) {
  // Keyed by proposal id so the note resets without discarding the stored receipt.
  return <ReviewBody key={proposalId ?? "none"} proposalId={proposalId} onClose={onClose} />;
}

const TH = "eyebrow h-10 px-3 text-left align-middle whitespace-nowrap";
const TD = "px-3 align-middle";

function ReviewBody({ proposalId, onClose }: Props) {
  const { proposals, decisions, proposalActions, teams, applyProposal, rejectProposal, refreshBudgets, reconcileProposal, reviseProposal } = useAppStore();
  const proposal = proposalId ? proposals.find((p) => p.id === proposalId) : undefined;
  const action = proposalId ? proposalActions[proposalId] : undefined;
  const receipt = action?.receipt ?? decisions.find((d) => d.proposalId === proposalId);
  const [pendingAction, setPendingAction] = useState<"apply" | "reject" | "dismiss">();
  const [checking, setChecking] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [checkMessage, setCheckMessage] = useState<string>();
  const [localError, setLocalError] = useState<string>();
  const [note, setNote] = useState("");
  const headingRef = useRef<HTMLHeadingElement>(null);
  const changedLines = proposal?.lines.filter(line => line.after !== line.before) ?? [];
  const unchangedLines = proposal?.lines.filter(line => line.after === line.before) ?? [];

  const busy = action?.mutation === "pending" || (!action && pendingAction !== undefined);
  const unknown = action?.mutation === "unknown" && !receipt;
  const closed = action?.mutation === "confirmed" || !!receipt;
  const canAct = proposal?.status === "proposed" && !busy && !unknown && !closed;
  const canDismiss = (proposal?.status === "stale" || proposal?.status === "failed") && !busy && !unknown && !closed;
  const mutationError = !closed && !unknown && !busy ? action?.error ?? localError : undefined;

  async function onApply() {
    if (!proposal || !canAct) return;
    setLocalError(undefined);
    setPendingAction("apply");
    try {
      await applyProposal(proposal.id, note.trim() || undefined);
    } catch (e) {
      setLocalError(e instanceof Error ? e.message : "The request could not be confirmed. Check its status before trying again.");
    } finally {
      setPendingAction(undefined);
    }
  }

  async function onReject(dismiss = false) {
    if (!proposal || (dismiss ? !canDismiss : !canAct)) return;
    setLocalError(undefined);
    setPendingAction(dismiss ? "dismiss" : "reject");
    try {
      await rejectProposal(proposal.id);
    } catch (e) {
      setLocalError(e instanceof Error ? e.message : "The rejection could not be confirmed. Check its status before trying again.");
    } finally {
      setPendingAction(undefined);
    }
  }

  async function onCheckStatus() {
    if (!proposalId || checking) return;
    setChecking(true);
    setCheckMessage(undefined);
    try {
      const found = await reconcileProposal(proposalId);
      if (!found) setCheckMessage("No confirmed decision is available yet. Check again before making another request.");
    } catch (e) {
      setCheckMessage(e instanceof Error ? e.message : "Status could not be checked. The outcome is still unknown.");
    } finally {
      setChecking(false);
    }
  }

  async function onRefresh() {
    if (refreshing) return;
    setRefreshing(true);
    try {
      await refreshBudgets();
    } finally {
      setRefreshing(false);
    }
  }

  function onRevise() {
    if (!proposal) return;
    onClose();
    reviseProposal(proposal.id);
  }

  const outcome = (
    <>
      {receipt && <Receipt decision={receipt} />}
      {closed && !receipt && (
        <Banner tone={action?.action === "reject" ? "muted" : "ok"} icon={action?.action === "reject" ? <X strokeWidth={1.5} /> : <Check strokeWidth={1.5} />} title={action?.action === "reject" ? "Rejected and recorded" : "Applied and saved"}>
          The backend confirmed your decision. Its full history entry will appear after the view refreshes.
        </Banner>
      )}
      {closed && action?.sync === "failed" && (
        <Banner tone="warn" icon={<AlertTriangle strokeWidth={1.5} />} title="Decision saved; totals need refreshing">
          Your decision is confirmed. {displayCopy(action.syncError, "The latest totals could not be loaded.")}
          <Button variant="outline" size="sm" className="mt-2 block" onClick={() => void onRefresh()} disabled={refreshing}>
            {refreshing ? "Refreshing…" : "Retry refresh"}
          </Button>
        </Banner>
      )}
      {closed && action?.sync === "pending" && <p role="status" className="text-xs text-muted-foreground">Decision saved. Refreshing totals…</p>}
      {unknown && (
        <Banner tone="warn" icon={<AlertTriangle strokeWidth={1.5} />} title="Confirmation unavailable">
          This request may have been recorded. Check its status before making another request.
          {checkMessage && <p className="mt-1">{displayCopy(checkMessage, "Status could not be checked. The outcome is still unknown.")}</p>}
          <Button variant="outline" size="sm" className="mt-2 block" onClick={() => void onCheckStatus()} disabled={checking}>
            {checking ? "Checking…" : "Check status"}
          </Button>
        </Banner>
      )}
      {mutationError && (
        <Banner tone="destructive" icon={<AlertTriangle strokeWidth={1.5} />} title="Request could not be completed">
          {displayCopy(mutationError, "The request could not be completed.")}
        </Banner>
      )}
    </>
  );

  return (
    <Dialog open={!!proposalId} onOpenChange={(o) => { if (!o && !busy) onClose(); }}>
      <DialogContent initialFocus={headingRef} className="max-h-[92dvh] min-w-0 gap-5 overflow-x-hidden overflow-y-auto rounded-2xl border border-border bg-card p-6 sm:max-w-3xl">
        {!proposal ? (
          <>
            <DialogHeader>
              <DialogTitle ref={headingRef} tabIndex={-1} className="outline-none">{closed ? "Saved decision" : "Proposal not found"}</DialogTitle>
              <DialogDescription>The proposal details are not available in the current view.</DialogDescription>
            </DialogHeader>
            {outcome}
            <DialogFooter><Button variant="ghost" onClick={onClose} disabled={busy}>Close</Button></DialogFooter>
          </>
        ) : (
          <>
            <DialogHeader className="gap-2 pr-8">
              <div className="flex flex-wrap items-center gap-1.5">
                <KindBadge kind={proposal.kind} />
                {unknown ? <Badge variant="warning">Confirmation needed</Badge> : busy && (action?.action === "reject" || pendingAction === "reject" || pendingAction === "dismiss") ? (
                  <Badge variant="outline">Recording…</Badge>
                ) : <ProposalStatusBadge status={receipt?.action === "applied" ? "applied" : receipt?.action === "rejected" ? "rejected" : busy ? "pending" : proposal.status} />}
              </div>
              <DialogTitle ref={headingRef} tabIndex={-1} className="leading-tight outline-none">{proposal.kind === "add_budget" ? `Adds ${exactAmount(proposal.addedAmount ?? 0, proposal.unit)} to the total allocation` : "Redistributes the existing allocation"}</DialogTitle>
              <DialogDescription className="text-xs leading-relaxed">
                {proposal.kind === "add_budget"
                  ? "New funding is added to the total allocation. No team loses allocation."
                  : "Allocation moves between teams. The total allocation does not change."}
                {" "}Prepared <span className="num">{fmtDateTime(proposal.createdAt)}</span>.
                {proposal.revisesProposalId && " Revises an earlier proposal."}
              </DialogDescription>
              <p className="text-xs text-muted-foreground">
                Budget period reviewed · <span className="num">{fmtDate(proposal.period.start, { year: true })} – {fmtDate(proposal.period.end, { year: true })}</span> (UTC, inclusive)
              </p>
            </DialogHeader>

            {outcome}
            {!closed && !unknown && !busy && proposal.status === "stale" && (
              <Banner tone="warn" icon={<History strokeWidth={1.5} />} title="Budgets changed since this was prepared">
                Ask the assistant for a refreshed proposal, or dismiss this one to record that it was not used.
              </Banner>
            )}
            {!closed && !unknown && !busy && proposal.status === "failed" && (
              <Banner tone="destructive" icon={<Ban strokeWidth={1.5} />} title="Refused by the backend">
                {displayCopy(proposal.failureReason, "This change could not be applied.")}
              </Banner>
            )}

            <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
              <span className="eyebrow">Total allocation</span>
              <span className="num flex flex-wrap items-baseline gap-1.5 text-sm">
                <span className="text-muted-foreground">{exactAmount(proposal.totalBefore, proposal.unit)}</span>
                <span aria-hidden className="text-muted-foreground">→</span>
                <span className="font-medium">{exactAmount(proposal.totalAfter, proposal.unit)}</span>
                <ExactDelta before={proposal.totalBefore} after={proposal.totalAfter} unit={proposal.unit} kind={proposal.kind} />
              </span>
            </div>

            <section aria-label="Changed team allocations" className="min-w-0 space-y-2">
              <h3 className="eyebrow">{changedLines.length} {changedLines.length === 1 ? "team changes" : "teams change"}</h3>
              {changedLines.length ? <AllocationReviewTable lines={changedLines} proposal={proposal} teams={teams} label="Changed team allocations"/> : <p className="text-sm text-muted-foreground">No team allocations change in this proposal.</p>}
            </section>
            {unchangedLines.length > 0 && <details data-unchanged-allocations className="group min-w-0 overflow-hidden rounded-xl border border-border">
              <summary className="flex min-h-10 cursor-pointer list-none items-center gap-2 px-4 py-2 text-xs outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring [&::-webkit-details-marker]:hidden"><ChevronRight className="size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-90" aria-hidden/><span>{unchangedLines.length} unchanged {unchangedLines.length === 1 ? "allocation" : "allocations"}</span><span className="ml-auto text-muted-foreground">View amounts</span></summary>
              <AllocationReviewTable lines={unchangedLines} proposal={proposal} teams={teams} label="Unchanged team allocations"/>
            </details>}

            <section className="space-y-1.5">
              <h3 className="eyebrow">Why</h3>
              <p className="text-sm leading-relaxed text-foreground/80">{rationaleSummary(displayCopy(proposal.rationale, "No explanation available."))}</p>
              <details className="group rounded-xl border border-border">
                <summary className="flex min-h-10 cursor-pointer list-none items-center gap-2 px-4 py-2 text-sm select-none [&::-webkit-details-marker]:hidden">
                  <ChevronRight className="size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-90" aria-hidden strokeWidth={1.5} />
                  <span>Full explanation and assumptions</span>
                </summary>
                <p className="border-t border-border px-4 py-3 text-sm leading-relaxed break-words whitespace-pre-wrap text-muted-foreground">{displayCopy(proposal.rationale, "No explanation available.")}</p>
              </details>
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
                        <span className="font-medium text-foreground">{displaySourceText(c.title, "Source document")}</span>
                        {c.locator && <span className="text-muted-foreground">{displaySourceText(c.locator)}</span>}
                        {c.date && <span className="num text-muted-foreground">· {fmtDate(c.date, { year: true })}</span>}
                      </div>
                      {c.excerpt && <blockquote className="mt-1.5 border-l border-border-strong pl-2.5 leading-relaxed text-muted-foreground">“{displaySourceText(c.excerpt)}”</blockquote>}
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
              ) : unknown ? (
                <Button variant="ghost" onClick={onClose}>Close</Button>
              ) : proposal.status === "stale" || proposal.status === "failed" ? (
                <>
                  <Button variant="link" onClick={onRevise} disabled={busy} className="sm:mr-auto">Ask for a refreshed proposal</Button>
                  <Button variant="ghost" onClick={onClose} disabled={busy}>Close</Button>
                  <Button onClick={() => void onReject(true)} disabled={!canDismiss} className="min-w-20">
                    {busy && pendingAction === "dismiss" ? "Recording…" : "Dismiss"}
                  </Button>
                </>
              ) : proposal.status !== "proposed" ? (
                <Button variant="ghost" onClick={onClose}>Close</Button>
              ) : (
                <>
                  <Button variant="link" onClick={onRevise} disabled={busy} className="sm:mr-auto">Revise</Button>
                  <Button variant="ghost" onClick={() => void onReject(false)} disabled={!canAct}>
                    {busy && (action?.action === "reject" || pendingAction === "reject") ? "Recording…" : "Reject"}
                  </Button>
                  <Button onClick={onApply} disabled={!canAct} className="min-w-20">
                    {busy && (action?.action === "apply" || pendingAction === "apply") ? "Applying…" : "Apply"}
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

function AllocationReviewTable({lines,proposal,teams,label}: {lines:AllocationProposal["lines"];proposal:AllocationProposal;teams:Team[];label:string}) {
  const reviewed = (teamId:string) => proposal.forecastsReviewed?.find(f => f.teamId === teamId && !f.personId);
  return (
            <div className="min-w-0 max-w-full overflow-hidden rounded-xl border border-border">
              <div className="max-w-full overflow-x-auto" role="region" aria-label={label} tabIndex={0}>
                <table aria-label={label} className="w-full min-w-[600px] text-sm">
                  <thead>
                    <tr className="border-b border-border-strong">
                      <th scope="col" className={TH}>Team <span className="normal-case tracking-normal">({unitLabel(proposal.unit)})</span></th>
                      <th scope="col" className={cn(TH, "text-right")}>Before</th>
                      <th scope="col" className={cn(TH, "text-right")}>After</th>
                      <th scope="col" className={cn(TH, "text-right")}>Change</th>
                      <th scope="col" className={cn(TH, "hidden text-right sm:table-cell")}>Projection reviewed</th>
                    </tr>
                  </thead>
                  <tbody>
                    {lines.map((l) => {
                      const d = l.after - l.before;
                      const f = reviewed(l.teamId);
                      const compatible = f?.unit === proposal.unit && f.period.start === proposal.period.start && f.period.end === proposal.period.end && f.basis === "full_period";
                      const proj = compatible && f?.status === "available" && typeof f.projected === "number" ? f.projected : undefined;
                      const projection = proj !== undefined && f ? (
                        <span className={cn("num", proj > l.after ? "text-destructive" : "text-muted-foreground")} title={proj > l.after ? "Projected spend exceeds the new allocation" : undefined}>
                          {exactAmount(proj, f.unit)}
                        </span>
                      ) : (
                        <span className="text-xs text-muted-foreground">{f && !compatible ? "Not comparable to this period" : displayCopy(f?.unavailableReason, "Unavailable")}</span>
                      );
                      return (
                        <tr key={l.teamId} className={cn("h-12 border-b border-border transition-colors duration-300 last:border-0 hover:bg-popover", d === 0 && "text-muted-foreground")}>
                          <td className={cn(TD, "min-w-[150px] max-w-[220px] py-3")}>
                            <span className="flex items-center gap-2">
                              <span aria-hidden className="size-1.5 shrink-0 rounded-full" style={{ background: teamColor(teams, l.teamId) }} />
                              <span className="break-words whitespace-normal">{teamName(teams, l.teamId)}</span>
                            </span>
                            <span className="mt-0.5 block pl-3.5 text-xs text-muted-foreground sm:hidden">
                              Projection reviewed · {projection}
                            </span>
                          </td>
                          <td className={cn(TD, "num text-right text-muted-foreground")}>{exactAmount(l.before, proposal.unit)}</td>
                          <td className={cn(TD, "num text-right", d !== 0 && "font-medium")}>{exactAmount(l.after, proposal.unit)}</td>
                          <td className={cn(TD, "text-right text-xs whitespace-nowrap")}><ExactDelta before={l.before} after={l.after} unit={proposal.unit} kind={proposal.kind} /></td>
                          <td className={cn(TD, "hidden max-w-[180px] text-right break-words whitespace-normal sm:table-cell")}>{projection}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

  );
}

function rationaleSummary(rationale: string) {
  const firstParagraph = rationale.trim().split(/\n\s*\n/, 1)[0].replace(/\s+/g, " ");
  const firstSentence = firstParagraph.match(/^.*?[.!?](?:\s|$)/)?.[0].trim() ?? firstParagraph;
  if (firstSentence.length <= 240) return firstSentence;
  return `${firstSentence.slice(0, 237).replace(/\s+\S*$/, "")}…`;
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
    <Banner tone={decision.action === "rejected" ? "muted" : "ok"} icon={decision.action === "rejected" ? <X strokeWidth={1.5} /> : <Check strokeWidth={1.5} />} title={decision.action === "rejected" ? "Rejected and recorded" : "Applied and saved"}>
      <span className="text-foreground/80">
        {decision.action === "rejected" ? "This proposal did not change allocations. The rejection is in the decision history." : changed.length === 0
          ? "No allocation changed."
          : changed.map((l, i) => (
              <span key={l.teamId}>
                {i > 0 && <span className="text-muted-foreground"> · </span>}
                {teamName(teams, l.teamId)} <span className="num">{exactAmount(l.before, decision.unit)} → {exactAmount(l.after, decision.unit)}</span> (<ExactDelta before={l.before} after={l.after} unit={decision.unit} kind={decision.kind} />)
              </span>
            ))}
      </span>
      <br />
      <span className="num">{fmtDateTime(decision.appliedAt)}</span> by {displaySourceText(decision.appliedBy === "finance-demo" ? "Finance" : decision.appliedBy, "Finance")}
      {decision.note ? <> · <span className="italic">“{displaySourceText(decision.note)}”</span></> : null}
    </Banner>
  );
}

// Format the decimal values supplied by the contract without compacting or losing cents.
// Subtract scaled integers so a $0.30 → $0.40 change never displays floating-point noise.
function decimalValue(value: number) {
  const [mantissa, exponent = "0"] = value.toString().split("e");
  const [whole, fraction = ""] = mantissa.split(".");
  const scale = fraction.length - Number(exponent);
  return { integer: BigInt(`${whole}${fraction}`) * BigInt(10) ** BigInt(Math.max(0, -scale)), scale: Math.max(0, scale) };
}

function decimalAmount(integer: bigint, scale: number, unit: Unit) {
  const digits = (integer < BigInt(0) ? -integer : integer).toString().padStart(scale + 1, "0");
  const whole = (scale ? digits.slice(0, -scale) : digits).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const fraction = scale ? digits.slice(-scale).replace(/0+$/, "") : "";
  const amount = `${integer < BigInt(0) ? "−" : ""}${unit === "usd" ? "$" : ""}${whole}${fraction ? `.${fraction}` : ""}`;
  return unit === "usd" ? amount : `${amount} ${unit === "credits" ? "cr" : "tokens"}`;
}

function exactAmount(value: number, unit: Unit) {
  if (!Number.isFinite(value)) return "Unavailable";
  const { integer, scale } = decimalValue(value);
  return decimalAmount(integer, scale, unit);
}

function ExactDelta({ before, after, unit, kind }: { before: number; after: number; unit: Unit; kind: Decision["kind"] }) {
  if (!Number.isFinite(before) || !Number.isFinite(after)) return <span className="text-muted-foreground">Unavailable</span>;
  const a = decimalValue(before);
  const b = decimalValue(after);
  const scale = Math.max(a.scale, b.scale);
  const delta = b.integer * BigInt(10) ** BigInt(scale - b.scale) - a.integer * BigInt(10) ** BigInt(scale - a.scale);
  const sign = delta > BigInt(0) ? 1 : delta < BigInt(0) ? -1 : 0;
  return <span className={cn("num text-xs", deltaClass(sign, kind))}>{delta === BigInt(0) ? "no change" : `${delta > BigInt(0) ? "+" : ""}${decimalAmount(delta, scale, unit)}`}</span>;
}
