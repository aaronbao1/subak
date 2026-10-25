"use client";
import type { ReactNode } from "react";
import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import type { Team } from "@/lib/contracts";
import { cn } from "@/lib/utils";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { CATEGORY_OPTIONS, EFFECT_OPTIONS, SCOPE_OPTIONS, isDefaultFilters, type CategoryFilter, type EffectFilter, type EvidenceFilters } from "./derive";
import { CATEGORY_FILTER_LABEL, EFFECT_FILTER_LABEL, SCOPE_FILTER_LABEL } from "./labels";

interface Props {
  filters: EvidenceFilters;
  teams: Team[];
  onChange: (next: EvidenceFilters) => void;
  shown: number;
  total: number;
}

const ALL = "__all__";
const TRIGGER = "h-8 rounded-md border-transparent bg-popover text-xs hover:border-border-strong dark:bg-popover dark:hover:bg-popover";
const EFFECT_ICON: Record<EffectFilter, ReactNode> = {
  all: "All",
  increase: <ArrowUpRight aria-hidden className="size-3.5" strokeWidth={1.75} />,
  decrease: <ArrowDownRight aria-hidden className="size-3.5" strokeWidth={1.75} />,
};

/** One quiet row: scope and effect as segments, category and team as pickers, the count at the end. */
export function FilterRow({ filters, teams, onChange, shown, total }: Props) {
  const set = <K extends keyof EvidenceFilters>(key: K, value: EvidenceFilters[K]) => onChange({ ...filters, [key]: value });
  const active = !isDefaultFilters(filters);

  return (
    <div className="flex flex-wrap items-center gap-2" role="region" aria-label="Evidence filters">
      <Segmented label="Scope" options={SCOPE_OPTIONS} value={filters.scope} render={(o) => SCOPE_FILTER_LABEL[o]} onChange={(v) => set("scope", v)} />
      <Segmented label="Effect" options={EFFECT_OPTIONS} value={filters.effect} render={(o) => EFFECT_ICON[o]} aria={(o) => EFFECT_FILTER_LABEL[o]} onChange={(v) => set("effect", v)} />

      <Select value={filters.category} onValueChange={(v) => set("category", (v ?? "all") as CategoryFilter)}>
        <SelectTrigger size="sm" aria-label="Category" className={TRIGGER}>
          <SelectValue>{(v: string | null) => (v && v !== "all" ? CATEGORY_FILTER_LABEL[v as CategoryFilter] : "Any category")}</SelectValue>
        </SelectTrigger>
        <SelectContent alignItemWithTrigger={false}>
          {CATEGORY_OPTIONS.map((c) => <SelectItem key={c} value={c}>{c === "all" ? "Any category" : CATEGORY_FILTER_LABEL[c]}</SelectItem>)}
        </SelectContent>
      </Select>

      <Select value={filters.team ?? ALL} onValueChange={(v) => set("team", v && v !== ALL ? v : undefined)}>
        <SelectTrigger size="sm" aria-label="Team" className={cn(TRIGGER, "min-w-32")}>
          <SelectValue>{(v: string | null) => (v && v !== ALL ? teams.find((t) => t.id === v)?.name ?? v : "All teams")}</SelectValue>
        </SelectTrigger>
        <SelectContent alignItemWithTrigger={false}>
          <SelectItem value={ALL}>All teams</SelectItem>
          {teams.map((t) => (
            <SelectItem key={t.id} value={t.id}>
              <span aria-hidden className="size-2 shrink-0 rounded-full" style={{ background: t.color }} />
              {t.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <div className="ml-auto flex items-center gap-3 text-xs text-muted-foreground">
        <span className="num">{active ? `${shown}/${total}` : total}</span>
        {active && (
          <button
            type="button"
            onClick={() => onChange({ scope: "all", effect: "all", category: "all", team: undefined })}
            className="rounded-sm underline underline-offset-4 decoration-border-strong transition-colors duration-300 hover:text-foreground hover:decoration-foreground"
          >
            Clear
          </button>
        )}
      </div>
    </div>
  );
}

function Segmented<T extends string>({ label, options, value, render, aria, onChange }: { label: string; options: T[]; value: T; render: (v: T) => ReactNode; aria?: (v: T) => string; onChange: (v: T) => void }) {
  return (
    <div className="flex items-center rounded-md bg-popover p-0.5" role="group" aria-label={label}>
      {options.map((opt) => {
        const pressed = opt === value;
        return (
          <button
            key={opt} type="button" onClick={() => onChange(opt)} aria-pressed={pressed} aria-label={aria?.(opt)} title={aria?.(opt)}
            className={cn("inline-flex h-7 items-center rounded-sm px-2.5 text-xs text-muted-foreground transition-colors duration-300 hover:text-foreground", pressed && "bg-card text-foreground")}
          >
            {render(opt)}
          </button>
        );
      })}
    </div>
  );
}
