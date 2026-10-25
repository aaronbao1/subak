"use client";
import { useState } from "react";
import { ChevronRight } from "lucide-react";
import type { AllocationProposal, Decision } from "@/lib/contracts";
import { useAppStore } from "@/lib/store";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { formatAmount } from "@/lib/format";
import { cn } from "@/lib/utils";
import { PageTitle } from "@/components/shared/stat-tile";
import { fmtDate, fmtDateTime } from "@/components/team/labels";
import { AllocationTable, decisionTotals, DeltaChip, kindShort, MiniTotal, PairedBars, ProposalStatusBadge, Reveal, teamColor, teamName, TotalBar } from "./proposal-bits";
import { ProposalReview } from "./proposal-review";

/** /decisions: receipts newest first, plus proposals that still need attention. */
export function DecisionLog() {
  const { loaded, decisions, proposals, teams, setAssistantOpen } = useAppStore();
  const [reviewId, setReviewId] = useState<string | undefined>();

  if (!loaded) {
    return (
      <div className="space-y-6">
        <div className="space-y-2">
          <Skeleton className="h-7 w-28" />
        </div>
        <Skeleton className="h-12 w-full rounded-xl" />
        <Skeleton className="h-12 w-full rounded-xl" />
      </div>
    );
  }

  const attention = proposals.filter((p) => p.status === "proposed" || p.status === "stale" || p.status === "failed");

  return (
    <div className="space-y-8">
      <PageTitle title="Decisions" />

      {attention.length > 0 && (
        <section className="space-y-3" aria-label="Needs attention">
          <h2 className="eyebrow">Needs attention</h2>
          <ul className="divide-y divide-border rounded-xl border border-border bg-card">
            {attention.map((p) => (
              <li key={p.id}><AttentionRow p={p} onOpen={() => setReviewId(p.id)} /></li>
            ))}
          </ul>
        </section>
      )}

      <section className="space-y-3" aria-label="History">
        {attention.length > 0 && <h2 className="eyebrow">History</h2>}
        {decisions.length === 0 ? (
          <div className="flex flex-col items-center gap-3 rounded-xl border border-border px-6 py-16 text-center">
            <div className="space-y-1">
              <div className="eyebrow">No decisions yet</div>
              <p className="text-sm text-muted-foreground">Applied proposals land here.</p>
            </div>
            <Button variant="outline" size="lg" onClick={() => setAssistantOpen(true)}>Ask the assistant</Button>
          </div>
        ) : (
          <ol className="divide-y divide-border rounded-xl border border-border bg-card">
            {decisions.map((d) => (
              <li key={d.id}><DecisionReceipt d={d} teams={teams} /></li>
            ))}
          </ol>
        )}
      </section>

      <ProposalReview proposalId={reviewId} onClose={() => setReviewId(undefined)} />
    </div>
  );
}

/** One row for a proposal that still needs finance: awaiting review, stale, or refused. Stale and failed can be dismissed. */
function AttentionRow({ p, onOpen }: { p: AllocationProposal; onOpen: () => void }) {
  const rejectProposal = useAppStore((s) => s.rejectProposal);
  const [dismissing, setDismissing] = useState(false);
  const [error, setError] = useState<string | undefined>();
  const proposed = p.status === "proposed";
  const dismissable = p.status === "stale" || p.status === "failed";

  async function dismiss() {
    if (!dismissable || dismissing) return;
    setDismissing(true);
    setError(undefined);
    try {
      await rejectProposal(p.id); // records a rejection so the history explains why this proposal was not used
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not record the dismissal.");
      setDismissing(false);
    }
  }

  return (
    <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-3 px-5 py-3">
      <div className="min-w-0 flex-1 space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <ProposalStatusBadge status={dismissing ? "pending" : p.status} />
          <span className="text-sm">{kindShort(p.kind)}</span>
          <span className="num text-xs text-muted-foreground">{fmtDate(p.createdAt)}</span>
        </div>
        <TotalBar before={p.totalBefore} after={p.totalAfter} unit={p.unit} kind={p.kind} className="max-w-sm" />
        {p.status === "failed" && <div className="text-xs text-destructive">{p.failureReason ?? "Refused by the backend."}</div>}
        {error && <div className="text-xs text-destructive">{error}</div>}
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {dismissable && (
          <Button size="sm" variant="ghost" onClick={() => void dismiss()} disabled={dismissing}>
            {dismissing ? "Recording…" : "Dismiss"}
          </Button>
        )}
        <Button size="sm" variant={proposed ? "default" : "ghost"} onClick={onOpen} disabled={dismissing}>
          {proposed ? "Review" : "Details"}
        </Button>
      </div>
    </div>
  );
}

