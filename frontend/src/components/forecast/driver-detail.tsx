"use client";
import { displayCopy, displayReference, displaySourceText, safeDisplayMetadata } from "@/lib/display-copy";

import Link from "next/link";
import { ExternalLink, MessageSquare, CalendarDays } from "lucide-react";
import type { ForecastDriver } from "@/lib/contracts";
import { driverQuestion, type DriverInsight } from "@/lib/driver-insights";
import { useAppStore } from "@/lib/store";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";

export function effectAmount(value: number | null | undefined, unit: string, signed = false): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "Unavailable";
  const options: Intl.NumberFormatOptions = { maximumFractionDigits: 2, ...(signed ? { signDisplay: "exceptZero" } : {}) };
  return unit.toLowerCase() === "usd"
    ? new Intl.NumberFormat("en-US", { ...options, style: "currency", currency: "USD" }).format(value)
    : `${new Intl.NumberFormat("en-US", options).format(value)} ${unit.toUpperCase()}`;
}

export function insightDates(start?: string | null, end?: string | null): string {
  const date = (value: string) => {
    const instant = new Date(value.length === 10 ? `${value}T00:00:00Z` : value);
    return Number.isNaN(instant.getTime()) ? displayCopy(value) : new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", timeZone: "UTC" }).format(instant);
  };
  return start ? `${date(start)}${end ? ` – ${date(end)} (end exclusive)` : " onward"}` : "Effective dates not supplied";
}

const citationText = (value: unknown): string | undefined => typeof value === "string" && value.trim() ? value : undefined;
function sourceLink(value: unknown): string | undefined {
  if (typeof value !== "string") return undefined;
  try { const url = new URL(value); return ["https:", "http:"].includes(url.protocol) ? url.href : undefined; } catch { return undefined; }
}

