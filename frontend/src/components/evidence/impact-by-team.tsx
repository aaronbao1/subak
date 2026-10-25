"use client";
import { useState } from "react";
import { cn } from "@/lib/utils";
import type { TeamImpact } from "./derive";
import { signedAmount } from "./labels";
import { DivergingBar } from "./marks";

interface Props {
  impacts: TeamImpact[];
  selectedTeam?: string;
  onSelect: (teamId: string | undefined) => void;
  /** No forecast carries adjustments yet: rows show item counts as a neutral meter instead. */
  hasAnyAdjustments: boolean;
  mounted: boolean;
}

const TOP = 8;

/** Bar list: team · diverging bar · net. Sorted by size, top N then "+N more". A row filters the feed. */
export function ImpactByTeam({ impacts, selectedTeam, onSelect, hasAnyAdjustments, mounted }: Props) {
  const [all, setAll] = useState(false);
  const sorted = [...impacts].sort((a, b) => (hasAnyAdjustments ? Math.abs(b.net) - Math.abs(a.net) : b.items - a.items) || a.team.name.localeCompare(b.team.name));
  const visible = all ? sorted : sorted.slice(0, TOP);
  // Keep the selected team visible even when it falls outside the top N.
  const selected = sorted.find((r) => r.team.id === selectedTeam);
  if (selected && !visible.includes(selected)) visible.push(selected);
  const more = sorted.length - visible.length;
  const maxNet = Math.max(1, ...impacts.map((i) => Math.abs(i.net)));
  const maxItems = Math.max(1, ...impacts.map((i) => i.items));

  if (impacts.length === 0) return null;

  return (
    <section aria-labelledby="impact-heading" className="rounded-xl border border-border bg-card py-4">
      <h2 id="impact-heading" className="px-5 pb-2 text-sm font-medium">{hasAnyAdjustments ? "Impact by team" : "Items by team"}</h2>
      <ul role="list">
        {visible.map((row, i) => {
          const isSel = selectedTeam === row.team.id;
          return (
            <li key={row.team.id}>
              <button
                type="button"
                aria-pressed={isSel}
                onClick={() => onSelect(isSel ? undefined : row.team.id)}
                title={row.overAllotment ? "Pushes the projection over the allotment" : undefined}
                className={cn(
                  "grid w-full grid-cols-[8px_minmax(0,7.5rem)_minmax(0,1fr)_3.5rem] items-center gap-3 px-5 py-1.5 text-left transition-colors duration-300 hover:bg-popover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:ring-inset",
                  isSel && "bg-brand-soft shadow-[inset_2px_0_0_var(--brand)]",
                )}
              >
                <span aria-hidden className="size-2 rounded-full" style={{ background: row.team.color }} />
                <span className="truncate text-xs text-foreground/80">{row.team.name}</span>
                {hasAnyAdjustments ? (
                  <DivergingBar value={row.net} max={maxNet} animate={mounted} delay={i * 40} />
                ) : (
                  <span aria-hidden className="relative block h-1.5 overflow-hidden rounded-sm bg-popover">
                    <span className={cn("absolute inset-y-0 left-0 rounded-sm bg-foreground/40", mounted && "animate-grow-x")} style={{ width: `${(row.items / maxItems) * 100}%`, ["--rise-delay" as string]: `${i * 40}ms` }} />
                  </span>
                )}
                <span className={cn("num text-right text-xs", row.overAllotment ? "text-destructive" : row.hasAdjustments || (!hasAnyAdjustments && row.items) ? "text-foreground" : "text-muted-foreground")}>
                  {hasAnyAdjustments ? (row.hasAdjustments ? signedAmount(row.net, row.unit, { compact: true }) : "—") : row.items}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
      {(more > 0 || all) && (
        <button type="button" onClick={() => setAll(!all)} className="num mt-1 px-5 text-[11px] text-muted-foreground transition-colors duration-300 hover:text-foreground">
          {all ? "Show less" : `+${more} more`}
        </button>
      )}
    </section>
  );
}
