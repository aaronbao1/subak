"use client";
import { useMemo, useState } from "react";
import Link from "next/link";
import { ArrowUpRight, CalendarDays, ChevronRight, FileCheck2 } from "lucide-react";
import { useAppStore } from "@/lib/store";
import { selectScopeSummary } from "@/lib/finance-summary";
import { rankForecastInsights } from "@/lib/driver-insights";
import { driverStart } from "@/lib/planning-drafts";
import { DriverDetail } from "@/components/forecast/driver-detail";
import { scopeView } from "./forecast-derive";
import { buildOverviewPriorities, type OverviewPriority } from "./overview-priorities-derive";
import { chartDate, chartMoney } from "@/components/forecast/chart-data";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { SourceSheet } from "@/components/team/source-sheet";

export function OverviewPriorities({ hideBudget = false }: { hideBudget?: boolean }) {
  const { company, teams, spending, budgets, forecastBundle, forecastEvidence, context, proposals } = useAppStore();
  const [selection, setSelection] = useState<{ id: string; contextKey: string }>();
  const [documentId, setDocumentId] = useState<string>();
  const period = company?.currentPeriod ?? budgets[0]?.period;
  const unit = company?.budgetUnit ?? budgets[0]?.unit ?? "usd";
  const issued = scopeView(forecastBundle, "company");
  const asOf = String(issued?.publication?.information_cutoff ?? issued?.information_cutoff ?? period?.end ?? "").slice(0, 10);
  const priorities = useMemo(() => {
    if (!period || !asOf) return [];
    const summaries = teams.map(team => ({ team, summary: selectScopeSummary({ scope: { type: "team", id: team.id }, period, unit, datasetId: company?.id ?? "unknown", spending, budgets, forecastView: scopeView(forecastBundle, "team", team.id) }) }));
    const scheduledDrivers = issued ? rankForecastInsights({ view: issued, evidence: forecastEvidence }).map(insight => ({ insight, start: driverStart(insight.driver) })) : [];
    return buildOverviewPriorities({ summaries, context, proposals, teams, period, unit, asOf, scheduledDrivers }).filter(item => !hideBudget || item.kind !== "budget").slice(0, hideBudget ? 3 : 5);
  }, [period, asOf, teams, unit, company?.id, spending, budgets, forecastBundle, forecastEvidence, issued, context, proposals, hideBudget]);
  const contextKey = `${company?.id}:${period?.start}:${period?.end}:${issued?.run_id}`;
  const selected = selection?.contextKey === contextKey ? priorities.find(priority => priority.id === selection.id) : undefined;
  return <section className="rounded-xl border border-border bg-card p-5" aria-label={hideBudget ? "What’s changing" : "Needs attention"}>
    <h2 className="text-sm font-semibold">{hideBudget ? "What’s changing" : "Needs attention"}</h2>
    {priorities.length ? <ul className="mt-3 divide-y divide-border">{priorities.map(priority => <li key={priority.id}><button onClick={() => setSelection({ id: priority.id, contextKey })} className="flex w-full items-start gap-3 py-3.5 text-left hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"><span className="mt-0.5 rounded-md border border-border p-1.5 text-muted-foreground" aria-hidden>{priority.kind === "budget" ? <ArrowUpRight className="size-4" /> : priority.kind === "proposal" ? <FileCheck2 className="size-4" /> : <CalendarDays className="size-4" />}</span><span className="min-w-0 flex-1"><span className="block text-sm font-medium leading-snug">{priority.title}</span><span className="mt-1 block text-xs leading-relaxed text-muted-foreground">{priority.kind === "budget" ? `${chartMoney(priority.amount, unit)} above allocation · ${chartDate(priority.period.start)}–${chartDate(priority.period.end)}` : priority.kind === "context" ? `${priority.sources[0].scope === "company" ? "Company" : priority.sources[0].teamIds.map(id => teams.find(team => team.id === id)?.name).filter(Boolean).join(", ")} · starts ${chartDate(priority.sources[0].effectiveFrom!)} · source context` : priority.description}</span></span><ChevronRight className="mt-1 size-4 shrink-0 text-muted-foreground" /></button></li>)}</ul> : <p className="py-5 text-sm text-muted-foreground">No matching budget exceptions or upcoming source-backed changes found.</p>}
    <Link href="/evidence?view=changes" className="mt-3 inline-block text-xs text-muted-foreground hover:text-foreground hover:underline">Explore forecast assumptions →</Link>
    <Sheet open={!!selected && selected.kind !== "driver"} onOpenChange={open => { if (!open) setSelection(undefined); }}><SheetContent side="right" className="w-full overflow-y-auto sm:max-w-lg"><SheetHeader className="pr-10"><SheetTitle>{selected?.title ?? "Priority"}</SheetTitle><SheetDescription>{selected ? selected.kind === "budget" ? `Selected period · ${chartDate(selected.period.start)}–${chartDate(selected.period.end)}` : selected.description : "Financial explanation"}</SheetDescription></SheetHeader>{selected && <PriorityExplanation priority={selected} onViewSource={setDocumentId} />}</SheetContent></Sheet>
    <DriverDetail insight={selected?.kind === "driver" ? selected.driverInsight : undefined} onClose={() => setSelection(undefined)} />
    <SourceSheet documentId={documentId} onClose={() => setDocumentId(undefined)} />
  </section>;
}

