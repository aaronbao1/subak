"use client";
import { useCallback, useMemo } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useAppStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import { PageTitle } from "@/components/shared/stat-tile";
import { riseDelay, useMounted } from "@/components/shared/motion";
import {
  applyFilters, buildRows, indexAdjustments, isDefaultFilters, macroBuckets, parseFilters, peopleAffected, projectionTotals,
  serializeFilters, teamImpacts, todayIso, type EvidenceFilters,
} from "./derive";
import { ProjectionStrip } from "./projection-strip";
import { FilterRow } from "./filter-row";
import { EvidenceFeed } from "./evidence-feed";
import { ImpactByTeam } from "./impact-by-team";
import { MacroWatch } from "./macro-watch";
import { PeopleAffected } from "./people-affected";
import { EvidenceSkeleton } from "./skeleton";

const MACRO_WINDOW_DAYS = 14;

/**
 * Why the projections are what they are. Reads `?scope=&effect=&category=&team=` so a team page can link straight
 * into its own evidence; the filters write back to the URL with `replace` so the back button is not spammed.
 */
export function EvidencePage() {
  const { loaded, company, teams, people, context, forecasts, personForecasts, budgets, spending } = useAppStore();
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const mounted = useMounted();

  const filters = useMemo(() => parseFilters(params, teams), [params, teams]);
  const setFilters = useCallback(
    (next: EvidenceFilters) => router.replace(`${pathname}${serializeFilters(next)}`, { scroll: false }),
    [router, pathname],
  );
  const clearFilters = useCallback(() => setFilters({ scope: "all", effect: "all", category: "all", team: undefined }), [setFilters]);

  const unit = company?.budgetUnit ?? budgets[0]?.unit ?? "usd";
  const adjustments = useMemo(() => indexAdjustments(forecasts, personForecasts), [forecasts, personForecasts]);
  const rows = useMemo(() => buildRows(context, teams, people, adjustments), [context, teams, people, adjustments]);
  const filtered = useMemo(() => applyFilters(rows, filters), [rows, filters]);
  // The team panel ignores the team filter itself so every row stays clickable while one team is selected.
  const rowsSansTeam = useMemo(() => applyFilters(rows, { ...filters, team: undefined }), [rows, filters]);

  const totals = useMemo(() => projectionTotals(forecasts, teams, unit), [forecasts, teams, unit]);
  const impacts = useMemo(() => teamImpacts(teams, rowsSansTeam, forecasts, budgets, spending, unit), [teams, rowsSansTeam, forecasts, budgets, spending, unit]);
  const buckets = useMemo(() => macroBuckets(rows, todayIso(), MACRO_WINDOW_DAYS), [rows]);
  const affected = useMemo(() => peopleAffected(filtered, teams), [filtered, teams]);

  if (!loaded) return <EvidenceSkeleton />;

  const enter = (i: number) => ({ className: cn("min-w-0", mounted ? "animate-rise" : "opacity-0"), style: riseDelay(i) });

  return (
    <div className="min-w-0 space-y-6">
      <div {...enter(0)}>
        <PageTitle
          title="Evidence"
          description="What moves the projections beyond the trend: company changes, team plans and what individual people are doing, each with its source."
        />
      </div>

      <div {...enter(1)}>
        <ProjectionStrip totals={totals} />
      </div>

      <div {...enter(2)}>
        <FilterRow filters={filters} teams={teams} onChange={setFilters} shown={filtered.length} total={rows.length} />
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(320px,1fr)]">
        <div className="min-w-0">
          <EvidenceFeed rows={filtered} unit={unit} mounted={mounted} enterAt={180} onClearFilters={clearFilters} filtersActive={!isDefaultFilters(filters)} />
        </div>
        <aside className="min-w-0 space-y-6 lg:sticky lg:top-6 lg:self-start" aria-label="Evidence summary">
          <div {...enter(3)}>
            <ImpactByTeam impacts={impacts} selectedTeam={filters.team} onSelect={(team) => setFilters({ ...filters, team })} hasAnyAdjustments={totals.hasAdjustments} mounted={mounted} />
          </div>
          <div {...enter(4)}>
            <MacroWatch buckets={buckets} windowDays={MACRO_WINDOW_DAYS} />
          </div>
          <div {...enter(5)}>
            <PeopleAffected people={affected} />
          </div>
        </aside>
      </div>
    </div>
  );
}
