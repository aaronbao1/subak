"use client";
import { formatAmount } from "@/lib/format";
import { StatTile } from "@/components/shared/stat-tile";
import { Tag } from "@/components/team/labels";
import type { ProjectionTotals } from "./derive";
import { signedAmount } from "./labels";

/**
 * How the projection is built: trend baseline → evidence adjustments → projected. The arrow between the
 * tiles is the hero's connector in its static form: a hairline with three chevrons, no animation.
 */
export function ProjectionStrip({ totals }: { totals: ProjectionTotals }) {
  const { unit } = totals;
  const fmt = (n: number) => formatAmount(n, unit);
  const coverage = totals.teamsProjected < totals.teamsTotal
    ? `${totals.teamsProjected} of ${totals.teamsTotal} teams have a projection`
    : `${totals.teamsTotal} ${totals.teamsTotal === 1 ? "team" : "teams"}`;
  const aside = (
    <>
      {totals.anyScenario && <Tag title="Conditional on the stated assumptions; not an unconditional forecast">Scenario</Tag>}
    </>
  );

  if (totals.teamsProjected === 0) {
    return (
      <section aria-label="How the projection is built" className="rounded-xl border border-border bg-card p-5">
        <div className="eyebrow">How the projection is built</div>
        <p className="mt-2 text-sm text-muted-foreground">No team has an available projection for this period, so there is nothing to decompose yet.</p>
      </section>
    );
  }

  if (!totals.hasBaseline) {
    return (
      <section aria-label="How the projection is built" className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
        <StatTile card label="Projected" value={totals.projected} animate format={fmt} aside={aside} caption={periodCaption(totals, coverage)} />
        <div className="flex flex-col justify-center rounded-xl border border-dashed border-border p-5">
          <div className="eyebrow">Adjustments not provided by the forecast yet</div>
          <p className="mt-2 text-sm text-muted-foreground">
            The forecasts carry a projected total but no trend baseline, so the share that evidence moved cannot be shown. The feed below still lists what each item is expected to do.
          </p>
          <p className="num mt-3 text-xs text-muted-foreground">projected = trend baseline + evidence adjustments</p>
        </div>
      </section>
    );
  }

  return (
    <section aria-label="How the projection is built" className="space-y-3">
      <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)_auto_minmax(0,1fr)] md:items-stretch">
        <StatTile
          card label="Trend baseline" value={totals.baseline} animate format={fmt}
          caption={<>Where the trend alone lands &middot; {coverage}</>}
        />
        <Connector />
        <StatTile
          card label="Evidence adjustments" value={totals.adjustments} animate format={(n) => signedAmount(n, unit)}
          caption={<><span className="num">{totals.appliedItems}</span> {totals.appliedItems === 1 ? "item" : "items"} applied</>}
          muted={!totals.hasAdjustments}
        />
        <Connector />
        <StatTile card label="Projected" value={totals.projected} animate format={fmt} aside={aside} caption={periodCaption(totals, coverage)} />
      </div>
      <p className="num text-xs text-muted-foreground">
        projected = trend baseline + evidence adjustments
        {totals.anyRemaining && <span> &middot; remaining basis: excludes spend already incurred</span>}
      </p>
    </section>
  );
}

function periodCaption(totals: ProjectionTotals, coverage: string) {
  return totals.periodLabel ? <>{totals.periodLabel} &middot; {coverage}</> : coverage;
}

/** Static hairline with chevrons pointing from one figure to the next. Hidden when the tiles stack. */
function Connector() {
  return (
    <div className="hidden items-center md:flex" aria-hidden>
      <svg width="56" height="16" viewBox="0 0 56 16" className="block overflow-visible">
        <line x1="2" y1="8" x2="50" y2="8" stroke="var(--foreground)" strokeOpacity={0.22} strokeWidth={1.25} strokeLinecap="round" />
        {[14, 26, 38].map((x) => (
          <path key={x} d={`M${x - 3},3 L${x + 2},8 L${x - 3},13`} fill="none" stroke="var(--foreground)" strokeOpacity={0.6} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
        ))}
        <polygon points="50,3 55,8 50,13" fill="var(--foreground)" fillOpacity={0.8} />
      </svg>
    </div>
  );
}
