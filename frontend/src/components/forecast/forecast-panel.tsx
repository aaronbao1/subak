"use client";
import { displayCopy, displayReference } from "@/lib/display-copy";
import Link from "next/link";
import { MessageSquare, RefreshCw } from "lucide-react";
import { useAppStore } from "@/lib/store";
import { Button } from "@/components/ui/button";
import { forecastPrompt, scopeView } from "@/components/dashboard/forecast-derive";
import { SpendForecastChart } from "./spend-forecast-chart";
import { CalculationDetails } from "./calculation-details";
import { chartDate, chartMoney } from "./chart-data";
import { DriverOverview } from "./driver-overview";

const isRunning = (status?: string) => ["pending", "queued", "running"].includes(status ?? "");

/** A compact finance view of an immutable publication. Actuals, detailed sources and scenarios keep their own identities. */
export function ForecastPanel({ scopeType = "company", scopeId, showDrivers = true }: { scopeType?: "company" | "team" | "person"; scopeId?: string; showDrivers?: boolean }) {
  const { forecastBundle, forecastEvidence, forecastError, forecastRefresh, refreshForecast, askForecastAssistant } = useAppStore();
  const view = scopeView(forecastBundle, scopeType, scopeId);
  const refreshing = isRunning(forecastRefresh?.status);
  if (!view) return <section aria-label="Published forecast" className="rounded-xl border border-border bg-card p-5">
    <h2 className="text-base font-medium">Spending outlook</h2>
    <p className="mt-2 text-sm text-muted-foreground">{displayCopy(forecastError, "No forecast is available for this scope yet.")}</p>
    <Button size="sm" variant="outline" className="mt-4" disabled={refreshing} onClick={() => void refreshForecast()}><RefreshCw className="size-3.5" />{refreshing ? "Updating forecast…" : "Update forecast"}</Button>
    {scopeType === "company" && forecastEvidence.length > 0 && <details className="mt-4 border-t border-border pt-3 text-xs"><summary className="cursor-pointer text-muted-foreground">Evidence processing ({forecastEvidence.length})</summary><ul className="mt-3 space-y-3">{forecastEvidence.map((item, index) => <li key={item.id ?? index}><p>{displayReference(String(item.source_id ?? (item.envelope as Record<string, unknown> | undefined)?.source_id ?? item.id ?? ""), `Source ${index + 1}`)} · {displayCopy(String(item.status ?? item.queue_status ?? "received"))}</p>{typeof item.last_error === "string" && <p className="mt-1 text-destructive">{displayCopy(item.last_error)}</p>}</li>)}</ul></details>}
  </section>;
  const quarter = view.quarter_outlook;
  const end = typeof quarter?.end === "string" ? new Date(Date.parse(`${quarter.end.slice(0, 10)}T00:00:00Z`) - 86_400_000).toISOString().slice(0, 10) : undefined;
  const periodStart = typeof quarter?.start === "string" ? quarter.start : undefined;
  const hasOutlook = typeof quarter?.base === "number" && Number.isFinite(quarter.base);
  const incomplete = quarter?.complete === false || !hasOutlook;
  return <section aria-label="Published forecast" className="min-w-0 rounded-xl border border-border bg-card">
    <header className="flex flex-wrap items-start justify-between gap-4 border-b border-border px-5 py-4">
      <div><h2 className="text-base font-medium">Spending outlook</h2><p className="mt-1 text-xs text-muted-foreground">Published {chartDate(String(view.publication?.generated_at ?? view.generated_at ?? ""))}</p></div>
      <div className="text-right"><p className="text-xl font-medium tabular-nums">{chartMoney(quarter?.base, view.target.unit)}</p><p className="mt-1 text-xs text-muted-foreground">{incomplete && hasOutlook ? "Partial period total" : "Full-period total"}{periodStart && end ? ` · ${chartDate(periodStart)}–${chartDate(end)}` : end ? ` through ${chartDate(end)}` : ""}</p></div>
    </header>
    <div className="space-y-4 p-5">
      {incomplete && <p className="rounded-md border border-warning/30 px-3 py-2 text-xs text-warning">{hasOutlook ? "Partial outlook: this amount excludes unavailable inputs. Review the calculation details before planning against it." : "The complete outlook is unavailable. Supported published values remain visible below."}</p>}
      {forecastError && <p role="alert" className="text-xs text-destructive">{displayCopy(forecastError)}</p>}
      {refreshing && <p role="status" className="text-xs text-muted-foreground">Updating forecast… Your current published outlook remains visible.</p>}
      {forecastRefresh?.status === "failed" && <p role="alert" className="text-xs text-destructive">Forecast update failed. Your published outlook is unchanged.</p>}
      <SpendForecastChart key={`${view.run_id}:${view.scope.type}:${view.scope.id}`} view={view} />
      {showDrivers && <details className="border-t border-border pt-3"><summary className="cursor-pointer text-xs text-muted-foreground">What changes the outlook <span className="ml-1">({view.included_drivers.length} included changes)</span></summary><div className="mt-3"><DriverOverview view={view} evidence={forecastEvidence} compact /></div><Link href={`/evidence?view=changes${scopeType === "team" ? `&team=${encodeURIComponent(scopeId ?? "")}` : ""}`} className="mt-3 inline-block text-xs font-medium hover:underline">Explore all forecast changes →</Link></details>}
      <CalculationDetails view={view} bundle={forecastBundle} evidence={forecastEvidence} actions={<><Button size="sm" variant="outline" onClick={() => askForecastAssistant(forecastPrompt(view), { action: "explain", run_id: view.run_id, scope_type: view.scope.type, scope_id: view.scope.id })}><MessageSquare className="size-3.5" />Explain this outlook</Button><Button size="sm" variant="outline" disabled={refreshing} onClick={() => void refreshForecast()}><RefreshCw className="size-3.5" />Update forecast</Button></>} />
    </div>
  </section>;
}