/** Compact receipt row: status dot, kind, date, total as a tiny bar, deltas as chips. Click for details. */
function DecisionReceipt({ d, teams }: { d: Decision; teams: ReturnType<typeof useAppStore.getState>["teams"] }) {
  const [open, setOpen] = useState(false);
  const applied = d.action === "applied";
  const { before, after } = decisionTotals(d);
  const changed = applied ? [...d.lines].filter((l) => l.after !== l.before).sort((a, b) => Math.abs(b.after - b.before) - Math.abs(a.after - a.before)) : [];
  const chips = changed.slice(0, 3);
  const projected = (teamId: string) => {
    const f = d.forecastsReviewed?.find((x) => x.teamId === teamId);
    return f?.status === "available" && typeof f.projected === "number" ? f.projected : undefined;
  };
  const unavailable = (d.forecastsReviewed ?? []).filter((f) => f.status !== "available" || typeof f.projected !== "number");

  return (
    <article>
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="grid w-full grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-4 gap-y-2 px-5 py-3 text-left transition-colors duration-300 outline-none hover:bg-popover focus-visible:ring-2 focus-visible:ring-ring sm:grid-cols-[auto_7rem_6.5rem_minmax(0,1fr)_auto]"
      >
        <span className="flex items-center gap-2" title={applied ? "Applied" : "Rejected"}>
          <span aria-hidden className={cn("size-1.5 rounded-full", applied ? "bg-success" : "bg-muted-foreground")} />
          <span className="sr-only">{applied ? "Applied" : "Rejected"}</span>
          <ChevronRight aria-hidden strokeWidth={1.5} className={cn("size-4 text-muted-foreground transition-transform duration-150", open && "rotate-90")} />
        </span>
        <span className={cn("text-sm", !applied && "text-muted-foreground")}>{kindShort(d.kind)}</span>
        <span className="num hidden text-xs text-muted-foreground sm:block">{fmtDate(d.appliedAt)}</span>
        <span className="hidden min-w-0 flex-wrap items-center gap-1.5 sm:flex">
          {!applied ? (
            <span className="text-xs text-muted-foreground">Rejected</span>
          ) : chips.length === 0 ? (
            <span className="text-xs text-muted-foreground">No change</span>
          ) : (
            <>
              {chips.map((l) => (
                <span key={l.teamId} className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                  <span aria-hidden className="size-1.5 rounded-full" style={{ background: teamColor(teams, l.teamId) }} />
                  <span className="max-w-[7rem] truncate">{teamName(teams, l.teamId)}</span>
                  <DeltaChip n={l.after - l.before} unit={d.unit} kind={d.kind} />
                </span>
              ))}
              {changed.length > chips.length && <span className="num text-xs text-muted-foreground">+{changed.length - chips.length}</span>}
            </>
          )}
        </span>
        <MiniTotal before={before} after={after} unit={d.unit} kind={d.kind} applied={applied} />
      </button>

      {open && (
        <div className="space-y-4 px-5 pt-1 pb-5 sm:pl-[4.25rem]">
          <div className="text-xs text-muted-foreground">
            <span className={applied ? "text-success" : undefined}>{applied ? "Applied" : "Rejected"}</span>
            {" · "}<span className="num">{fmtDateTime(d.appliedAt)}</span> · {d.appliedBy}
          </div>
          {applied && <PairedBars lines={d.lines} unit={d.unit} teams={teams} kind={d.kind} projection={projected} />}
          {unavailable.length > 0 && (
            <ul className="space-y-0.5 text-xs text-muted-foreground">
              {unavailable.map((f) => (
                <li key={f.teamId}>{teamName(teams, f.teamId)} · projection {f.unavailableReason ?? "unavailable"}</li>
              ))}
            </ul>
          )}
          {d.note && <p className="text-sm text-muted-foreground italic">“{d.note}”</p>}
          {d.rationale && <p className="max-w-prose text-sm leading-relaxed text-foreground/80">{d.rationale}</p>}
          <Reveal show="Show table" hide="Hide table">
            <AllocationTable
              lines={d.lines}
              unit={d.unit}
              teams={teams}
              kind={d.kind}
              extra={d.forecastsReviewed?.length ? [{
                header: "Projection reviewed",
                cell: (l) => {
                  const p = projected(l.teamId);
                  return p === undefined ? <span className="font-sans text-muted-foreground">—</span> : <span className="text-muted-foreground">{formatAmount(p, d.unit)}</span>;
                },
              }] : []}
            />
          </Reveal>
        </div>
      )}
    </article>
  );
}
