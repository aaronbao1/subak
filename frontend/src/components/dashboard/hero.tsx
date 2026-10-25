import type { Unit } from "@/lib/contracts";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { formatAmount, formatPct, pct } from "@/lib/format";
import { dateLabel } from "./derive";

export interface HeroProps {
  unit: Unit;
  spent: number;
  /** Sum of allocations; undefined when there are no budgets. */
  envelope?: number;
  /** Sum of available full-period projections; undefined when none is available. */
  projected?: number;
  projectedTeamCount: number;
  unavailableCount: number;
  teamCount: number;
  periodLabel?: string;
  periodRange?: string;
  asOf?: string;
  hasPlaceholder: boolean;
  isDemo: boolean;
}

export function Hero(p: HeroProps) {
  const used = p.envelope ? Math.min(100, pct(p.spent, p.envelope)) : 0;
  return (
    <section aria-label="Company spend summary" className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
        <span>Recorded spend to date</span>
        {p.isDemo && <Badge variant="outline" className="h-4 px-1.5 text-[10px] font-normal">demo data</Badge>}
        {p.hasPlaceholder && <Badge variant="secondary" className="h-4 px-1.5 text-[10px] font-normal text-muted-foreground">placeholder projections</Badge>}
      </div>

      <div className="text-5xl font-semibold leading-none tracking-tight md:text-6xl">
        {formatAmount(p.spent, p.unit)}
      </div>

      <dl className="flex flex-wrap gap-x-8 gap-y-2 text-sm">
        <Stat label="Company envelope" value={p.envelope === undefined ? "No budgets yet" : formatAmount(p.envelope, p.unit)} muted={p.envelope === undefined} />
        <Stat
          label="Projected for period"
          value={p.projected === undefined ? "No projection" : formatAmount(p.projected, p.unit)}
          muted={p.projected === undefined}
          hint={p.projected !== undefined && p.projectedTeamCount < p.teamCount ? `${p.projectedTeamCount} of ${p.teamCount} teams` : undefined}
        />
        <Stat label="Period" value={p.periodLabel ?? "Period not set"} muted={!p.periodLabel} title={p.periodRange} />
        <Stat label="As of" value={p.asOf ? dateLabel(p.asOf) : "No complete day yet"} muted={!p.asOf} title={p.asOf} />
      </dl>

      {p.envelope !== undefined && p.envelope > 0 && (
        <div className="max-w-xl space-y-1.5">
          <Progress value={used} aria-label="Spent versus envelope" />
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>{formatPct(pct(p.spent, p.envelope))} of envelope recorded</span>
            <span>{formatAmount(Math.max(0, p.envelope - p.spent), p.unit)} remaining</span>
          </div>
        </div>
      )}

      {p.unavailableCount > 0 && (
        <p className="text-xs text-muted-foreground">
          {p.unavailableCount} {p.unavailableCount === 1 ? "team" : "teams"} without a projection
        </p>
      )}
    </section>
  );
}

function Stat({ label, value, muted, hint, title }: { label: string; value: string; muted?: boolean; hint?: string; title?: string }) {
  return (
    <div title={title}>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className={muted ? "text-muted-foreground" : "font-medium tabular-nums"}>
        {value}
        {hint && <span className="ml-1.5 text-xs font-normal text-muted-foreground">{hint}</span>}
      </dd>
    </div>
  );
}

export function HeroSkeleton() {
  return (
    <section className="space-y-4">
      <Skeleton className="h-4 w-40" />
      <Skeleton className="h-14 w-72" />
      <div className="flex gap-8">
        <Skeleton className="h-10 w-28" />
        <Skeleton className="h-10 w-28" />
        <Skeleton className="h-10 w-28" />
        <Skeleton className="h-10 w-28" />
      </div>
      <Skeleton className="h-1 max-w-xl" />
    </section>
  );
}
