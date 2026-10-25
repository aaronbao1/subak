"use client";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Plus } from "lucide-react";
import { useAppStore } from "@/lib/store";
import { Button } from "@/components/ui/button";
import { RequestInbox } from "./request-inbox";
import { RequestDialogs } from "./request-dialogs";
import { pendingRequestSummary, requestMoney } from "./request-list-derive";

/** Compact, current-period request consideration without treating a submitted amount as approved funding. */
export function BudgetRequestsOverview() {
  const { company, teams, requests, requestState, requestError, loadRequests } = useAppStore();
  const [selectedId, setSelectedId] = useState<string>();
  const [adding, setAdding] = useState(false);
  useEffect(() => { if (requestState === "idle") void loadRequests(); }, [requestState, loadRequests]);
  const summary = useMemo(() => pendingRequestSummary(requests, company?.currentPeriod), [requests, company?.currentPeriod]);
  const hasData = requestState === "ready" || requests.length > 0;
  const allAmountsUnknown = summary.matching.length > 0 && summary.unknownCount === summary.matching.length;
  const visible = [...summary.matching].sort((a, b) => b.source.submittedAt.localeCompare(a.source.submittedAt)).slice(0, 3);
  return <section aria-label="Team requests" className="min-w-0 rounded-xl border border-border bg-card">
    <header className="flex flex-wrap items-start justify-between gap-3 px-5 py-4"><div><h2 className="text-base font-medium">Team requests</h2><p className="mt-1 text-xs text-muted-foreground">Requests and project updates</p></div><Button variant="outline" size="sm" onClick={() => setAdding(true)}><Plus className="size-3.5" />Add team update</Button></header>
    <dl className="mx-5 mb-3 grid grid-cols-2 gap-4 border-y border-border py-3"><div><dt className="text-xs text-muted-foreground">Open this period</dt><dd className="mt-1 text-2xl font-medium tabular-nums">{hasData ? summary.matching.length : "—"}</dd></div><div><dt className="text-xs text-muted-foreground">Still requested</dt><dd className={`mt-1 font-medium ${allAmountsUnknown ? "text-base" : "text-2xl tabular-nums"}`}>{!hasData ? "—" : allAmountsUnknown ? "Not specified" : summary.matching.length ? requestMoney(summary.total) : "$0"}</dd>{summary.unknownCount > 0 && <dd className="mt-1 text-[11px] text-muted-foreground">{summary.unknownCount} without an amount</dd>}</div></dl>
    {requestError && <p role="alert" className="mx-5 mb-3 flex flex-wrap gap-2 text-xs text-warning">Requests could not refresh.<button onClick={() => void loadRequests()} className="underline underline-offset-4">Try again</button></p>}
    {requestState === "loading" && !requests.length ? <p className="px-5 py-8 text-sm text-muted-foreground">Loading requests…</p> : visible.length ? <RequestInbox requests={visible} teams={teams} onSelect={request => setSelectedId(request.id)} compact /> : <p className="px-5 py-5 text-sm text-muted-foreground">{requestError && !requests.length ? "Requests are unavailable." : "No open requests for this period."}</p>}
    <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-5 py-3"><span className="text-[11px] text-muted-foreground">Requests are assessed before any allocation changes.</span><Link href="/requests" className="text-xs font-medium hover:underline">View all{summary.open.length > summary.matching.length ? ` (${summary.open.length} open)` : ""} →</Link></footer>
    <RequestDialogs request={requests.find(request => request.id === selectedId)} onCloseRequest={() => setSelectedId(undefined)} adding={adding} onCloseAdd={() => setAdding(false)} onSaved={request => setSelectedId(request.id)} />
  </section>;
}
