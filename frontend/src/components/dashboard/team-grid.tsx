"use client";
import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import type { Unit } from "@/lib/contracts";
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
 * One compact card per team. Clicking the card selects the team in the chart; the team name and
 * the footer arrow navigate to the team page so both actions stay available.
 */
export function TeamGrid({ summaries, unit, selectedId, onSelect }: TeamGridProps) {
  return (
    <section className="space-y-3" aria-label="Teams">
      <div className="flex items-baseline justify-between px-0.5">
        <h2 className="text-sm font-medium">Teams</h2>
        <span className="text-xs text-muted-foreground">{summaries.length} {summaries.length === 1 ? "team" : "teams"}</span>
      </div>
      <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
        {summaries.map((s) => {
          const { team, budget, spent, projected, high, daily, dailyProjected } = s;
          const allocated = budget?.allocated;
          const status = teamStatus(allocated, projected, high);
          const selected = team.id === selectedId;
          const href = `/teams/${team.id}`;
          return (
            <li key={team.id} className="min-w-0">
              <div
                role="button" tabIndex={0} aria-pressed={selected}
                onClick={() => onSelect(team.id)}
                onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(team.id); } }}
                className={cn(
                  "flex h-full cursor-pointer flex-col gap-3 rounded-xl bg-card p-3.5 ring-1 ring-foreground/10 transition-[box-shadow,background-color] hover:ring-foreground/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  selected && "bg-muted/30 ring-foreground/35 hover:ring-foreground/35",
                )}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <Link
                      href={href} onClick={(e) => e.stopPropagation()}
                      className="flex min-w-0 items-center gap-2 text-sm font-medium hover:underline"
                    >
                      <span className="size-2 shrink-0 rounded-full" style={{ background: team.color }} />
                      <span className="truncate">{team.name}</span>
                    </Link>
                    <p className="mt-0.5 truncate pl-4 text-[11px] text-muted-foreground">{team.lead ? `Lead ${team.lead}` : "No lead set"}</p>
                  </div>
                  <span className={cn("shrink-0 rounded-full px-1.5 py-px text-[10px] font-medium leading-4", STATUS_META[status].className)}>
                    {STATUS_META[status].label}
                  </span>
                </div>

                <dl className="grid grid-cols-3 gap-2">
                  <Figure label="Allocation" value={typeof allocated === "number" ? formatAmount(allocated, unit, { compact: true }) : "Not set"} muted={typeof allocated !== "number"} />
                  <Figure label="Spent" value={formatAmount(spent, unit, { compact: true })} />
                  <Figure label="Projection" value={typeof projected === "number" ? formatAmount(projected, unit, { compact: true }) : "None"} muted={typeof projected !== "number"} />
                </dl>

                <div className="mt-auto flex items-end justify-between gap-3">
                  <Sparkline points={[...daily, ...dailyProjected.filter((p) => !daily.some((d) => d.date === p.date))]} color={team.color} className="h-6 w-full min-w-0 flex-1 opacity-80" />
                  <Link
                    href={href} onClick={(e) => e.stopPropagation()}
                    className="flex shrink-0 items-center gap-0.5 text-[11px] text-muted-foreground hover:text-foreground"
                  >
                    View team <ArrowUpRight className="size-3" />
                  </Link>
                </div>
              </div>
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
      <dd className={cn("truncate text-sm", muted ? "text-muted-foreground" : "font-medium tabular-nums")}>{value}</dd>
    </div>
  );
}

export function TeamGridSkeleton() {
  return (
    <section className="space-y-3">
      <div className="flex items-baseline justify-between px-0.5">
        <Skeleton className="h-4 w-14" />
        <Skeleton className="h-3 w-12" />
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="space-y-3 rounded-xl bg-card p-3.5 ring-1 ring-foreground/10">
            <div className="flex items-start justify-between">
              <div className="space-y-1.5"><Skeleton className="h-4 w-28" /><Skeleton className="h-3 w-20" /></div>
              <Skeleton className="h-4 w-14 rounded-full" />
            </div>
            <div className="grid grid-cols-3 gap-2">
              {Array.from({ length: 3 }).map((_, j) => <div key={j} className="space-y-1"><Skeleton className="h-3 w-14" /><Skeleton className="h-4 w-12" /></div>)}
            </div>
            <Skeleton className="h-6 w-full" />
          </div>
        ))}
      </div>
    </section>
  );
}
