"use client";
import { useState } from "react";
import Link from "next/link";
import { ArrowUpRight, ChevronRight, FileSearch, MessageSquare, X } from "lucide-react";
import type { Unit } from "@/lib/contracts";
import { Button } from "@/components/ui/button";
import { StatTile } from "@/components/shared/stat-tile";
import { COMPONENT_COLOR } from "@/components/shared/components";
import { COMPONENT_LABEL, StatusChip, teamStatus } from "@/components/team/labels";
import { formatAmount } from "@/lib/format";
import { cn } from "@/lib/utils";
import { dayLabel, type DailyPoint, type TeamSummary } from "./derive";
import { ProviderLogo } from "./provider-brand";
import { BarRow, StackedBar } from "./bars";
import { ComponentSwatch, EstimateLegend, isUnbilled, provenanceText } from "./cost-components";
import { BulletBar } from "@/components/team/viz";
import type { PersonSummary } from "@/components/person/derive";
import { SignalChip } from "@/components/person/signal-badges";

export interface TeamBreakdownPanelProps {
  summary: TeamSummary | null;
  unit: Unit;
  onClose: () => void;
  askAssistant: (text: string) => void;
  /** The team's people, so the panel can show who is moving the number. */
  people?: PersonSummary[];
}

export function TeamBreakdownPanel({ summary, unit, onClose, askAssistant, people = [] }: TeamBreakdownPanelProps) {
  if (!summary) return null;

  const { team, budget, forecast, spent, projected, low, high, byComponent, byModel, daily, dailyProjected } = summary;
  const apiTotal = byModel.reduce((s, m) => s + m.amount, 0);
  const allocated = budget?.allocated;
  const status = teamStatus(budget, forecast, spent);
  const over = typeof projected === "number" && typeof allocated === "number" ? projected > allocated : typeof allocated === "number" && spent > allocated;
  const days = [...daily, ...dailyProjected];
  const componentTotal = byComponent.reduce((s, c) => s + c.amount, 0);
  const componentMax = Math.max(0, ...byComponent.map((c) => c.amount));
  const money = (n: number) => formatAmount(n, unit);
  const compact = (n: number) => formatAmount(n, unit, { compact: true });
  const projectionTitle = forecast?.status === "available"
    ? `${forecast.basis === "full_period" ? "Whole period, including spend to date" : "Spend to date plus the remaining projection"}${typeof low === "number" && typeof high === "number" ? ` · range ${compact(low)} to ${compact(high)}` : ""}`
    : undefined;
  const sortedPeople = [...people].sort((a, b) => (b.projected ?? b.spent) - (a.projected ?? a.spent));
  const peopleMax = Math.max(0, ...people.map((p) => Math.max(p.spent, p.projected ?? 0)));

  return (
    <aside className="flex min-h-full min-w-0 flex-col divide-y divide-border" aria-label={`${team.name} breakdown`}>
      <header className="flex items-center gap-3 px-4 py-4">
        <div className="flex min-w-0 flex-1 items-center gap-2">
          <span className="size-2 shrink-0 rounded-full" style={{ background: team.color }} aria-hidden />
          <h2 className="truncate text-base font-medium" title={team.lead ? `Lead ${team.lead}` : undefined}>{team.name}</h2>
          <StatusChip status={status} />
        </div>
        <Button variant="ghost" size="icon-xs" onClick={onClose} aria-label="Clear selection" className="-mr-1.5 text-muted-foreground"><X strokeWidth={1.5} /></Button>
      </header>

      <div className="space-y-4 px-4 py-4">
        {/* The three figures count up when the panel opens and tick when another team is picked. */}
        <div className="grid grid-cols-3 gap-3">
          <StatTile size="compact" animate format={money} label="Allocation" value={typeof allocated === "number" ? allocated : "Not set"} muted={typeof allocated !== "number"} />
          <StatTile size="compact" animate format={money} label="Spent" value={spent} />
          <div title={projectionTitle}>
            <StatTile size="compact" animate format={money} label="Projection" value={typeof projected === "number" ? projected : "None"} muted={typeof projected !== "number"} />
          </div>
        </div>
        <BulletBar
          size="md" spent={spent} allocation={allocated} projected={projected} color={team.color} grow
          title={`Spent ${money(spent)}${typeof projected === "number" ? `, projected ${money(projected)}` : ""}${typeof low === "number" && typeof high === "number" ? ` (range ${compact(low)} to ${compact(high)})` : ""}${typeof allocated === "number" ? ` of ${money(allocated)} allocated` : ", no allocation"}`}
        />
        {forecast?.status === "unavailable" && (
          <p className="rounded-md border border-dashed border-border px-2.5 py-1.5 text-xs text-muted-foreground">
            {forecast.unavailableReason ?? "Projection unavailable."}
          </p>
        )}
        <DailyBars days={days} lastRecorded={daily.at(-1)?.date} color={team.color} unit={unit} />
      </div>

      <Section
        title="Cost components"
        hint={componentTotal > 0 ? (
          <span className="flex items-center gap-2">
            <StackedBar className="w-16" segments={byComponent.filter((c) => c.component !== "included_usage").map((c) => ({ key: c.component, value: c.amount, color: COMPONENT_COLOR[c.component] }))} />
            {compact(componentTotal)}
          </span>
        ) : undefined}
      >
        {byComponent.some((c) => c.amount > 0 && isUnbilled(c.provenances)) && <EstimateLegend className="mb-2" />}
        <ul>
          {byComponent.map((c, i) => {
            const informational = c.component === "included_usage";
            const noRecords = c.amount === 0 && c.provenances.length === 0;
            return (
              <BarRow
                key={c.component} index={i}
                label={<><ComponentSwatch component={c.component} />{COMPONENT_LABEL[c.component]}</>}
                value={c.amount} max={componentMax} color={COMPONENT_COLOR[c.component]} dashed={informational} muted={informational || noRecords}
                title={`${money(c.amount)} · ${provenanceText(c.provenances)}${informational ? " · informational, not billed" : ""}`}
                valueNode={noRecords ? "—" : <span className={cn(isUnbilled(c.provenances) && "underline decoration-dotted decoration-muted-foreground underline-offset-4")}>{compact(c.amount)}</span>}
              />
            );
          })}
        </ul>
      </Section>

      {byModel.length > 0 && (
        <Section title="By model" hint={compact(apiTotal)}>
          <ul>
            {byModel.map((m, i) => (
              <BarRow
                key={m.model} index={i}
                label={<><ProviderLogo provider={m.provider} className="size-3.5" /><span className="truncate">{m.model}</span></>}
                value={m.amount} max={byModel[0]?.amount ?? 1} color="var(--chart-5)"
                title={`${m.model} · ${money(m.amount)}${typeof m.tokens === "number" ? ` · ${formatAmount(m.tokens, "tokens")}` : ""}`}
                valueNode={compact(m.amount)}
              />
            ))}
          </ul>
        </Section>
      )}

      {people.length > 0 && (
        <Section title="People" hint={`${people.length}`} summaryTitle="Spent, then projected. The team projection is the sum of these.">
          <ul className="space-y-1">
            {sortedPeople.map((p) => (
              <li key={p.person.id} className="py-1 text-xs">
                <div className="grid grid-cols-[minmax(0,7rem)_minmax(0,1fr)_auto] items-center gap-3">
                  <Link href={`/teams/${team.id}/people/${p.person.id}`} className="min-w-0 truncate text-foreground/80 underline-offset-4 hover:text-foreground hover:underline">{p.person.name}</Link>
                  <PersonBar spent={p.spent} projected={p.projected} max={peopleMax} color={team.color} />
                  <span className="num shrink-0 text-right" title={`${money(p.spent)} spent${p.projected != null ? `, ${money(p.projected)} projected` : ""}`}>
                    {compact(p.spent)}
                    <span className="text-muted-foreground"> → {p.projected != null ? compact(p.projected) : "—"}</span>
                  </span>
                </div>
                {p.signals.length > 0 && <div className="mt-1"><SignalChip item={p.signals[0]} /></div>}
              </li>
            ))}
          </ul>
        </Section>
      )}

      <footer className="mt-auto flex flex-wrap gap-2 px-4 py-3">
        <Button variant="outline" size="sm" nativeButton={false} render={<Link href={`/teams/${team.id}`} />}>
          View team <ArrowUpRight strokeWidth={1.5} />
        </Button>
        <Button variant="ghost" size="sm" className="text-muted-foreground" nativeButton={false} render={<Link href={`/evidence?team=${encodeURIComponent(team.id)}`} />}>
          <FileSearch strokeWidth={1.5} /> Evidence
        </Button>
        <Button
          variant="ghost" size="sm" className="text-muted-foreground"
          onClick={() => askAssistant(`Why is ${team.name} tracking ${over ? "over" : "under"} its allocation?`)}
        >
          <MessageSquare strokeWidth={1.5} /> Ask assistant
        </Button>
      </footer>
    </aside>
  );
}

