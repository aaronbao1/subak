"use client";
import { Popover } from "@base-ui/react/popover";
import { Check, ChevronDown, ListFilter } from "lucide-react";
import type { Team } from "@/lib/contracts";
import { cn } from "@/lib/utils";

export interface TeamPickerProps {
  teams: Team[];
  /** Ids currently hidden from the chart. Empty means every team is drawn. */
  hiddenIds: ReadonlySet<string>;
  onChange: (hidden: Set<string>) => void;
  /** Ids drawn only as part of the summed "Other" line, so the reader can see which teams to swap in. */
  foldedIds?: ReadonlySet<string>;
}

/**
 * Dropdown of every team with a checkbox each, so a crowded chart can be thinned to the lines that matter.
 * Stores the *hidden* set rather than the visible one: an empty set means "all", and a dataset switch
 * that adds teams shows them by default instead of silently leaving them out.
 */
export function TeamPicker({ teams, hiddenIds, onChange, foldedIds }: TeamPickerProps) {
  const visibleCount = teams.filter((t) => !hiddenIds.has(t.id)).length;
  const allVisible = visibleCount === teams.length;
  const label = allVisible ? "All teams" : `${visibleCount} teams shown`;

  const toggle = (id: string) => {
    const next = new Set(hiddenIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    onChange(next);
  };
  const only = (id: string) => onChange(new Set(teams.filter((t) => t.id !== id).map((t) => t.id)));

  return (
    <Popover.Root>
      <Popover.Trigger
        aria-label="Choose teams to show on the chart"
        className={cn(
          "flex h-7 items-center gap-1.5 rounded-md border border-transparent px-2 text-xs text-muted-foreground transition-colors duration-300 outline-none select-none",
          "hover:bg-popover hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50 data-popup-open:bg-popover data-popup-open:text-foreground",
          !allVisible && "border-border bg-popover text-foreground",
        )}
      >
        <ListFilter aria-hidden className="size-4" strokeWidth={1.5} />
        <span className="num">{label}</span>
        <ChevronDown aria-hidden className="size-3" strokeWidth={1.5} />
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Positioner side="bottom" align="end" sideOffset={6} className="isolate z-50">
          <Popover.Popup
            className={cn(
              "w-60 max-h-(--available-height) origin-(--transform-origin) overflow-hidden rounded-lg border border-border bg-popover text-popover-foreground shadow-[0_8px_32px_rgba(0,0,0,0.5)]",
              "duration-150 data-open:animate-in data-open:fade-in-0 data-closed:animate-out data-closed:fade-out-0",
            )}
          >
            <div className="flex h-10 items-center justify-between gap-2 border-b border-border px-3">
              <span className="eyebrow">Teams on chart</span>
              <span className="flex items-center gap-1 text-xs text-muted-foreground">
                <button
                  type="button"
                  onClick={() => onChange(new Set())}
                  disabled={allVisible}
                  className="rounded-sm px-1.5 py-0.5 transition-colors duration-300 hover:bg-muted hover:text-foreground disabled:opacity-50 disabled:hover:bg-transparent"
                >
                  All
                </button>
                <button
                  type="button"
                  onClick={() => onChange(new Set(teams.map((t) => t.id)))}
                  disabled={visibleCount === 0}
                  className="rounded-sm px-1.5 py-0.5 transition-colors duration-300 hover:bg-muted hover:text-foreground disabled:opacity-50 disabled:hover:bg-transparent"
                >
                  None
                </button>
              </span>
            </div>
            <ul className="max-h-72 overflow-y-auto p-1" role="group" aria-label="Teams">
              {teams.map((t) => {
                const checked = !hiddenIds.has(t.id);
                const folded = checked && (foldedIds?.has(t.id) ?? false);
                return (
                  <li key={t.id} className="group/row flex items-center rounded-md hover:bg-muted">
                    <label className="flex min-w-0 flex-1 cursor-pointer items-center gap-2 py-1.5 pl-2 pr-1 text-xs select-none">
                      <input type="checkbox" className="peer sr-only" checked={checked} onChange={() => toggle(t.id)} />
                      <span
                        aria-hidden
                        className={cn(
                          "flex size-3.5 shrink-0 items-center justify-center rounded-sm border border-border-strong transition-colors duration-300",
                          "peer-focus-visible:ring-2 peer-focus-visible:ring-ring/50",
                          checked && "border-transparent",
                        )}
                        style={checked ? { background: t.color } : undefined}
                      >
                        {checked && <Check className="size-2.5 text-background" strokeWidth={1.5} />}
                      </span>
                      <span className={cn("truncate", !checked && "text-muted-foreground")}>{t.name}</span>
                      {folded && <span className="ml-auto shrink-0 text-[11px] text-muted-foreground">in Other</span>}
                    </label>
                    <button
                      type="button"
                      onClick={() => only(t.id)}
                      className="mr-1 shrink-0 rounded-sm px-1.5 py-0.5 text-[11px] text-muted-foreground opacity-0 transition-opacity duration-150 hover:bg-muted hover:text-foreground focus-visible:opacity-100 group-hover/row:opacity-100"
                    >
                      Only
                    </button>
                  </li>
                );
              })}
            </ul>
          </Popover.Popup>
        </Popover.Positioner>
      </Popover.Portal>
    </Popover.Root>
  );
}
