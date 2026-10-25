"use client";
import { formatAmount } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useCountUp } from "@/components/shared/motion";
import { EFFECT_FILL } from "@/components/shared/tone";
import { Tag } from "@/components/team/labels";
import type { ProjectionTotals, ScopeStep } from "./derive";
import { signedAmount } from "./labels";

const H = 96;
const STEP_LABEL: Record<ScopeStep["scope"], string> = { company: "Company", team: "Teams", person: "People", other: "Other" };

interface Col {
  key: string;
  label: string;
  lo: number;
  hi: number;
  value: string;
  kind: "total" | "up" | "down";
  title: string;
}

/**
 * Trend baseline → signed steps by evidence scope → projection, as one small zero-based waterfall.
 * Exact values sit above each bar; item counts and the basis live in the bar's tooltip.
 */
export function ProjectionStrip({ totals, steps, mounted }: { totals: ProjectionTotals; steps: ScopeStep[]; mounted: boolean }) {
  const { unit } = totals;
  const projected = useCountUp(totals.projected);
  const fmt = (n: number) => formatAmount(n, unit, { compact: true });

  if (totals.teamsProjected === 0) return null;

  const cols: Col[] = [];
  if (totals.hasBaseline) {
    cols.push({ key: "base", label: "Trend", lo: 0, hi: totals.baseline, value: fmt(totals.baseline), kind: "total", title: `Trend baseline ${formatAmount(totals.baseline, unit)}` });
    let run = totals.baseline;
    for (const s of steps) {
      if (s.amount === 0) continue;
      const next = run + s.amount;
      cols.push({
        key: s.scope, label: STEP_LABEL[s.scope], lo: Math.min(run, next), hi: Math.max(run, next),
        value: signedAmount(s.amount, unit, { compact: true }), kind: s.amount > 0 ? "up" : "down",
        title: `${STEP_LABEL[s.scope]} evidence ${signedAmount(s.amount, unit)} · ${s.items} ${s.items === 1 ? "item" : "items"}`,
      });
      run = next;
    }
  }
  cols.push({ key: "proj", label: "Projected", lo: 0, hi: totals.projected, value: fmt(totals.projected), kind: "total", title: `Projected ${formatAmount(totals.projected, unit)}${totals.anyRemaining ? " · remaining basis, excludes incurred spend" : ""}` });

  const max = Math.max(1, ...cols.map((c) => c.hi));
  const y = (v: number) => (v / max) * H;
  const partial = totals.teamsProjected < totals.teamsTotal;

  return (
    <section aria-label="How the projection is built" className="rounded-xl border border-border bg-card p-5">
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-4">
        <div className="space-y-1">
          <div className="eyebrow">{totals.periodLabel ? `Projected · ${totals.periodLabel}` : "Projected"}</div>
          <div className="num text-[32px] leading-none font-normal">{formatAmount(projected, unit)}</div>
          <div className="flex flex-wrap items-center gap-2 pt-1 text-xs text-muted-foreground">
            {totals.hasAdjustments && <span className="num">{signedAmount(totals.adjustments, unit, { compact: true })} from evidence</span>}
            {partial && <span className="num">{totals.teamsProjected}/{totals.teamsTotal} teams</span>}
            {totals.anyRemaining && <span title="Remaining basis: excludes spend already incurred">excl. incurred</span>}
            {totals.anyScenario && <Tag title="Conditional on the stated assumptions; not an unconditional forecast">Scenario</Tag>}
          </div>
        </div>

        <figure className="min-w-0 flex-1 sm:max-w-[420px]" aria-label="Projection waterfall">
          <div className="relative flex items-end" style={{ height: H + 18 }}>
            {/* Baseline hairline. */}
            <span aria-hidden className="absolute inset-x-0 bottom-0 h-px bg-border" />
            {cols.map((c, i) => {
              const bottom = y(c.lo);
              const height = Math.max(2, y(c.hi) - y(c.lo));
              const endLevel = c.kind === "down" ? c.lo : c.hi;
              const next = cols[i + 1];
              return (
                <div key={c.key} className="relative h-full flex-1" title={c.title}>
                  {next && (
                    <span aria-hidden className="absolute left-1/2 w-full border-t border-dashed border-border-strong" style={{ bottom: y(endLevel) }} />
                  )}
                  <span
                    className={cn(
                      "num absolute inset-x-0 text-center text-[11px] whitespace-nowrap",
                      c.kind === "total" ? "text-foreground/80" : "text-muted-foreground",
                    )}
                    style={{ bottom: bottom + height + 4 }}
                  >
                    {c.value}
                  </span>
                  <span
                    aria-hidden
                    className={cn(
                      "absolute left-1/2 w-6 -translate-x-1/2",
                      mounted && "animate-grow-y",
                      c.kind === "total" && (c.key === "proj" ? "rounded-t-[4px] bg-foreground/70" : "rounded-t-[4px] bg-foreground/30"),
                      c.kind === "up" && "rounded-t-[4px]",
                      c.kind === "down" && "rounded-b-[4px]",
                    )}
                    style={{ background: c.kind === "up" ? EFFECT_FILL.increase : c.kind === "down" ? EFFECT_FILL.decrease : undefined, bottom, height, ["--rise-delay" as string]: `${i * 80}ms`, transformOrigin: c.kind === "down" ? "center top" : "center bottom" }}
                  />
                </div>
              );
            })}
          </div>
          <figcaption className="mt-2 flex">
            {cols.map((c) => (
              <span key={c.key} className="num flex-1 truncate text-center text-[11px] text-muted-foreground">{c.label}</span>
            ))}
          </figcaption>
          <p className="sr-only">{cols.map((c) => `${c.label} ${c.value}`).join(", ")}</p>
        </figure>
      </div>
    </section>
  );
}
