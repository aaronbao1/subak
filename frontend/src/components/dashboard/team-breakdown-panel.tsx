"use client";
import Link from "next/link";
import { ArrowUpRight, MessageSquare, MousePointerClick, X } from "lucide-react";
import type { Unit } from "@/lib/contracts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatAmount } from "@/lib/format";
import { cn } from "@/lib/utils";
import { COMPONENT_LABEL, PROVENANCE_LABEL, dateLabel, type TeamSummary } from "./derive";
import { STATUS_META, teamStatus } from "./status";

export interface TeamBreakdownPanelProps {
  summary: TeamSummary | null;
  unit: Unit;
  onClose: () => void;
  askAssistant: (text: string) => void;
}

/** Component segments share one neutral hue; the label row carries identity. Included usage is informational. */
const SEGMENT_STYLE: Record<string, string> = {
  subscription: "bg-foreground/80",
  included_usage: "bg-foreground/15 border border-dashed border-foreground/40",
  extra_usage: "bg-foreground/55",
  api: "bg-foreground/35",
};

export function TeamBreakdownPanel({ summary, unit, onClose, askAssistant }: TeamBreakdownPanelProps) {
  if (!summary) {
    return (
      <Card className="min-h-48 lg:min-h-full">
        <CardContent className="flex h-full flex-1 flex-col items-center justify-center gap-2 py-10 text-center text-sm text-muted-foreground">
          <MousePointerClick className="size-5" />
          Click a line to see a team&apos;s breakdown
        </CardContent>
      </Card>
    );
  }

  const { team, budget, forecast, spent, projected, low, high, byComponent, daily } = summary;
  const allocated = budget?.allocated;
  const status = teamStatus(allocated, projected);
  const over = typeof projected === "number" && typeof allocated === "number" ? projected > allocated : typeof allocated === "number" && spent > allocated;
  const last7 = daily.slice(-7).reverse();
  const componentTotal = byComponent.reduce((s, c) => s + c.amount, 0);

  return (
    <Card className="min-w-0">
      <CardHeader>
        <CardTitle className="flex min-w-0 items-center gap-2">
          <span className="size-2.5 shrink-0 rounded-full" style={{ background: team.color }} />
          <span className="truncate">{team.name}</span>
        </CardTitle>
        <CardDescription className="flex flex-wrap items-center gap-1.5 text-xs">
          {team.lead && <span>Lead {team.lead}</span>}
          <span className={cn("rounded-full px-1.5 py-px text-[10px] font-medium", STATUS_META[status].className)}>{STATUS_META[status].label}</span>
        </CardDescription>
        <CardAction>
          <Button variant="ghost" size="icon-xs" onClick={onClose} aria-label="Clear selection"><X /></Button>
        </CardAction>
      </CardHeader>

      <CardContent className="space-y-5">
        <dl className="grid grid-cols-3 gap-2 text-sm">
          <Figure label="Allocation" value={typeof allocated === "number" ? formatAmount(allocated, unit) : "Not set"} muted={typeof allocated !== "number"} />
          <Figure label="Spent" value={formatAmount(spent, unit)} />
          <Figure
            label="Projection"
            value={typeof projected === "number" ? formatAmount(projected, unit) : "No projection"}
            muted={typeof projected !== "number"}
            sub={typeof low === "number" && typeof high === "number" ? `${formatAmount(low, unit, { compact: true })} to ${formatAmount(high, unit, { compact: true })}` : undefined}
          />
        </dl>
        {forecast?.status === "unavailable" && (
          <p className="rounded-md bg-muted/60 px-2.5 py-2 text-xs text-muted-foreground">
            {forecast.unavailableReason ?? "Projection unavailable."}
          </p>
        )}
        {forecast?.status === "available" && forecast.origin === "placeholder" && (
          <p className="-mt-3 text-[11px] text-muted-foreground">Placeholder projection, full-period basis.</p>
        )}

        <section className="space-y-2">
          <h3 className="text-xs font-medium text-muted-foreground">Spend by cost component</h3>
          {componentTotal > 0 && (
            <div className="flex h-2 w-full gap-0.5 overflow-hidden rounded-full" aria-hidden>
              {byComponent.filter((c) => c.amount > 0).map((c) => (
                <div key={c.component} className={cn("h-full rounded-sm", SEGMENT_STYLE[c.component])} style={{ width: `${(c.amount / componentTotal) * 100}%` }} />
              ))}
            </div>
          )}
          <ul className="space-y-1.5 text-xs">
            {byComponent.map((c) => (
              <li key={c.component} className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
                <span className="flex items-center gap-1.5">
                  <span className={cn("size-2 rounded-sm", SEGMENT_STYLE[c.component])} />
                  {COMPONENT_LABEL[c.component]}
                  {c.component === "included_usage" && <span className="text-muted-foreground">informational</span>}
                </span>
                <span className="flex items-center gap-1.5">
                  {c.provenances.map((p) => (
                    <Badge key={p} variant="outline" className="h-4 px-1.5 text-[10px] font-normal text-muted-foreground">{PROVENANCE_LABEL[p]}</Badge>
                  ))}
                  <span className="tabular-nums">{c.amount > 0 || c.provenances.length ? formatAmount(c.amount, unit) : "No records"}</span>
                </span>
              </li>
            ))}
          </ul>
        </section>

        <section className="space-y-2">
          <h3 className="text-xs font-medium text-muted-foreground">Last 7 days</h3>
          {last7.length === 0 ? (
            <p className="text-xs text-muted-foreground">No daily records.</p>
          ) : (
            <table className="w-full text-xs">
              <tbody>
                {last7.map((d) => (
                  <tr key={d.date} className="border-t first:border-t-0">
                    <td className="py-1 text-muted-foreground">{dateLabel(d.date)}</td>
                    <td className="py-1 text-right text-muted-foreground">{d.partial && "partial"}</td>
                    <td className="py-1 text-right tabular-nums">{formatAmount(d.amount, unit)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" nativeButton={false} render={<Link href={`/teams/${team.id}`} />}>
            View team <ArrowUpRight />
          </Button>
          <Button
            variant="secondary" size="sm"
            onClick={() => askAssistant(`Why is ${team.name} tracking ${over ? "over" : "under"} its allocation?`)}
          >
            <MessageSquare /> Ask assistant
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function Figure({ label, value, sub, muted }: { label: string; value: string; sub?: string; muted?: boolean }) {
  return (
    <div className="min-w-0">
      <dt className="text-[11px] text-muted-foreground">{label}</dt>
      <dd className={cn("truncate", muted ? "text-xs text-muted-foreground" : "font-medium tabular-nums")}>{value}</dd>
      {sub && <dd className="text-[11px] text-muted-foreground tabular-nums">{sub}</dd>}
    </div>
  );
}
