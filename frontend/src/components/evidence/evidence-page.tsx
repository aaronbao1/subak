"use client";
import { displaySourceText } from "@/lib/display-copy";
import { useCallback, useMemo } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Search } from "lucide-react";
import { useAppStore } from "@/lib/store";
import { PageTitle } from "@/components/shared/stat-tile";
import { applyFilters, buildRows, indexAdjustments, isDefaultFilters, parseFilters, serializeFilters, type EvidenceFilters } from "./derive";
import { FilterRow } from "./filter-row";
import { EvidenceFeed } from "./evidence-feed";
import { EvidenceSkeleton } from "./skeleton";
import { SourceLibrary } from "./source-library";
import { DriverOverview } from "@/components/forecast/driver-overview";
import { scopeView } from "@/components/dashboard/forecast-derive";

/** Evidence starts with finding sources. Forecast explanations are a focused secondary view. */
export function EvidencePage() {
  const { loaded, company, teams, people, context, forecasts, personForecasts, budgets, forecastBundle, forecastEvidence } = useAppStore();
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const filters = useMemo(() => parseFilters(params, teams), [params, teams]);
  const search = params.get("q") ?? "";
  const selectedView = params.get("view");
  const tab = selectedView === "changes" ? "changes" : selectedView === "assessments" ? "assessments" : "sources";
  const visibleCount = Math.max(8, Number(params.get("limit")) || 8);
  const setParam = useCallback((key: string, value: string) => {
    const next = new URLSearchParams(params.toString());
    if (value) next.set(key, value); else next.delete(key);
    if (key !== "limit") next.delete("limit");
    router.replace(`${pathname}${next.size ? `?${next}` : ""}`, { scroll: false });
  }, [router, pathname, params]);
  const setFilters = useCallback((next: EvidenceFilters) => {
    const query = new URLSearchParams(serializeFilters(next));
    if (search) query.set("q", search);
    if (tab !== "sources") query.set("view", tab);
    router.replace(`${pathname}${query.size ? `?${query}` : ""}`, { scroll: false });
  }, [router, pathname, search, tab]);
  const clearFilters = useCallback(() => router.replace(`${pathname}${tab === "sources" ? "" : `?view=${tab}`}`, { scroll: false }), [router, pathname, tab]);
  const unit = company?.budgetUnit ?? budgets[0]?.unit ?? "usd";
  const adjustments = useMemo(() => indexAdjustments(forecasts, personForecasts), [forecasts, personForecasts]);
  const rows = useMemo(() => buildRows(context, teams, people, adjustments), [context, teams, people, adjustments]);
  const filtered = useMemo(() => applyFilters(rows, filters).filter(row => !search.trim() || `${row.item.title} ${row.item.summary} ${row.teams.map(team => team.name).join(" ")}`.toLowerCase().includes(search.trim().toLowerCase())), [rows, filters, search]);
  const view = filters.team ? scopeView(forecastBundle, "team", filters.team) : scopeView(forecastBundle, "company");
  if (!loaded) return <EvidenceSkeleton />;
  return <div className="min-w-0 space-y-5">
    <PageTitle title="Evidence" description="Find the plans, messages and sources behind spending decisions." />
    <div className="flex flex-wrap gap-x-5 gap-y-2 border-b border-border" role="group" aria-label="Evidence views">{[{ key: "sources", label: "Sources" }, { key: "assessments", label: "Assessments" }, { key: "changes", label: "Forecast changes" }].map(item => <button key={item.key} aria-pressed={tab === item.key} onClick={() => setParam("view", item.key === "sources" ? "" : item.key)} className={`border-b-2 pb-3 text-sm ${tab === item.key ? "border-primary font-medium text-foreground" : "border-transparent text-muted-foreground hover:text-foreground"}`}>{item.label}</button>)}</div>
    {tab === "sources" ? <SourceLibrary teams={teams} search={search} onSearch={value => setParam("q", value)} teamId={params.get("team") || undefined} onTeamChange={value => setParam("team", value ?? "")} /> : tab === "assessments" ? <>
      <div className="rounded-xl border border-border bg-card p-4">
        <div className="flex flex-wrap items-center gap-3"><label className="flex min-w-56 flex-1 items-center gap-2 rounded-md border border-border bg-background px-3"><Search className="size-4 text-muted-foreground" /><input aria-label="Search assessments" placeholder="Search assessed plans or teams" value={search} onChange={event => setParam("q", event.target.value)} className="h-9 w-full bg-transparent text-sm outline-none" /></label><span className="text-xs text-muted-foreground">{filtered.length} assessments</span></div>
        <details className="mt-3" open={!isDefaultFilters(filters)}><summary className="cursor-pointer text-xs text-muted-foreground">Filter by team, scope and category</summary><div className="mt-4"><FilterRow filters={filters} teams={teams} onChange={setFilters} shown={filtered.length} total={rows.length} /></div></details>
      </div>
      {rows.length ? <EvidenceFeed rows={filtered.slice(0, visibleCount)} unit={unit} mounted enterAt={0} onClearFilters={clearFilters} filtersActive={!isDefaultFilters(filters) || !!search} /> : <p className="rounded-xl border border-border bg-card p-5 text-sm text-muted-foreground">No source assessments yet. Received documents are available in Sources.</p>}
      {filtered.length > visibleCount && <button onClick={() => setParam("limit", String(visibleCount + 8))} className="w-full rounded-lg border border-border py-3 text-sm hover:bg-muted">Show 8 more assessments <span className="ml-1 text-muted-foreground">({filtered.length - visibleCount} remaining)</span></button>}
    </> : <>
      <label className="flex items-center gap-3 text-sm">Scope<select aria-label="Forecast changes scope" value={filters.team ?? ""} onChange={event => setFilters({ ...filters, team: event.target.value || undefined })} className="rounded-md border border-border bg-card p-2"><option value="">Company</option>{teams.map(team => <option key={team.id} value={team.id}>{displaySourceText(team.name, "Team")}</option>)}</select></label>
      {view ? <DriverOverview view={view} evidence={forecastEvidence} /> : <p className="rounded-xl border border-border p-5 text-sm text-muted-foreground">No published forecast is available for this scope.</p>}
    </>}
  </div>;
}
