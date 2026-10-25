"use client";
import Link from "next/link";
import { ArrowUpRight, ChevronRight, MessageSquare, X } from "lucide-react";
import type { Unit } from "@/lib/contracts";
import { Button } from "@/components/ui/button";
import { formatAmount } from "@/lib/format";
import { cn } from "@/lib/utils";
import { COMPONENT_LABEL, PROVENANCE_LABEL, dayLabel, type TeamSummary } from "./derive";
import { STATUS_BADGE, STATUS_META, teamStatus } from "./status";
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

/** Component segments share one neutral hue; the label row carries identity. Included usage is informational. */
const SEGMENT_STYLE: Record<string, string> = {
  subscription: "bg-foreground/80",
  included_usage: "bg-foreground/10 border border-dashed border-foreground/40",
  extra_usage: "bg-foreground/55",
  api: "bg-foreground/30",
};

const BADGE = "inline-flex h-5 items-center rounded-md border border-border bg-popover px-1.5 text-[11px] text-muted-foreground whitespace-nowrap";

export function TeamBreakdownPanel({ summary, unit, onClose, askAssistant, people = [] }: TeamBreakdownPanelProps) {
  if (!summary) return null;

  const { team, budget, forecast, spent, projected, low, high, byComponent, daily, dailyProjected } = summary;
  const allocated = budget?.allocated;
  const status = teamStatus(allocated, projected, high);
  const over = typeof projected === "number" && typeof allocated === "number" ? projected > allocated : typeof allocated === "number" && spent > allocated;
  const days = [...daily, ...dailyProjected];
  const componentTotal = byComponent.reduce((s, c) => s + c.amount, 0);

  return (
    <aside className="flex min-h-full min-w-0 flex-col divide-y divide-border" aria-label={`${team.name} breakdown`}>
      <header className="flex items-start gap-3 px-4 py-4">
        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 items-center gap-2">
            <span className="size-2 shrink-0 rounded-full" style={{ background: team.color }} aria-hidden />
            <h2 className="truncate text-base font-medium">{team.name}</h2>
            <span className={cn(STATUS_BADGE, STATUS_META[status].className)}>{STATUS_META[status].label}</span>
          </div>
          {team.lead && <p className="mt-1 text-xs text-muted-foreground">Lead {team.lead}</p>}
        </div>
        <Button variant="ghost" size="icon-xs" onClick={onClose} aria-label="Clear selection" className="-mr-1.5 -mt-0.5 text-muted-foreground"><X strokeWidth={1.5} /></Button>
      </header>

      <div className="space-y-3 px-4 py-4">
        <dl className="grid grid-cols-3 gap-3">
          <Figure label="Allocation" value={typeof allocated === "number" ? formatAmount(allocated, unit) : "Not set"} muted={typeof allocated !== "number"} />
          <Figure label="Spent" value={formatAmount(spent, unit)} />
          <Figure
            label="Projection"
            value={typeof projected === "number" ? formatAmount(projected, unit) : "None"}
            muted={typeof projected !== "number"}
            sub={typeof low === "number" && typeof high === "number" ? `${formatAmount(low, unit, { compact: true })} to ${formatAmount(high, unit, { compact: true })}` : undefined}
          />
        </dl>
        {forecast?.status === "unavailable" && (
          <p className="rounded-md border border-dashed border-border px-2.5 py-1.5 text-xs text-muted-foreground">
            {forecast.unavailableReason ?? "Projection unavailable."}
          </p>
        )}
        {forecast?.status === "available" && forecast.origin === "placeholder" && (
          <p className="text-xs text-muted-foreground">Placeholder projection for the whole period, including spend to date.</p>
        )}
      </div>

      <Section title="Cost components" hint={componentTotal > 0 ? formatAmount(componentTotal, unit, { compact: true }) : undefined}>
        {componentTotal > 0 && (
          <div className="flex h-1.5 w-full gap-px overflow-hidden rounded-sm bg-muted" aria-hidden>
            {byComponent.filter((c) => c.amount > 0).map((c) => (
              <div key={c.component} className={cn("h-full", SEGMENT_STYLE[c.component])} style={{ width: `${(c.amount / componentTotal) * 100}%` }} />
            ))}
          </div>
        )}
        <ul className="divide-y divide-border text-xs">
          {byComponent.map((c) => (
            <li key={c.component} className="flex flex-wrap items-center justify-between gap-x-3 gap-y-0.5 py-2">
              <span className="flex items-center gap-1.5">
                <span className={cn("size-2 rounded-sm", SEGMENT_STYLE[c.component])} aria-hidden />
                {COMPONENT_LABEL[c.component]}
                {c.component === "included_usage" && <span className="text-[11px] text-muted-foreground">informational</span>}
              </span>
              <span className="flex items-center gap-1.5">
                {c.provenances.map((p) => (
                  <span key={p} className={BADGE}>{PROVENANCE_LABEL[p]}</span>
                ))}
                <span className={cn("num text-right", c.component === "included_usage" && "text-muted-foreground")}>
                  {c.amount > 0 || c.provenances.length ? formatAmount(c.amount, unit) : <span className="text-muted-foreground">No records</span>}
                </span>
              </span>
            </li>
          ))}
        </ul>
      </Section>

      {people.length > 0 && (
        <Section title="People" hint={`${people.length}`}>
          <ul className="divide-y divide-border text-xs">
            {[...people].sort((a, b) => (b.projected ?? b.spent) - (a.projected ?? a.spent)).map((p) => (
              <li key={p.person.id} className="py-2">
                <div className="flex items-center justify-between gap-3">
                  <Link href={`/teams/${team.id}/people/${p.person.id}`} className="min-w-0 truncate underline-offset-4 hover:underline">{p.person.name}</Link>
                  <span className="num shrink-0 text-right">
                    {formatAmount(p.spent, unit, { compact: true })}
                    <span className="text-muted-foreground"> → {p.projected != null ? formatAmount(p.projected, unit, { compact: true }) : "—"}</span>
                  </span>
                </div>
                {p.signals.length > 0 && <div className="mt-1 flex flex-wrap gap-1">{p.signals.slice(0, 1).map((s) => <SignalChip key={s.id} item={s} />)}</div>}
              </li>
            ))}
          </ul>
          <p className="text-[11px] text-muted-foreground">Spent → projected. The team projection is the sum of these.</p>
        </Section>
      )}

      <Section title="Day by day" hint={days.length ? `${days.length} days` : undefined}>
        {days.length === 0 ? (
          <p className="text-xs text-muted-foreground">No daily records.</p>
        ) : (
          <table className="w-full text-xs">
            <tbody className="divide-y divide-border">
              {days.map((d) => (
                <tr key={`${d.date}-${d.projected ? "p" : "r"}`} className={cn(d.projected && "text-muted-foreground")}>
                  <td className="num py-2 text-muted-foreground">{dayLabel(d.date)}</td>
                  <td className="py-2 text-right text-[11px] text-muted-foreground">{d.projected ? (d.date === daily.at(-1)?.date ? "full day, projected" : "projected") : d.partial ? "recorded so far" : ""}</td>
                  <td className="num py-2 text-right">{formatAmount(d.amount, unit, { compact: true })}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {dailyProjected.length > 0 && forecast?.origin === "placeholder" && (
          <p className="text-[11px] text-muted-foreground">Projected days are placeholder projections.</p>
        )}
      </Section>

      <footer className="mt-auto flex flex-wrap gap-2 px-4 py-3">
        <Button variant="outline" size="sm" nativeButton={false} render={<Link href={`/teams/${team.id}`} />}>
          View team <ArrowUpRight strokeWidth={1.5} />
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

/** Collapsed by default: the headline figures answer the first question; details open on demand. One divider row, no nested card. */
function Section({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <details className="group">
      <summary className="flex h-10 cursor-pointer list-none items-center gap-2 px-4 text-sm text-foreground transition-colors duration-300 hover:bg-popover [&::-webkit-details-marker]:hidden">
        <ChevronRight className="size-4 text-muted-foreground transition-transform duration-150 group-open:rotate-90" strokeWidth={1.5} />
        <span>{title}</span>
        {hint && <span className="num ml-auto text-xs text-muted-foreground">{hint}</span>}
      </summary>
      <div className="space-y-2 px-4 pb-4 pt-1">{children}</div>
    </details>
  );
}

function Figure({ label, value, sub, muted }: { label: string; value: string; sub?: string; muted?: boolean }) {
  return (
    <div className="min-w-0">
      <dt className="eyebrow truncate">{label}</dt>
      <dd className={cn("num mt-2 truncate text-xl leading-none", muted ? "text-muted-foreground" : "font-medium text-foreground")}>{value}</dd>
      {sub && <dd className="num mt-1.5 truncate text-xs text-muted-foreground">{sub}</dd>}
    </div>
  );
}
