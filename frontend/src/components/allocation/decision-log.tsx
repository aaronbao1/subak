"use client";
import { displayCopy, displaySourceText } from "@/lib/display-copy";
import { useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import type { AllocationProposal, Decision } from "@/lib/contracts";
import { useAppStore } from "@/lib/store";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { formatAmount } from "@/lib/format";
import { cn } from "@/lib/utils";
import { PageTitle } from "@/components/shared/stat-tile";
import { fmtDateTime } from "@/components/team/labels";
import { AllocationLines, decisionTotals, Delta, KindBadge, kindLabel, ProposalStatusBadge, teamName } from "./proposal-bits";
import { ProposalReview } from "./proposal-review";

/** /decisions: receipts newest first, plus proposals that still need attention. */
export function DecisionLog() {
  const { loaded, decisions, proposals, teams, setAssistantOpen } = useAppStore();
  const [reviewId, setReviewId] = useState<string | undefined>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const status = searchParams.get("status") ?? "all";
  const team = searchParams.get("team") ?? "all";
  const period = searchParams.get("period") ?? "all";
  function updateFilter(name: string, value: string) {
    const next = new URLSearchParams(searchParams.toString());
    if (value === "all") next.delete(name); else next.set(name, value);
    router.replace(`${pathname}${next.size ? `?${next}` : ""}`, { scroll: false });
  }

  if (!loaded) {
    return (
      <div className="space-y-6">
        <div className="space-y-2">
          <Skeleton className="h-7 w-28" />
          <Skeleton className="h-4 w-72 max-w-full" />
        </div>
        <Skeleton className="h-24 w-full rounded-xl" />
        <Skeleton className="h-24 w-full rounded-xl" />
      </div>
    );
  }

  const periodKey = (p: AllocationProposal) => `${p.period.start}_${p.period.end}`;
  const periods = [...new Map(proposals.map(p => [periodKey(p), p.period])).entries()];
  const attention = proposals.filter((p) => (p.status === "proposed" || p.status === "stale" || p.status === "failed")
    && (status === "all" || status === "pending")
    && (team === "all" || p.lines.some(l => l.teamId === team && l.after !== l.before))
    && (period === "all" || periodKey(p) === period));
  const history = decisions.filter(d => (status === "all" || d.action === status)
    && (team === "all" || d.lines.some(l => l.teamId === team && l.after !== l.before))
    && (period === "all" || proposals.some(p => p.id === d.proposalId && periodKey(p) === period)));

  return (
    <div className="space-y-8">
      <PageTitle title="Decisions" description="Review proposed changes and see exactly what was saved." />

      <div className="flex flex-wrap items-end gap-3 rounded-lg border border-border bg-card p-3">
        <label className="flex min-w-36 flex-1 flex-col gap-1.5 text-xs text-muted-foreground">Status
          <select value={status} onChange={e => updateFilter("status", e.target.value)} className="h-9 rounded-md border border-input bg-background px-2 text-sm text-foreground"><option value="all">All statuses</option><option value="pending">Needs review</option><option value="applied">Applied</option><option value="rejected">Rejected</option></select>
        </label>
        <label className="flex min-w-36 flex-1 flex-col gap-1.5 text-xs text-muted-foreground">Team
          <select value={team} onChange={e => updateFilter("team", e.target.value)} className="h-9 rounded-md border border-input bg-background px-2 text-sm text-foreground"><option value="all">All teams</option>{teams.map(t => <option key={t.id} value={t.id}>{displaySourceText(t.name, "Team")}</option>)}</select>
        </label>
        <label className="flex min-w-36 flex-1 flex-col gap-1.5 text-xs text-muted-foreground">Budget period
          <select value={period} onChange={e => updateFilter("period", e.target.value)} className="h-9 rounded-md border border-input bg-background px-2 text-sm text-foreground"><option value="all">All periods</option>{periods.map(([key, p]) => <option key={key} value={key}>{displayCopy(p.label, "Budget period")}</option>)}</select>
        </label>
        {(status !== "all" || team !== "all" || period !== "all") && <Button variant="ghost" onClick={() => router.replace(pathname, { scroll: false })}>Clear filters</Button>}
      </div>

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
        {history.length === 0 ? (
          <div className="flex flex-col items-center gap-3 rounded-xl border border-border px-6 py-16 text-center">
            <div className="space-y-1">
              <div className="eyebrow">{decisions.length ? "No matching decisions" : "No decisions yet"}</div>
              <p className="max-w-xs text-sm leading-relaxed text-muted-foreground">
                {decisions.length ? "Change your filters to see more receipts." : "Ask the assistant for a proposal, review it, and apply or reject it. The receipt lands here."}
              </p>
            </div>
            <Button variant="outline" size="lg" onClick={() => setAssistantOpen(true)}>Ask the assistant</Button>
          </div>
        ) : (
          <ol className="divide-y divide-border rounded-xl border border-border bg-card">
            {history.map((d) => (
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
    <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-3 px-5 py-4">
      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex flex-wrap items-center gap-1.5">
          <KindBadge kind={p.kind} />
          <ProposalStatusBadge status={dismissing ? "pending" : p.status} />
        </div>
        <div className="text-sm leading-snug font-medium">{kindLabel(p)}</div>
        <div className={cn("text-xs leading-snug text-muted-foreground", p.status === "failed" && "text-destructive")}>
          {p.status === "proposed" && <>Prepared <span className="num">{fmtDateTime(p.createdAt)}</span>. Not saved until applied.</>}
          {p.status === "stale" && "Budgets changed since this was prepared. Ask for a refreshed proposal or dismiss it."}
          {p.status === "failed" && displayCopy(p.failureReason, "This change could not be applied.")}
        </div>
        {error && <div className="text-xs text-destructive">{displayCopy(error, "The dismissal could not be recorded.")}</div>}
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

function DecisionReceipt({ d, teams }: { d: Decision; teams: ReturnType<typeof useAppStore.getState>["teams"] }) {
  const [open, setOpen] = useState(false);
  const applied = d.action === "applied";
  const { before, after } = decisionTotals(d);
  const changed = d.lines.filter((l) => l.after !== l.before);

  return (
    <article className="space-y-3 px-5 py-4">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="min-w-0 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="eyebrow inline-flex items-center gap-1.5">
              <span aria-hidden className={cn("size-1.5 rounded-full", applied ? "bg-success" : "bg-muted-foreground")} />
              {applied ? "Applied" : "Rejected"}
            </span>
            <span className="num text-xs text-muted-foreground">{fmtDateTime(d.appliedAt)}</span>
            <span aria-hidden className="text-xs text-muted-foreground">·</span>
            <span className="text-xs text-muted-foreground">{displaySourceText(d.appliedBy === "finance-demo" ? "Finance" : d.appliedBy, "Finance")}</span>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <KindBadge kind={d.kind} />
          </div>
        </div>
        <div className="text-right">
          <div className="eyebrow">Total allocation</div>
          {applied ? (
            <div className="num mt-1 flex items-baseline justify-end gap-1.5 text-sm">
              <span className="text-muted-foreground">{formatAmount(before, d.unit)}</span>
              <span aria-hidden className="text-muted-foreground">→</span>
              <span className="font-medium">{formatAmount(after, d.unit)}</span>
            </div>
          ) : (
            <div className="mt-1 text-sm text-muted-foreground"><span className="num">{formatAmount(before, d.unit)}</span> <span className="text-xs">unchanged</span></div>
          )}
        </div>
      </div>

      <p className={cn("text-sm leading-relaxed", !applied && "text-muted-foreground")}>
        {applied ? (
          changed.length ? (
            changed.map((l, i) => (
              <span key={l.teamId}>
                {i > 0 && <span aria-hidden className="mx-1.5 text-muted-foreground">·</span>}
                {teamName(teams, l.teamId)} <Delta n={l.after - l.before} unit={d.unit} kind={d.kind} />
              </span>
            ))
          ) : "No allocation changed."
        ) : "Allocations left unchanged."}
      </p>

      {d.note && <p className="text-sm leading-relaxed text-muted-foreground italic">“{displaySourceText(d.note)}”</p>}

      <div>
        <Button variant="link" size="xs" className="h-auto px-0 text-xs text-muted-foreground hover:text-foreground" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
          {open ? "Hide details" : "Show details"}
        </Button>
        {open && (
          <div className="mt-3 space-y-5 border-t border-border pt-4">
            <div className="space-y-1">
              <div className="eyebrow">Per team</div>
              <AllocationLines lines={d.lines} unit={d.unit} teams={teams} kind={d.kind} />
            </div>
            {d.rationale && (
              <div className="space-y-1.5">
                <div className="eyebrow">Why</div>
                <p className="text-sm leading-relaxed text-foreground/80">{displayCopy(d.rationale, "No explanation available.")}</p>
              </div>
            )}
            {d.forecastsReviewed && d.forecastsReviewed.length > 0 && (
              <div className="space-y-1.5">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="eyebrow">Projections reviewed at the time</span>
                </div>
                <ul className="divide-y divide-border text-sm">
                  {d.forecastsReviewed.map((f) => (
                    <li key={f.teamId} className="flex h-10 items-center justify-between gap-3">
                      <span>{teamName(teams, f.teamId)}</span>
                      <span className="inline-flex items-center gap-2 text-muted-foreground">
                        <span className="num">{f.status === "available" && typeof f.projected === "number" ? formatAmount(f.projected, f.unit) : displayCopy(f.unavailableReason, "Unavailable")}</span>                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </article>
  );
}
