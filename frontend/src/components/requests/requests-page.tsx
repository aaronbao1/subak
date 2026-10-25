"use client";
import { displaySourceText } from "@/lib/display-copy";
import { useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Plus, Search } from "lucide-react";
import { useAppStore } from "@/lib/store";
import { Button } from "@/components/ui/button";
import { PageTitle } from "@/components/shared/stat-tile";
import { RequestInbox } from "./request-inbox";
import { RequestDialogs } from "./request-dialogs";
import { isOpenRequest, requestMatchesPeriod } from "./request-list-derive";

const selectClass = "h-9 rounded-md border border-border bg-card px-3 text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring";
export function RequestsPage() {
  const { company, teams, requests, requestState, requestError, loadRequests } = useAppStore();
  const [adding, setAdding] = useState(false);
  const router = useRouter(), pathname = usePathname(), params = useSearchParams();
  const status = params.get("status") ?? "open", query = params.get("q") ?? "", teamId = params.get("team") ?? "", period = params.get("period") ?? "all";
  const selectedId = params.get("request");
  useEffect(() => { if (requestState === "idle") void loadRequests(); }, [requestState, loadRequests]);
  const setParam = (key: string, value: string) => { const next = new URLSearchParams(params.toString()); if (value) next.set(key, value); else next.delete(key); router.replace(`${pathname}${next.size ? `?${next}` : ""}`, { scroll: false }); };
  const filtered = useMemo(() => requests.filter(request => (status === "all" || status === "open" && isOpenRequest(request) || status === "approved" && request.status === "approved_applied" || status === "rejected" && request.status === "rejected") && (!teamId || request.teamId === teamId) && (period !== "current" || company?.currentPeriod && requestMatchesPeriod(request, company.currentPeriod)) && (!query.trim() || `${request.title} ${request.projectName ?? ""} ${request.narrative} ${teams.find(team => team.id === request.teamId)?.name ?? ""}`.toLowerCase().includes(query.trim().toLowerCase()))).sort((a, b) => b.source.submittedAt.localeCompare(a.source.submittedAt)), [requests, status, teamId, period, company, query, teams]);
  return <div className="min-w-0 space-y-5">
    <PageTitle title="Team requests" description="Consider new work against the budget, then prepare an allocation for review." actions={<Button onClick={() => setAdding(true)}><Plus className="size-4" />Add team update</Button>} />
    <div className="flex flex-wrap items-center gap-3 rounded-xl border border-border bg-card p-4">
      <label className="flex min-w-52 flex-1 items-center gap-2 rounded-md border border-border px-3"><Search className="size-4 text-muted-foreground" /><input aria-label="Search team requests" placeholder="Search requests or projects" value={query} onChange={event => setParam("q", event.target.value)} className="h-9 w-full bg-transparent text-sm outline-none" /></label>
      <select aria-label="Request status" value={status} onChange={event => setParam("status", event.target.value)} className={selectClass}><option value="open">Open requests</option><option value="all">All statuses</option><option value="approved">Approved and applied</option><option value="rejected">Rejected</option></select>
      <select aria-label="Request team" value={teamId} onChange={event => setParam("team", event.target.value)} className={selectClass}><option value="">All teams</option>{teams.filter(team => team.id !== "unattributed").map(team => <option key={team.id} value={team.id}>{displaySourceText(team.name, "Team")}</option>)}</select>
      <select aria-label="Request period" value={period} onChange={event => setParam("period", event.target.value)} className={selectClass}><option value="all">All periods</option><option value="current">Current period</option></select>
    </div>
    {requestError && <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-warning/30 p-4 text-sm"><p>Requests could not refresh. Previously loaded requests remain available.</p><Button size="sm" variant="outline" onClick={() => void loadRequests()}>Try again</Button></div>}
    <section className="overflow-hidden rounded-xl border border-border bg-card" aria-label="Request inbox"><header className="border-b border-border px-5 py-3 text-xs text-muted-foreground">{filtered.length} {filtered.length === 1 ? "request" : "requests"}</header>{requestState === "loading" && !requests.length ? <p className="p-8 text-sm text-muted-foreground">Loading requests…</p> : <RequestInbox requests={filtered} teams={teams} onSelect={request => setParam("request", request.id)} />}</section>
    <RequestDialogs request={requests.find(request => request.id === selectedId)} onCloseRequest={() => setParam("request", "")} adding={adding} onCloseAdd={() => setAdding(false)} onSaved={request => setParam("request", request.id)} />
  </div>;
}