export function DriverDetail({ insight, onClose, onEditDriver }: {
  insight?: DriverInsight;
  onClose: () => void;
  onEditDriver?: (driver: ForecastDriver) => void;
}) {
  const askForecastAssistant = useAppStore(state => state.askForecastAssistant);
  const edit = () => { if (insight && onEditDriver) { onEditDriver(insight.driver); onClose(); } };
  const question = () => { if (insight) { const draft = driverQuestion(insight); askForecastAssistant(displayCopy(draft.prompt), draft.context); onClose(); } };
  const planningQuery = insight ? new URLSearchParams({ driver: insight.driver.id, run: insight.runId, scope_type: insight.scope.type, ...(insight.scope.id ? { scope_id: insight.scope.id } : {}) }).toString() : "";

  return <Sheet open={!!insight} onOpenChange={open => { if (!open) onClose(); }}>
    <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-lg">
      <SheetHeader className="pr-10">
        <SheetTitle>{displayCopy(insight?.title, "Forecast assumption")}</SheetTitle>
        <SheetDescription>{insight ? `${displayCopy(insight.scope.name ?? insight.scope.type)} · conditional quarter · ${insightDates(insight.horizon.start, insight.horizon.end)}` : "Source and forecast comparison"}</SheetDescription>
      </SheetHeader>
      {insight && <div className="space-y-6 px-4 pb-6 text-sm">
        <div className="rounded-xl border border-border p-4">
          <p className="text-xs text-muted-foreground">Modeled quarter difference</p>
          <p className="mt-1 text-2xl font-semibold tabular-nums">{effectAmount(insight.delta, insight.target.unit, true)}</p>
          <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{displayCopy(insight.reason)}</p>
          {insight.effect && <dl className="mt-4 grid grid-cols-2 gap-4 border-t border-border pt-3 text-xs">
            <div><dt className="text-muted-foreground">With this assumption</dt><dd className="mt-1 font-medium tabular-nums">{effectAmount(insight.effect.with_base, insight.target.unit)}</dd></div>
            <div><dt className="text-muted-foreground">Without this assumption</dt><dd className="mt-1 font-medium tabular-nums">{effectAmount(insight.effect.without_base, insight.target.unit)}</dd></div>
          </dl>}
        </div>
        {insight.effect && <p className="text-xs leading-relaxed text-muted-foreground">{displayCopy(insight.effect.qualification, "The model compares the issued assumptions with the same forecast omitting this one.")} These comparisons can interact; they are not additive explanations, proven causal effects, or realized savings.</p>}

        <div className="space-y-2">
          <h3 className="text-xs font-medium">Timing and scope</h3>
          <p className="text-xs text-muted-foreground">{insightDates(insight.driver.effective_from, insight.driver.effective_to)} · UTC</p>
          <p className="text-xs text-muted-foreground">{insight.status === "unknown_scope" ? "Applicability to this team or person has not been established." : `Selected forecast: ${displayCopy(insight.scope.name ?? insight.scope.type)}.`}</p>
        </div>

        <div className="space-y-3">
          <h3 className="text-xs font-medium">Source passages</h3>
          {insight.driver.citations?.length ? insight.driver.citations.map((citation, index) => {
            const href = sourceLink(citation.url ?? citation.source_url);
            return <blockquote key={index} className="space-y-2 border-l-2 border-primary/30 pl-3">
              <p className="text-sm leading-relaxed">{displaySourceText(citationText(citation.excerpt) ?? citationText(citation.quote) ?? citationText(citation.text), "No passage supplied.")}</p>
              <footer className="text-[11px] text-muted-foreground">
                <span>{displayCopy(citationText(citation.title), "Source")}</span>
                {citation.locator !== undefined && <span> · {displayCopy(String(citation.locator))}</span>}
                {href && <a href={href} target="_blank" rel="noopener noreferrer" className="ml-2 inline-flex items-center gap-1 underline underline-offset-2">Open source <ExternalLink className="size-3" aria-hidden="true" /></a>}
              </footer>
            </blockquote>;
          }) : <p className="text-xs text-muted-foreground">A cited source passage was not supplied for this assumption.</p>}
          <p className="text-[11px] text-muted-foreground">Source revision {displayReference(String(insight.driver.source_revision ?? "not supplied"), "loaded revision")}</p>
        </div>

        <div className="flex flex-wrap gap-2">
          {insight.inSnapshot && <Button size="sm" variant="outline" onClick={question}><MessageSquare className="size-3" /> Ask about this assumption</Button>}
          {insight.inSnapshot && (insight.status === "modeled" || insight.status === "included") && (onEditDriver
            ? <Button size="sm" variant="outline" onClick={edit}><CalendarDays className="size-3" /> Try a scenario</Button>
            : <Link href={`/planning?${planningQuery}`} onClick={onClose} className="inline-flex items-center gap-2 rounded-md border border-border px-3 py-2 text-xs font-medium hover:bg-muted"><CalendarDays className="size-3" /> Try a scenario</Link>)}
        </div>
        {!insight.inSnapshot && <p className="text-xs text-muted-foreground">This source is outside the issued snapshot. It has no numerical effect in this forecast.</p>}
        <details className="border-t border-border pt-3 text-xs">
          <summary className="cursor-pointer text-muted-foreground">Assumptions and calculation record</summary>
          <dl className="mt-3 space-y-2">
            <div><dt className="text-muted-foreground">Source identifier</dt><dd className="break-all">{displayReference(insight.driver.source_id, "Source record")}</dd></div>
            <div><dt className="text-muted-foreground">Issued run</dt><dd className="break-all">{displayReference(insight.runId, "Published forecast")}</dd></div>
            <div><dt className="text-muted-foreground">Comparison period (end exclusive)</dt><dd>{insight.horizon.start ?? "Unknown"} → {insight.horizon.end ?? "Unknown"}</dd></div>
            {Object.entries(safeDisplayMetadata(insight.driver.parameters ?? {}) as Record<string, unknown>).map(([key, value]) => <div key={key}><dt className="text-muted-foreground">{displayCopy(key.replaceAll("_", " "))}</dt><dd className="break-words">{typeof value === "object" ? JSON.stringify(value) : String(value)}</dd></div>)}
          </dl>
          <pre className="mt-3 max-h-72 overflow-auto whitespace-pre-wrap rounded-lg bg-muted/40 p-3 text-[10px]">{JSON.stringify(insight.effect ? { available: insight.effect.available, with_assumption: insight.effect.with_base, without_assumption: insight.effect.without_base, difference: insight.effect.base_delta, unit: insight.target.unit, daily: insight.effect.daily?.map(({ start, end, with_base, without_base, base_delta }) => ({ start, end, with_base, without_base, base_delta })), weekly: insight.effect.weekly?.map(({ start, end, with_base, without_base, base_delta }) => ({ start, end, with_base, without_base, base_delta })) } : { available: false, reason: "No matching issued comparison for this run, scope and quarter." }, null, 2)}</pre>
        </details>
      </div>}
    </SheetContent>
  </Sheet>;
}
