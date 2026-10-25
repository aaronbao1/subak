"use client";
import { displaySourceText } from "@/lib/display-copy";
import type { Team } from "@/lib/contracts";
import { cn } from "@/lib/utils";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { CATEGORY_OPTIONS, EFFECT_OPTIONS, SCOPE_OPTIONS, isDefaultFilters, type EvidenceFilters } from "./derive";
import { CATEGORY_FILTER_LABEL, EFFECT_FILTER_LABEL, SCOPE_FILTER_LABEL } from "./labels";

interface Props {
  filters: EvidenceFilters;
  teams: Team[];
  onChange: (next: EvidenceFilters) => void;
  /** Rows shown after filtering, for the count at the end of the row. */
  shown: number;
  total: number;
}

const ALL_TEAMS = "__all__";

/** One row of segmented controls plus a team picker. Wraps below lg; every option is a real button with aria-pressed. */
export function FilterRow({ filters, teams, onChange, shown, total }: Props) {
  const set = <K extends keyof EvidenceFilters>(key: K, value: EvidenceFilters[K]) => onChange({ ...filters, [key]: value });
  const active = !isDefaultFilters(filters);

  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-3" role="region" aria-label="Evidence filters">
      <Segmented label="Scope" options={SCOPE_OPTIONS} value={filters.scope} labels={SCOPE_FILTER_LABEL} onChange={(v) => set("scope", v)} />
      <Segmented label="Effect" options={EFFECT_OPTIONS} value={filters.effect} labels={EFFECT_FILTER_LABEL} onChange={(v) => set("effect", v)} />
      <Segmented label="Category" options={CATEGORY_OPTIONS} value={filters.category} labels={CATEGORY_FILTER_LABEL} onChange={(v) => set("category", v)} />

      <div className="flex items-center gap-2">
        <span className="eyebrow">Team</span>
        <Select value={filters.team ?? ALL_TEAMS} onValueChange={(v) => set("team", v && v !== ALL_TEAMS ? v : undefined)}>
          <SelectTrigger size="sm" aria-label="Team" className="h-8 min-w-36 rounded-md border-border bg-popover text-xs hover:border-border-strong">
            <SelectValue>{(v: string | null) => (v && v !== ALL_TEAMS ? displaySourceText(teams.find((t) => t.id === v)?.name, "Selected team") : "All teams")}</SelectValue>
          </SelectTrigger>
          <SelectContent alignItemWithTrigger={false}>
            <SelectItem value={ALL_TEAMS}>All teams</SelectItem>
            {teams.map((t) => (
              <SelectItem key={t.id} value={t.id}>
                <span aria-hidden className="size-2 shrink-0 rounded-full" style={{ background: t.color }} />
                {displaySourceText(t.name, "Team")}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="ml-auto flex items-center gap-3 text-xs text-muted-foreground">
        <span><span className="num text-foreground/80">{shown}</span> of <span className="num">{total}</span> items</span>
        {active && (
          <button
            type="button"
            onClick={() => onChange({ scope: "all", effect: "all", category: "all", team: undefined })}
            className="rounded-sm underline underline-offset-4 decoration-border-strong transition-colors duration-300 hover:text-foreground hover:decoration-foreground"
          >
            Clear filters
          </button>
        )}
      </div>
    </div>
  );
}

function Segmented<T extends string>({ label, options, value, labels, onChange }: { label: string; options: T[]; value: T; labels: Record<T, string>; onChange: (v: T) => void }) {
  return (
    <div className="flex items-center gap-2">
      <span className="eyebrow">{label}</span>
      <div className="flex flex-wrap items-center rounded-md bg-popover p-0.5" role="group" aria-label={label}>
        {options.map((opt) => {
          const pressed = opt === value;
          return (
            <button
              key={opt} type="button" onClick={() => onChange(opt)} aria-pressed={pressed}
              className={cn(
                "h-7 rounded-sm px-2.5 text-xs text-muted-foreground transition-colors duration-300 hover:text-foreground",
                pressed && "bg-card text-foreground",
              )}
            >
              {labels[opt]}
            </button>
          );
        })}
      </div>
    </div>
  );
}
