"use client";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, SlidersHorizontal } from "lucide-react";
import { useAppStore } from "@/lib/store";
import type { DailyUsageQuery, DailyUsageResponse, UsageMetric, UsageScope } from "@/lib/contracts/usage";
import { fetchDailyUsage } from "@/lib/data/usage-client";
import { formatExactUsd, formatUsageValue, mockDailyUsage, normalizeUsageScope, summarizeUsage, usageDateOffset, usageDates } from "@/lib/usage-derive";
import { Button } from "@/components/ui/button";
import { displayCopy, displayReference } from "@/lib/display-copy";
import { TokenActivityCalendar } from "./token-activity-calendar";
import { DayDetail } from "./day-detail";
import { UsageTrend } from "./usage-trend";

const inputClass = "h-10 min-w-0 rounded-md border border-border bg-background px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-brand";
function validScope(value: string | null): UsageScope["type"] { return value === "team" || value === "person" || value === "shared" ? value : "company"; }
function validDate(value: string | null): string | undefined { return value && /^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(Date.parse(`${value}T00:00:00Z`)) ? value : undefined; }
const humanDate = (date: string) => new Date(`${date}T00:00:00Z`).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });

export function UsagePage() {
  const params = useSearchParams();
  const { loaded, company, teams, people, spendingHistory } = useAppStore();
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;
  const [scope, setScope] = useState<UsageScope>(normalizeUsageScope({ type: validScope(params.get("scope_type")), id: params.get("scope_id") ?? undefined }));
  const [metric, setMetric] = useState<UsageMetric>(params.get("metric") === "tokens" ? "tokens" : "spend");
  const [start, setStart] = useState(validDate(params.get("start_date")) ?? "");
  const [end, setEnd] = useState(() => { const date = validDate(params.get("end_date_exclusive")); return date ? usageDateOffset(date, -1) : ""; });
  const [provider, setProvider] = useState(params.get("provider") ?? "");
  const [model, setModel] = useState(params.get("model") ?? "");
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [response, setResponse] = useState<DailyUsageResponse | null>(null);
  const [loadedRequestKey, setLoadedRequestKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  const [automaticRange, setAutomaticRange] = useState(!params.has("start_date") && !params.has("end_date_exclusive"));
  const mockLastDay = useMemo(() => spendingHistory.reduce((latest, record) => record.date > latest ? record.date : latest, ""), [spendingHistory]);
  const today = new Date().toISOString().slice(0, 10);
  const defaultEnd = !apiUrl && mockLastDay ? mockLastDay : today;
  const startDate = start || usageDateOffset(defaultEnd, -90);
  const endDate = end || defaultEnd;
  const query = useMemo<DailyUsageQuery>(() => ({ scopeType: scope.type, scopeId: scope.id ?? undefined, startDate, endDateExclusive: usageDateOffset(endDate, 1), provider: provider || undefined, model: model || undefined }), [scope.type, scope.id, startDate, endDate, provider, model]);
  const requestKey = JSON.stringify([query, retry, mockLastDay, company?.id]);
  const loading = loadedRequestKey !== requestKey;
  const validation = useMemo(() => { try { usageDates(query.startDate, query.endDateExclusive); if ((query.scopeType === "team" || query.scopeType === "person") && !query.scopeId) return "Choose a team or person."; return null; } catch (error) { return error instanceof Error ? error.message : "Choose a valid date range."; } }, [query]);

  useEffect(() => {
    if ((!apiUrl && !loaded) || validation) return;
    const controller = new AbortController();
    let active = true;
    const request = apiUrl ? fetchDailyUsage(apiUrl, query, controller.signal) : Promise.resolve(mockDailyUsage(spendingHistory, query, { asOf: `${mockLastDay || today}T12:00:00Z`, datasetId: `synthetic:${company?.id ?? "demo"}` }));
    request.then(result => {
      if (!active) return;
      setResponse(result); setLoadedRequestKey(requestKey); setError(null);
      if (automaticRange && result.availableStartDate && result.availableStartDate > query.startDate && result.availableStartDate < query.endDateExclusive) setStart(result.availableStartDate);
    }).catch(error => { if (active && !controller.signal.aborted) { setError(error instanceof Error ? error.message : "Usage could not be loaded."); setLoadedRequestKey(requestKey); } });
    return () => { active = false; controller.abort(); };
  }, [apiUrl, loaded, query, spendingHistory, mockLastDay, today, company?.id, automaticRange, validation, requestKey]);

  const buckets = response?.buckets ?? [];
  const selectedBuckets = selectedDate ? buckets.filter(bucket => bucket.date === selectedDate) : buckets;
  const summary = useMemo(() => summarizeUsage(selectedBuckets), [selectedBuckets]);
  const missingDays = buckets.filter(bucket => bucket.coverage === "missing" || bucket.coverage === "unknown").length;
  const completeDays = buckets.filter(bucket => bucket.coverage === "complete").length;
  const providers = [...new Set(buckets.flatMap(bucket => bucket.breakdowns.map(row => row.provider).filter((value): value is string => Boolean(value))))].sort();
  const scopeName = scope.type === "team" ? teams.find(team => team.id === scope.id)?.name ?? "Team" : scope.type === "person" ? people.find(person => person.id === scope.id)?.name ?? "Person" : scope.type === "shared" ? "Shared & unassigned" : company?.name ?? "Company";
  const scopedValue = scope.type === "company" || scope.type === "shared" ? scope.type : `${scope.type}:${scope.id}`;
  const backHref = scope.type === "team" ? `/teams/${encodeURIComponent(scope.id ?? "")}` : scope.type === "person" ? (() => { const person = people.find(item => item.id === scope.id); return person ? `/teams/${encodeURIComponent(person.teamId)}/people/${encodeURIComponent(person.id)}` : "/teams"; })() : "/overview";
  function setDateRange(newStart: string, newEnd: string) { setStart(newStart); setEnd(newEnd); setAutomaticRange(false); setSelectedDate(null); }
  function shareQuery(next: DailyUsageQuery, nextMetric: UsageMetric) {
    const search = new URLSearchParams({ scope_type: next.scopeType, start_date: next.startDate, end_date_exclusive: next.endDateExclusive, metric: nextMetric });
    if (next.scopeId) search.set("scope_id", next.scopeId); if (next.provider) search.set("provider", next.provider); if (next.model) search.set("model", next.model);
    window.history.replaceState(null, "", `/usage?${search}`);
  }
  useEffect(() => { if (!validation && (apiUrl || loaded)) shareQuery(query, metric); }, [query, metric, validation, apiUrl, loaded]);

  return <div className="min-w-0 space-y-6">
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div><Link href={backHref} className="mb-3 inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"><ArrowLeft className="size-3.5" />Back to {scope.type === "company" || scope.type === "shared" ? "overview" : displayCopy(scopeName)}</Link><h1 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">Usage activity</h1></div>
      <div className="inline-flex rounded-lg border border-border bg-card p-1" role="group" aria-label="Usage metric">{(["spend", "tokens"] as const).map(value => <Button key={value} variant={metric === value ? "secondary" : "ghost"} aria-pressed={metric === value} onClick={() => setMetric(value)}>{value === "spend" ? "Spend" : "Tokens"}</Button>)}</div>
    </div>
    <section aria-label="Usage filters" className="flex flex-wrap items-end gap-3 rounded-xl border border-border bg-card p-4">
      <label className="grid min-w-0 flex-1 gap-1.5 text-xs text-muted-foreground sm:min-w-44"><span>Scope</span><select className={inputClass} value={scopedValue} onChange={event => { const [type, ...id] = event.target.value.split(":"); setScope(normalizeUsageScope({ type: validScope(type), id: id.length ? id.join(":") : undefined })); setSelectedDate(null); }}><option value="company">Company total</option><option value="shared">Shared & unassigned</option><optgroup label="Teams">{teams.filter(team => team.id !== "unattributed").map(team => <option key={team.id} value={`team:${team.id}`}>{displayCopy(team.name)}</option>)}</optgroup><optgroup label="People">{people.map(person => <option key={person.id} value={`person:${person.id}`}>{displayCopy(person.name)}</option>)}</optgroup></select></label>
      <label className="grid min-w-0 flex-1 gap-1.5 text-xs text-muted-foreground sm:max-w-44"><span>From · UTC</span><input type="date" value={startDate} className={inputClass} onChange={event => { if (event.target.value) setDateRange(event.target.value, endDate); }} /></label>
      <label className="grid min-w-0 flex-1 gap-1.5 text-xs text-muted-foreground sm:max-w-44"><span>Through · UTC</span><input type="date" value={endDate} className={inputClass} onChange={event => { if (event.target.value) setDateRange(startDate, event.target.value); }} /></label>
      <div className="flex flex-wrap gap-1" aria-label="Date presets">{[4,13].map(weeks => <Button key={weeks} variant="ghost" size="sm" onClick={() => setDateRange(usageDateOffset(defaultEnd, -(weeks * 7 - 1)), defaultEnd)}>{weeks} weeks</Button>)}</div>
    </section>
    <details className="rounded-lg border border-border px-4 py-3"><summary className="cursor-pointer text-sm text-muted-foreground"><SlidersHorizontal className="mr-2 inline size-4" />Provider & model filters</summary><div className="mt-4 grid gap-3 sm:grid-cols-2"><label className="grid gap-1.5 text-xs text-muted-foreground">Provider<select className={inputClass} value={provider} onChange={event => { setProvider(event.target.value); setSelectedDate(null); }}><option value="">All providers</option>{[...new Set([...providers, ...(provider ? [provider] : [])])].map(item => <option key={item} value={item}>{displayCopy(item, "Provider")}</option>)}</select></label><label className="grid gap-1.5 text-xs text-muted-foreground">Exact model name<input className={inputClass} value={model} placeholder="All models" onChange={event => { setModel(event.target.value); setSelectedDate(null); }} /></label></div></details>
    {validation && <p role="alert" className="rounded-lg border border-destructive/30 p-4 text-sm text-destructive">{validation}</p>}
    {error && !loading && <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-destructive/30 p-4 text-sm"><p>{displayCopy(error)}</p><Button variant="outline" onClick={() => setRetry(value => value + 1)}>Retry usage</Button></div>}
    {loading && !validation && <p role="status" className="text-sm text-muted-foreground">Loading daily usage…</p>}
    {response && !loading && !validation && !error && <>
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground"><p>{displayCopy(scopeName)} · {humanDate(response.startDate)}–{humanDate(usageDateOffset(response.endDateExclusive, -1))} · UTC</p><p>Usage · {missingDays ? `${missingDays} days without data` : completeDays === buckets.length ? "All displayed days complete" : "Source coverage incomplete"}</p></div>
      <div className="grid gap-3 sm:grid-cols-3"><div className="rounded-xl border border-border bg-card p-5"><p className="text-xs text-muted-foreground">{selectedDate ? "Selected day" : "Selected range"} spending</p><p className="mt-2 break-all font-mono text-2xl tracking-tight">{formatExactUsd(summary.recordedSpend)}</p><p className="mt-2 text-xs text-muted-foreground">Included usage excluded</p></div><div className="rounded-xl border border-border bg-card p-5"><p className="text-xs text-muted-foreground">Tokens</p><p className="mt-2 font-mono text-2xl tracking-tight">{formatUsageValue(summary.tokens.total, "tokens", { compact: true })}</p><p className="mt-2 text-xs text-muted-foreground">{summary.tokens.input !== null && summary.tokens.output !== null ? "Input + output" : "Category details unavailable"}</p></div><div className="rounded-xl border border-border bg-card p-5"><p className="text-xs text-muted-foreground">Daily detail</p><p className="mt-2 text-xl tracking-tight">{selectedDate ? humanDate(selectedDate) : `${buckets.length} days`}</p><p className="mt-2 text-xs text-muted-foreground">{summary.recordCount.toLocaleString()} source records{selectedDate ? " in selection" : " in range"}</p></div></div>
      <TokenActivityCalendar buckets={buckets} metric={metric} selectedDate={selectedDate} onSelect={setSelectedDate} />
      <UsageTrend buckets={buckets} metric={metric} selectedDate={selectedDate} onSelect={setSelectedDate} />
      <DayDetail buckets={buckets} selectedDate={selectedDate} metric={metric} synthetic={response.synthetic} />
      <details className="rounded-lg border border-border px-4 py-3 text-xs text-muted-foreground"><summary className="cursor-pointer">Data coverage & sources</summary><div className="mt-3 space-y-2">{response.notes.map(note => <p key={note}>{displayCopy(note)}</p>)}<p>Last updated {new Date(response.asOf).toLocaleString("en-US", { timeZone: "UTC" })} UTC.</p>{response.sourceCoverage.map((source,index) => <p key={`${source.sourceKind}:${source.sourceAccount}:${index}`}>{displayCopy(displayReference(source.sourceKind, "Usage source"))}{source.sourceAccount ? ` · ${displayCopy(displayReference(source.sourceAccount, "Account"))}` : ""}: {source.recordCount.toLocaleString()} records · {source.coverage}</p>)}</div></details>
    </>}
  </div>;
}
