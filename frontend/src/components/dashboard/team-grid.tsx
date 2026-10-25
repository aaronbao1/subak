"use client";
import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import type { Unit } from "@/lib/contracts";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatAmount } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { TeamSummary } from "./derive";
import { Sparkline } from "./sparkline";
import { STATUS_META, teamStatus } from "./status";

export interface TeamGridProps {
  summaries: TeamSummary[];
  unit: Unit;
  selectedId: string | null;
  onSelect: (teamId: string) => void;
}

/**
 * One card per team. Clicking the card selects the team in the chart; the team name and
 * the footer arrow navigate to the team page so both actions stay available.
 */
export function TeamGrid({ summaries, unit, selectedId, onSelect }: TeamGridProps) {
  return (
    <section className="space-y-3" aria-label="Teams">
      <div className="flex items-baseline justify-between">
        <h2 className="text-base font-medium">Teams</h2>
        <span className="text-xs text-muted-foreground">{summaries.length} {summaries.length === 1 ? "team" : "teams"}</span>
      </div>
      <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
        {summaries.map((s) => {
          const { team, budget, spent, projected, daily } = s;
          const allocated = budget?.allocated;
          const status = teamStatus(allocated, projected);
          const selected = team.id === selectedId;
          const href = `/teams/${team.id}`;
          return (
            <li key={team.id} className="min-w-0">
              <Card
                size="sm" role="button" tabIndex={0} aria-pressed={selected}
                onClick={() => onSelect(team.id)}
                onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(team.id); } }}
                className={cn(
                  "h-full cursor-pointer transition-shadow hover:ring-foreground/25 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  selected && "ring-2 ring-foreground/40",
                )}
              >
                <CardHeader>
                  <CardTitle className="min-w-0">
                    <Link
                      href={href} onClick={(e) => e.stopPropagation()}
                      className="flex items-center gap-2 font-medium hover:underline"
                    >
                      <span className="size-2.5 shrink-0 rounded-full" style={{ background: team.color }} />
                      <span className="truncate">{team.name}</span>
                    </Link>
                  </CardTitle>
                  <CardDescription className="truncate text-xs">{team.lead ? `Lead ${team.lead}` : "No lead set"}</CardDescription>
                  <CardAction>
                    <span className={cn("rounded-full px-1.5 py-px text-[10px] font-medium", STATUS_META[status].className)}>
                      {STATUS_META[status].label}
                    </span>
                  </CardAction>
                </CardHeader>
                <CardContent className="space-y-3">
                  <dl className="grid grid-cols-3 gap-2 text-xs">
                    <Figure label="Allocation" value={typeof allocated === "number" ? formatAmount(allocated, unit, { compact: true }) : "Not set"} muted={typeof allocated !== "number"} />
                    <Figure label="Spent" value={formatAmount(spent, unit, { compact: true })} />
                    <Figure label="Projection" value={typeof projected === "number" ? formatAmount(projected, unit, { compact: true }) : "None"} muted={typeof projected !== "number"} />
                  </dl>
                  <div className="flex items-end justify-between gap-3">
                    <Sparkline points={daily} color={team.color} className="h-7 w-full min-w-0 flex-1" />
                    <Link
                      href={href} onClick={(e) => e.stopPropagation()}
                      className="flex shrink-0 items-center gap-0.5 text-xs text-muted-foreground hover:text-foreground"
                    >
                      View team <ArrowUpRight className="size-3" />
                    </Link>
                  </div>
                </CardContent>
              </Card>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function Figure({ label, value, muted }: { label: string; value: string; muted?: boolean }) {
  return (
    <div className="min-w-0">
      <dt className="text-[11px] text-muted-foreground">{label}</dt>
      <dd className={cn("truncate", muted ? "text-muted-foreground" : "font-medium tabular-nums")}>{value}</dd>
    </div>
  );
}

export function TeamGridSkeleton() {
  return (
    <section className="space-y-3">
      <Skeleton className="h-5 w-20" />
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
        {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-36 w-full" />)}
      </div>
    </section>
  );
}