/** Day-by-day as small columns: recorded solid, partial lighter, projected dashed. Exact values on hover. */
function DailyBars({ days, lastRecorded, color, unit }: { days: DailyPoint[]; lastRecorded?: string; color: string; unit: Unit }) {
  const [showTable, setShowTable] = useState(false);
  if (days.length === 0) return <p className="text-xs text-muted-foreground">No daily records.</p>;
  const max = Math.max(...days.map((d) => d.amount));
  const hasPartial = days.some((d) => !d.projected && d.partial);
  const hasProjected = days.some((d) => d.projected);
  const noteFor = (d: DailyPoint) => (d.projected ? (d.date === lastRecorded ? "full day, projected" : "projected") : d.partial ? "recorded so far" : "recorded");
  return (
    <div>
      <div className="flex h-10 items-end gap-px" role="img" aria-label={`${days.length} days of spend`}>
        {days.map((d) => {
          const note = noteFor(d);
          return (
            <div
              key={`${d.date}-${d.projected ? "p" : "r"}`}
              title={`${dayLabel(d.date)} · ${formatAmount(d.amount, unit)} · ${note}`}
              className={cn("min-w-0 flex-1 rounded-t-[2px]", d.projected && "border border-b-0 border-dashed")}
              style={{
                height: `${max > 0 ? Math.max(4, (d.amount / max) * 100) : 4}%`,
                ...(d.projected ? { borderColor: color } : { background: color, opacity: d.partial ? 0.45 : 0.85 }),
              }}
            />
          );
        })}
      </div>
      <div className="num mt-1 flex justify-between text-[11px] text-muted-foreground">
        <span>{dayLabel(days[0].date)}</span>
        <span>{dayLabel(days[days.length - 1].date)}</span>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
        <span className="inline-flex items-center gap-1.5"><span aria-hidden className="size-2 rounded-[2px]" style={{ background: color, opacity: 0.85 }} />Recorded</span>
        {hasPartial && <span className="inline-flex items-center gap-1.5"><span aria-hidden className="size-2 rounded-[2px]" style={{ background: color, opacity: 0.45 }} />Partial</span>}
        {hasProjected && <span className="inline-flex items-center gap-1.5"><span aria-hidden className="size-2 rounded-[2px] border border-dashed" style={{ borderColor: color }} />Projected</span>}
        <button type="button" onClick={() => setShowTable((v) => !v)} aria-expanded={showTable} className="ml-auto rounded-sm transition-colors duration-300 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
          {showTable ? "Hide table" : "Show table"}
        </button>
      </div>
      {showTable && (
        <table className="mt-2 w-full text-xs">
          <thead className="text-left text-muted-foreground">
            <tr><th className="py-1 font-normal">Day</th><th className="py-1 text-right font-normal">Amount</th><th className="py-1 pl-3 text-right font-normal">Status</th></tr>
          </thead>
          <tbody className="num">
            {days.map((d) => (
              <tr key={`${d.date}-${d.projected ? "p" : "r"}`} className="border-t border-border">
                <td className="py-1">{dayLabel(d.date)}</td>
                <td className="py-1 text-right">{formatAmount(d.amount, unit)}</td>
                <td className="py-1 pl-3 text-right text-muted-foreground">{noteFor(d)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

/** Spent solid in the team color, the projection as a dashed extension, scaled to the largest person. */
function PersonBar({ spent, projected, max, color }: { spent: number; projected?: number; max: number; color: string }) {
  const w = (v: number) => `${max > 0 ? Math.max(0, Math.min(100, (v / max) * 100)) : 0}%`;
  return (
    <span className="relative h-1.5 w-full overflow-hidden rounded-sm bg-muted" aria-hidden>
      {typeof projected === "number" && projected > spent && (
        <span className="absolute inset-y-0 border border-dashed" style={{ left: w(spent), width: `calc(${w(projected)} - ${w(spent)})`, borderColor: color }} />
      )}
      <span className="animate-grow-x absolute inset-y-0 left-0" style={{ width: w(spent), background: color }} />
    </span>
  );
}

/** Collapsed by default: the headline figures answer the first question; details open on demand. One divider row, no nested card. */
function Section({ title, hint, summaryTitle, children }: { title: string; hint?: React.ReactNode; summaryTitle?: string; children: React.ReactNode }) {
  return (
    <details className="group">
      <summary title={summaryTitle} className="flex h-10 cursor-pointer list-none items-center gap-2 px-4 text-sm text-foreground transition-colors duration-300 hover:bg-popover [&::-webkit-details-marker]:hidden">
        <ChevronRight className="size-4 text-muted-foreground transition-transform duration-150 group-open:rotate-90" strokeWidth={1.5} />
        <span>{title}</span>
        {hint && <span className="num ml-auto text-xs text-muted-foreground">{hint}</span>}
      </summary>
      <div className="px-4 pb-4 pt-1">{children}</div>
    </details>
  );
}
