"use client";
import type { Unit } from "@/lib/contracts";
import { Skeleton } from "@/components/ui/skeleton";
import { chartMoney } from "@/components/forecast/chart-data";
import type { TeamSummary } from "./derive";

export interface HeroProps {
  unit: Unit; spent: number; envelope?: number; projected?: number; projectedTeamCount: number;
  projectionCoverageNote?: string; unavailableCount: number; unavailableTeams?: string[]; teamCount: number;
  periodLabel?: string; periodRange?: string; asOf?: string; hasPlaceholder?: boolean; summaries?: TeamSummary[];
}
/** Legacy callers receive immediate known values; there is no simulated calculation state. */
export function Hero(props: HeroProps) {
  return <section aria-label="Company spend summary" className="rounded-xl border border-border bg-card p-5">
    <p className="text-xs text-muted-foreground">{props.periodLabel ?? "Selected period"}{props.periodRange && ` · ${props.periodRange}`}</p>
    <dl className="mt-4 grid gap-5 sm:grid-cols-3">{[{ label: "Spend to date", value: props.spent }, { label: "Budget", value: props.envelope }, { label: "Expected spend", value: props.projected }].map(item => <div key={item.label}><dt className="text-xs text-muted-foreground">{item.label}</dt><dd className="mt-2 text-3xl font-medium tabular-nums">{chartMoney(item.value, props.unit)}</dd></div>)}</dl>
    {props.projectionCoverageNote && <p className="mt-3 text-xs text-muted-foreground">{props.projectionCoverageNote}</p>}
  </section>;
}
export function excludedSentence(count: number, names: string[]): string { return `${count} ${count === 1 ? "team" : "teams"} with no projection available${names.length ? `: ${names.slice(0, 3).join(", ")}${names.length > 3 ? ` +${names.length - 3} more` : ""}` : ""}`; }
export function likelyOverSentence(names: string[]): string { return `${names.length} ${names.length === 1 ? "team" : "teams"} likely over: ${names.slice(0, 3).join(", ")}${names.length > 3 ? ` +${names.length - 3} more` : ""}`; }
export function HeroSkeleton() { return <section aria-label="Loading financial summary" className="grid grid-cols-2 gap-5 rounded-xl border border-border bg-card p-5 lg:grid-cols-4">{[0, 1, 2, 3].map(index => <div key={index} className="space-y-3"><Skeleton className="h-3 w-24" /><Skeleton className="h-8 w-32" /><Skeleton className="h-3 w-28" /></div>)}</section>; }
