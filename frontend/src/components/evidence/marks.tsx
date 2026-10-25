"use client";
import { ArrowDownRight, ArrowUpRight, CircleHelp, Minus } from "lucide-react";
import type { ContextItem, Person, Team } from "@/lib/contracts";
import { cn } from "@/lib/utils";
import { initials } from "@/components/context/source-brand";
import { EFFECT_FILL, EFFECT_TEXT as EFFECT_TONE } from "@/components/shared/tone";

const EFFECT_ICON = { increase: ArrowUpRight, decrease: ArrowDownRight, neutral: Minus, unknown: CircleHelp } as const;
export const EFFECT_TEXT = { increase: "Increases spend", decrease: "Decreases spend", neutral: "Neutral", unknown: "Effect unknown" } as const;

/**
 * Effect as an arrow in status color (shared/tone: increase = warning, decrease = success); the label rides along for
 * screen readers and the tooltip. `hollow` draws it thin and faded, for interpretations rather than observed events.
 */
export function EffectArrow({ effect, muted, hollow, className }: { effect: ContextItem["expectedEffect"]; muted?: boolean; hollow?: boolean; className?: string }) {
  const Icon = EFFECT_ICON[effect];
  const tone = muted ? "text-muted-foreground" : EFFECT_TONE[effect];
  const label = hollow ? `${EFFECT_TEXT[effect]} (interpretation)` : EFFECT_TEXT[effect];
  return (
    <span className={cn("inline-flex shrink-0", tone, className)} title={label}>
      <Icon aria-hidden className={cn("size-4", hollow && "opacity-70")} strokeWidth={hollow ? 1 : 1.75} strokeDasharray={hollow ? "2 2" : undefined} />
      <span className="sr-only">{label}</span>
    </span>
  );
}

/** Initials on a wash of the team color; ink stays foreground so text never wears the series color. */
export function Initials({ person, team, className }: { person: Person; team?: Team; className?: string }) {
  const accent = team?.color ?? "var(--border-strong)";
  return (
    <span
      aria-hidden
      className={cn("flex size-6 shrink-0 items-center justify-center rounded-full font-mono text-[10px] text-foreground/90 ring-2 ring-card", className)}
      style={{ background: `color-mix(in oklch, ${accent} 30%, var(--card))` }}
    >
      {initials(person.name) || "?"}
    </span>
  );
}

/** Up to `limit` overlapping initials, then "+N". */
export function InitialsStack({ people, teams, limit = 3 }: { people: Person[]; teams: Team[]; limit?: number }) {
  const shown = people.slice(0, limit);
  const more = people.length - shown.length;
  return (
    <span className="flex items-center" title={people.map((p) => p.name).join(", ")}>
      <span className="flex -space-x-1.5">
        {shown.map((p) => <Initials key={p.id} person={p} team={teams.find((t) => t.id === p.teamId)} className="size-5 text-[9px]" />)}
      </span>
      {more > 0 && <span className="num ml-1 text-[11px] text-muted-foreground">+{more}</span>}
      <span className="sr-only">{people.map((p) => p.name).join(", ")}</span>
    </span>
  );
}

/** Team identity dots, up to `limit`, then "+N". */
export function TeamDots({ teams, limit = 4 }: { teams: Team[]; limit?: number }) {
  const shown = teams.slice(0, limit);
  const more = teams.length - shown.length;
  return (
    <span className="flex items-center gap-1" title={teams.map((t) => t.name).join(", ")}>
      {shown.map((t) => <span key={t.id} aria-hidden className="size-2 shrink-0 rounded-full" style={{ background: t.color }} />)}
      {more > 0 && <span className="num text-[11px] text-muted-foreground">+{more}</span>}
      <span className="sr-only">{teams.map((t) => t.name).join(", ")}</span>
    </span>
  );
}

/**
 * A signed amount as a bar from a center tick: decreases run left in --success, increases right in --warning (shared/tone).
 * The signed number beside it carries the value, so color only reinforces.
 */
export function DivergingBar({ value, max, className, animate, delay = 0 }: { value: number; max: number; className?: string; animate?: boolean; delay?: number }) {
  const half = Math.min(50, (Math.abs(value) / Math.max(1, max)) * 50);
  return (
    <span aria-hidden className={cn("relative block h-1.5", className)}>
      <span className="absolute inset-y-[-2px] left-1/2 w-px -translate-x-1/2 bg-border-strong" />
      {value !== 0 && (
        <span
          className={cn("absolute inset-y-0", animate && "animate-grow-x", value < 0 ? "right-1/2 mr-px rounded-l-sm" : "left-1/2 ml-px rounded-r-sm")}
          style={{ background: EFFECT_FILL[value < 0 ? "decrease" : "increase"], width: `max(2px, calc(${half}% - 1px))`, transformOrigin: value < 0 ? "right center" : "left center", ["--rise-delay" as string]: `${delay}ms` }}
        />
      )}
    </span>
  );
}

