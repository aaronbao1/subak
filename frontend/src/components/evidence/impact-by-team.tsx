"use client";
import { cn } from "@/lib/utils";
import type { TeamImpact } from "./derive";
import { signedAmount } from "./labels";

interface Props {
  impacts: TeamImpact[];
  selectedTeam?: string;
  onSelect: (teamId: string | undefined) => void;
  /** No forecast carries adjustments yet; the bars are left out and the panel says why. */
  hasAnyAdjustments: boolean;
  mounted: boolean;
}

/**
 * One row per team: items, net adjustment, and a diverging bar centered at zero. Decreases run left in
 * --success, increases right in --destructive; the signed number beside the bar carries the value, so the
 * color is reinforcement rather than the only encoding. Clicking a row filters the feed to that team.
 */
export function ImpactByTeam({ impacts, selectedTeam, onSelect, hasAnyAdjustments, mounted }: Props) {
  const max = Math.max(1, ...impacts.map((i) => Math.abs(i.net)));
  return (
    <section aria-labelledby="impact-heading" className="rounded-xl border border-border bg-card">
      <header className="px-5 pt-5 pb-3">
        <h2 id="impact-heading" className="text-base font-medium">Impact by team</h2>
        <p className="mt-0.5 text-xs text-muted-foreground">
          {hasAnyAdjustments ? "Net amount evidence moved each team's projection. Select a team to filter the feed." : "Items per team. Adjustment amounts arrive with the forecast."}
        </p>
      </header>
      {impacts.length === 0 ? (
        <p className="px-5 pb-5 text-sm text-muted-foreground">No teams in this dataset.</p>
      ) : (
        <ul className="divide-y divide-border border-t border-border" role="list">
          {impacts.map((row, i) => {
            const selected = selectedTeam === row.team.id;
            const half = Math.min(50, (Math.abs(row.net) / max) * 50);
            return (
              <li key={row.team.id}>
                <button
                  type="button"
                  aria-pressed={selected}
                  onClick={() => onSelect(selected ? undefined : row.team.id)}
                  className={cn(
                    "flex w-full items-center gap-3 px-5 py-2.5 text-left transition-colors duration-300 hover:bg-popover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:ring-inset",
                    selected && "bg-brand-soft shadow-[inset_2px_0_0_var(--brand)]",
                  )}
                >
                  <span aria-hidden className="size-2 shrink-0 rounded-full" style={{ background: row.team.color }} />
                  <span className="min-w-0 flex-1">
                    <span className="flex items-baseline justify-between gap-3">
                      <span className="truncate text-sm">{row.team.name}</span>
                      <span className={cn("num shrink-0 text-sm", row.overAllotment ? "text-destructive" : row.hasAdjustments ? "text-foreground" : "text-muted-foreground")}>
                        {row.hasAdjustments ? signedAmount(row.net, row.unit, { compact: true }) : "—"}
                      </span>
                    </span>
                    <span className="mt-1 flex items-center gap-3">
                      <span className="num shrink-0 text-[11px] text-muted-foreground">{row.items} {row.items === 1 ? "item" : "items"}</span>
                      {hasAnyAdjustments && (
                        <span className="relative h-1.5 flex-1" aria-hidden>
                          {/* Neutral midpoint. */}
                          <span className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-border-strong" />
                          {row.net !== 0 && (
                            <span
                              className={cn("absolute inset-y-0", mounted && "animate-grow-x", row.net < 0 ? "right-1/2 mr-0.5 rounded-l-full bg-success" : "left-1/2 ml-0.5 rounded-r-full bg-destructive")}
                              style={{ width: `calc(${half}% - 2px)`, transformOrigin: row.net < 0 ? "right center" : "left center", ["--rise-delay" as string]: `${i * 40}ms` }}
                            />
                          )}
                        </span>
                      )}
                    </span>
                    {row.overAllotment && <span className="mt-1 block text-[11px] text-destructive">Pushes the projection over the allotment</span>}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