function PriorityExplanation({ priority, onViewSource }: { priority: OverviewPriority; onViewSource: (id: string) => void }) {
  return <div className="space-y-5 px-4 pb-6 text-sm">
    {priority.kind === "budget" && priority.summary && <><p>The published forecast exceeds this team’s allocation for the same period.</p><dl className="grid grid-cols-2 gap-4 rounded-lg border border-border p-4"><div><dt className="text-xs text-muted-foreground">Expected spend</dt><dd className="mt-1 text-xl tabular-nums">{chartMoney(priority.summary.issued.amount, priority.unit)}</dd></div><div><dt className="text-xs text-muted-foreground">Budget</dt><dd className="mt-1 text-xl tabular-nums">{chartMoney(priority.summary.allocation, priority.unit)}</dd></div></dl><p className="text-sm">Expected difference: <strong>{chartMoney(priority.amount, priority.unit)}</strong>. This is a forecast, not an additional charge or approved budget change.</p><Link href={`/teams/${priority.team?.id}`} className="inline-block rounded-md border border-border px-3 py-2 text-xs font-medium hover:bg-muted">Open {priority.team?.name}</Link><details className="border-t border-border pt-3 text-xs"><summary className="cursor-pointer text-muted-foreground">Calculation details</summary><p className="mt-3 break-words text-muted-foreground">Expected spend minus the matching allocation. Published forecast {priority.summary.issued.runId ?? "unavailable"}. Period {priority.summary.target.startDate} to {priority.summary.target.endDateExclusive} (end exclusive), {priority.summary.target.timezone}.</p></details></>}
    {priority.kind === "proposal" && <><p>Review each draft’s status before changing allocations.</p><ul className="space-y-3">{priority.proposals.map(proposal => <li key={proposal.id} className="rounded-lg border border-border p-3"><p className="font-medium">{proposal.kind === "add_budget" ? "Additional funding" : "Redistribution"} · {proposal.status}</p><p className="mt-1 text-xs text-muted-foreground">{proposal.rationale}</p></li>)}</ul><Link href="/decisions" className="inline-block rounded-md border border-border px-3 py-2 text-xs font-medium hover:bg-muted">Open decisions</Link></>}
    {priority.kind === "context" && <><p className="rounded-md border border-border p-3 text-xs text-muted-foreground">Source-backed context. No dollar impact or published forecast effect is inferred from this item.</p>{priority.sources.map(item => <div key={item.id}><h3 className="font-medium">{item.title}</h3><p className="mt-2 leading-relaxed text-muted-foreground">{item.summary}</p><p className="mt-2 text-xs text-muted-foreground">Effective {chartDate(item.effectiveFrom!)}{item.effectiveTo ? ` through ${chartDate(item.effectiveTo)}` : " onward"}</p>{item.uncertainty && <p className="mt-2 text-xs text-muted-foreground">Unresolved: {item.uncertainty}</p>}<details className="mt-3 border-t border-border pt-3 text-xs"><summary className="cursor-pointer text-muted-foreground">Sources ({item.sources.length})</summary><ul className="mt-3 space-y-3">{item.sources.map((source, index) => <li key={`${source.documentId}:${index}`}><p className="font-medium">{source.title}</p>{source.excerpt && <blockquote className="mt-1 text-muted-foreground">{source.excerpt}</blockquote>}<button className="mt-2 underline underline-offset-4" onClick={() => onViewSource(source.documentId)}>Open source</button></li>)}</ul></details></div>)}</>}
  </div>;
}
