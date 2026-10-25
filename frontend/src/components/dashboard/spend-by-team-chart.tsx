"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  CartesianGrid, Line, LineChart, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { Popover } from "@base-ui/react/popover";
import { ChevronLeft, ChevronRight } from "lucide-react";
import type { Period, Team, Unit } from "@/lib/contracts";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { formatAmount, unitNoun } from "@/lib/format";
import { WEEKEND_PATTERN_ID, isWeekend } from "@/components/shared/components";
import { EASE_CSS, ENTER_STAGGER_MS, usePrefersReducedMotion } from "@/components/shared/motion";
import { dateLabel, dayLabel, hasProjectedAmount, projectedKey, teamKey, toTs, type DailyRow } from "./derive";
import { TeamPicker } from "./team-picker";

const HALF_DAY = 43_200_000;
/** Up to two weeks of days get one tick per day with a weekday label; longer ranges fall back to weekly ticks. */
const DAILY_TICK_LIMIT = 14;
/** How much of the history is in view. 0 means everything. */
const ZOOMS = [{ days: 7, label: "Week" }, { days: 28, label: "4 weeks" }, { days: 0, label: "All" }] as const;
type ZoomDays = (typeof ZOOMS)[number]["days"];
/** The categorical palette has 8 slots. Past that, the smallest teams fold into one neutral "Other" line. */
const MAX_LINES = 8;
const OTHER_ID = "__other";
const AXIS_TICK = { fontSize: 11, fill: "var(--muted-foreground)", fontFamily: "var(--font-mono)" };
/*
 * First-paint draw-in (ms). Team lines with rank r (largest spend first) draw left to right from r*60 for 1100;
 * their dashed projections continue from where the recorded line ended for 500 more. Dots pop 300ms each,
 * 40ms per column, as soon as their line has passed them. The weekend hatch, partial and projected areas fade
 * in once the last projection is drawn. Pan, zoom, picker and selection never re-animate; a new dataset does.
 */
const LINE_MS = 1100;
const PROJ_MS = 500;
const DOT_MS = 300;
const DOT_STEP_MS = 40;
const AREAS_MS = 300;
/** Draw phases: lines, then recorded dots, then projected dots, then the reference areas, then settled. */
const PHASE = { lines: 0, dots: 1, projectedDots: 2, areas: 3, done: 4 } as const;
type Phase = (typeof PHASE)[keyof typeof PHASE];
const DOT_POP = "sbt-dot-pop";
const popStyle = (delayMs: number): React.CSSProperties => ({
  transformBox: "fill-box", transformOrigin: "center",
  animation: `${DOT_POP} ${DOT_MS}ms ${EASE_CSS} both`, animationDelay: `${Math.max(0, delayMs)}ms`,
});
const AREA_LABEL = { fontSize: 11, fill: "var(--muted-foreground)", fontFamily: "var(--font-mono)" };

/** A drawn line: a team, or the folded "Other" series which carries the teams it sums. */
interface Series {
  id: string;
  name: string;
  color: string;
  folded?: Team[];
}

export interface SpendByTeamChartProps {
  teams: Team[];
  rows: DailyRow[];
  partialDates: string[];
  unit: Unit;
  selectedId: string | null;
  onSelect: (teamId: string) => void;
  /** Accepted for existing callers; no longer rendered. */
  placeholder?: boolean;
  /** The planning period; the chart opens on it and earlier history sits to the left. */
  period?: Period;
}

/**
 * One line per team. Recorded days are solid with filled dots; projected days are dashed with hollow dots inside
 * a lightly shaded region, so "this is what was spent" and "this is what we expect" never blur. The chart opens
 * on the current period and pans back through history (trackpad swipe, drag, or the arrows) to show growth.
 * With more than eight teams visible, the eight largest by period spend are drawn as themselves and the rest
 * are summed into a neutral dashed "Other" line; hiding a team in the picker lets another take its place.
 * Colors follow the team (`team.color`), so hiding one team never recolors another.
 */
export function SpendByTeamChart({ teams: allTeams, rows: all, partialDates, unit, period, selectedId, onSelect }: SpendByTeamChartProps) {
  const [zoom, setZoom] = useState<ZoomDays>(7);
  /** Teams the reader has unchecked in the picker. Empty means every team is drawn. */
  const [hiddenIds, setHiddenIds] = useState<Set<string>>(() => new Set());
  const visibleTeams = useMemo(() => allTeams.filter((t) => !hiddenIds.has(t.id)), [allTeams, hiddenIds]);

  // Fold beyond eight: rank visible teams by recorded spend inside the planning period (all rows when no period).
  const { drawn, folded } = useMemo(() => {
    if (visibleTeams.length <= MAX_LINES) return { drawn: visibleTeams, folded: [] as Team[] };
    const inPeriod = period ? all.filter((r) => r.date >= period.start && r.date <= period.end) : all;
    const spendOf = new Map(visibleTeams.map((t) => {
      const k = teamKey(t.id);
      return [t.id, inPeriod.reduce((s, r) => s + (typeof r[k] === "number" ? (r[k] as number) : 0), 0)] as const;
    }));
    const top = new Set([...visibleTeams].sort((a, b) => (spendOf.get(b.id) ?? 0) - (spendOf.get(a.id) ?? 0)).slice(0, MAX_LINES).map((t) => t.id));
    // Keep the dataset's own order for the drawn teams so legend order does not jump as teams swap in.
    return { drawn: visibleTeams.filter((t) => top.has(t.id)), folded: visibleTeams.filter((t) => !top.has(t.id)) };
  }, [visibleTeams, all, period]);
  const foldedIds = useMemo(() => new Set(folded.map((t) => t.id)), [folded]);
  const series = useMemo<Series[]>(() => {
    const own: Series[] = drawn.map((t) => ({ id: t.id, name: t.name, color: t.color }));
    return folded.length ? [...own, { id: OTHER_ID, name: `Other (${folded.length} teams)`, color: "var(--chart-other)", folded }] : own;
  }, [drawn, folded]);
  /** Draw order for the first paint: the largest team by recorded spend in the period draws first; Other draws last. */
  const drawRank = useMemo(() => {
    const inPeriod = period ? all.filter((r) => r.date >= period.start && r.date <= period.end) : all;
    const spendOf = (s: Series) => s.folded ? -1 : inPeriod.reduce((sum, r) => { const v = r[teamKey(s.id)]; return sum + (typeof v === "number" ? v : 0); }, 0);
    const ordered = [...series].sort((a, b) => spendOf(b) - spendOf(a));
    return new Map(ordered.map((s, i) => [s.id, i]));
  }, [series, all, period]);

  // First-paint draw-in, run once per dataset. `phase` gates the dots and areas; Recharts draws the lines.
  const reduce = usePrefersReducedMotion();
  const [dataset, setDataset] = useState(allTeams);
  const [phase, setPhase] = useState<Phase>(PHASE.lines);
  if (dataset !== allTeams) { setDataset(allTeams); setPhase(PHASE.lines); }
  // Under reduced motion nothing is gated: lines, dots and areas render in their end state at once.
  const animating = phase < PHASE.done && !reduce;
  const lastBegin = Math.max(0, series.length - 1) * ENTER_STAGGER_MS;
  useEffect(() => {
    if (phase === PHASE.done || reduce) return;
    const areasAt = lastBegin + LINE_MS + PROJ_MS;
    const timers = [
      setTimeout(() => setPhase(PHASE.dots), LINE_MS),
      setTimeout(() => setPhase(PHASE.projectedDots), LINE_MS + PROJ_MS),
      setTimeout(() => setPhase(PHASE.areas), areasAt),
      setTimeout(() => setPhase(PHASE.done), areasAt + AREAS_MS + DOT_MS),
    ];
    return () => timers.forEach(clearTimeout);
    // Restart only when the dataset changes; the stagger is fixed at first paint.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dataset, reduce]);
  /** Any interaction settles the chart so pans, zooms and picks render instantly, even mid-sequence. */
  const settle = useCallback(() => setPhase(PHASE.done), []);
  /** Rows with the folded teams summed under the Other keys; untouched when nothing is folded. */
  const plotAll = useMemo(() => {
    if (folded.length === 0) return all;
    return all.map((r) => {
      let rec: number | null = null, proj: number | null = null;
      for (const t of folded) {
        const v = r[teamKey(t.id)]; if (typeof v === "number") rec = (rec ?? 0) + v;
        const pv = r[projectedKey(t.id)]; if (typeof pv === "number") proj = (proj ?? 0) + pv;
      }
      return { ...r, [teamKey(OTHER_ID)]: rec, [projectedKey(OTHER_ID)]: proj };
    });
  }, [all, folded]);

  const onHiddenChange = useCallback((next: Set<string>) => {
    settle();
    setHiddenIds(next);
    // Hiding the selected team would leave the breakdown panel pointing at a line that is no longer drawn.
    if (selectedId !== null && next.has(selectedId)) onSelect(selectedId);
  }, [selectedId, onSelect, settle]);
  /** Days between the window's right edge and the latest row; 0 shows the current period. */
  const [offset, setOffset] = useState(0);
  const plotRef = useRef<HTMLDivElement>(null);
  const wheelAcc = useRef(0);
  const drag = useRef<{ x: number; offset: number; moved: boolean } | null>(null);
  /** Set on pointer-up so the click that follows a drag does not also select a team. */
  const dragMoved = useRef(false);

  // The period can run weeks past the latest data (a quarter viewed in October). Open on the latest day that has
  // recorded or projected values, not on empty days at the end of the period.
  const plotSeries = useMemo(() => {
    let last = plotAll.length - 1;
    while (last > 0 && plotAll[last].kind === "empty") last--;
    return plotAll.slice(0, last + 1);
  }, [plotAll]);
  const windowDays = zoom === 0 ? plotSeries.length : Math.min(zoom, plotSeries.length);
  const maxOffset = Math.max(0, plotSeries.length - windowDays);
  const off = Math.min(offset, maxOffset);
  const endIdx = plotSeries.length - 1 - off;
  const rows = useMemo(() => plotSeries.slice(Math.max(0, endIdx - windowDays + 1), endIdx + 1), [plotSeries, endIdx, windowDays]);
  const canBack = off < maxOffset;
  const canForward = off > 0;
  const clampOffset = useCallback((o: number) => Math.max(0, Math.min(maxOffset, o)), [maxOffset]);
  const pan = useCallback((days: number) => { settle(); setOffset((o) => clampOffset(Math.min(o, maxOffset) + days)); }, [clampOffset, maxOffset, settle]);
  const changeZoom = useCallback((z: ZoomDays) => { settle(); setZoom(z); }, [settle]);
  const pxPerDay = () => (plotRef.current?.clientWidth ?? 600) / Math.max(1, windowDays);
  // Horizontal trackpad swipe (or shift+wheel) pans; vertical wheel keeps scrolling the page.
  const onWheel = (e: React.WheelEvent) => {
    const dx = e.shiftKey && Math.abs(e.deltaX) < Math.abs(e.deltaY) ? e.deltaY : e.deltaX;
    if (!dx) return;
    wheelAcc.current += dx;
    const step = Math.max(8, pxPerDay());
    const days = Math.trunc(wheelAcc.current / step);
    if (days !== 0) { wheelAcc.current -= days * step; pan(-days); }
  };
  const onPointerDown = (e: React.PointerEvent) => { if (e.button === 0) drag.current = { x: e.clientX, offset: off, moved: false }; };
  const onPointerMove = (e: React.PointerEvent) => {
    if (!drag.current) return;
    const days = Math.round((e.clientX - drag.current.x) / pxPerDay());
    if (days !== 0) { drag.current.moved = true; settle(); }
    setOffset(clampOffset(drag.current.offset + days));
  };
  const onPointerUp = () => { dragMoved.current = drag.current?.moved ?? false; drag.current = null; };
  const inPeriod = period && rows.length > 0 && rows[0].date >= period.start && rows[rows.length - 1].date <= period.end;
  const rangeLabel = rows.length ? `${dateLabel(rows[0].ts)} – ${dateLabel(rows[rows.length - 1].ts)}` : "";

  const domain = useMemo<[number, number] | undefined>(() => {
    if (rows.length === 0) return undefined;
    return [rows[0].ts - HALF_DAY, rows[rows.length - 1].ts + HALF_DAY];
  }, [rows]);

  const daily = rows.length <= DAILY_TICK_LIMIT;
  const ticks = useMemo(() => {
    if (rows.length === 0) return [];
    if (daily) return rows.map((r) => r.ts);
    const step = Math.max(1, Math.ceil(rows.length / 7));
    const out = rows.filter((_, i) => i % step === 0).map((r) => r.ts);
    const last = rows[rows.length - 1].ts;
    if (out[out.length - 1] !== last) out.push(last);
    return out;
  }, [rows, daily]);

  const weekendTs = useMemo(() => rows.filter((r) => isWeekend(r.date)).map((r) => r.ts), [rows]);
  const projectedRows = useMemo(() => rows.filter(r => series.some(s => hasProjectedAmount(r, s.id))), [rows, series]);
  const projectedStart = projectedRows[0]?.ts;
  const projectedDays = projectedRows.length;
  const hasProjection = projectedStart !== undefined;
  /** Index of the first projected row, so projected dots pop from the boundary rather than from the chart's left edge. */
  const projectedIdx0 = useMemo(() => Math.max(0, rows.findIndex(r => r.ts === projectedStart)), [rows, projectedStart]);
  const showDots = daily && (!animating || phase >= PHASE.dots);
  const showProjectedDots = daily && (!animating || phase >= PHASE.projectedDots);
  const tickLabel = (v: number) => (daily ? dayLabel(v) : dateLabel(v));

  const dimming = selectedId !== null;
  const noun = unitNoun(unit);
  const select = (s: Series) => { if (!s.folded && !dragMoved.current) onSelect(s.id); };

  return (
    <section className="flex min-w-0 flex-col rounded-xl border border-border bg-card" aria-label={`Daily ${noun} by team`}>
      {/* Dot pop and the reference-area fade, scoped to this chart. The global reduced-motion rule zeroes both. */}
      <style>{`@keyframes ${DOT_POP}{from{opacity:0;transform:scale(0)}to{opacity:1;transform:scale(1)}}
.sbt-plot .recharts-reference-area,.sbt-plot .recharts-reference-line{transition:opacity ${AREAS_MS}ms ${EASE_CSS}}
.sbt-plot.sbt-areas-pending .recharts-reference-area,.sbt-plot.sbt-areas-pending .recharts-reference-line{opacity:0}`}</style>
      <header className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2 px-5 pt-5">
        <div className="min-w-0">
          <h2 className="text-base font-medium">Daily {noun} by team</h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            <span className="num">{rangeLabel}</span>
            {inPeriod && period?.label && <span> · {period.label}</span>}
          </p>
        </div>
        <div className="flex items-center gap-1.5">
          {allTeams.length > 1 && <TeamPicker teams={allTeams} hiddenIds={hiddenIds} onChange={onHiddenChange} foldedIds={foldedIds} />}
          <div className="flex items-center rounded-md bg-popover p-0.5" role="group" aria-label="Range">
            {ZOOMS.map((z) => (
              <button
                key={z.label} type="button" onClick={() => changeZoom(z.days)} aria-pressed={zoom === z.days}
                className={cn(
                  "relative h-7 rounded-sm px-2.5 text-xs text-muted-foreground transition-colors duration-300 hover:text-foreground",
                  zoom === z.days && "bg-card text-foreground",
                )}
              >
                {z.label}
              </button>
            ))}
          </div>
          {zoom !== 0 && (
            <div className="flex items-center">
              <button type="button" onClick={() => pan(windowDays)} disabled={!canBack} aria-label="Earlier" className="rounded-md p-1.5 text-muted-foreground transition-colors duration-300 hover:bg-popover hover:text-foreground disabled:opacity-50 disabled:hover:bg-transparent">
                <ChevronLeft className="size-4" strokeWidth={1.5} />
              </button>
              <button type="button" onClick={() => pan(-windowDays)} disabled={!canForward} aria-label="Later" className="rounded-md p-1.5 text-muted-foreground transition-colors duration-300 hover:bg-popover hover:text-foreground disabled:opacity-50 disabled:hover:bg-transparent">
                <ChevronRight className="size-4" strokeWidth={1.5} />
              </button>
              {canForward && (
                <button type="button" onClick={() => { settle(); setOffset(0); }} className="ml-0.5 h-7 rounded-md px-2 text-xs text-muted-foreground transition-colors duration-300 hover:bg-popover hover:text-foreground">
                  Today
                </button>
              )}
            </div>
          )}
        </div>
      </header>

      <div className="px-3 pt-4">
        {plotAll.length === 0 ? (
          <div className="flex h-64 items-center justify-center text-sm text-muted-foreground">No spending recorded yet.</div>
        ) : series.length === 0 ? (
          <div className="flex h-64 flex-col items-center justify-center gap-3 text-sm text-muted-foreground md:h-72">
            <span>No teams selected.</span>
            <button type="button" onClick={() => onHiddenChange(new Set())} className="h-8 rounded-md border border-border bg-popover px-3 text-xs text-foreground transition-colors duration-300 hover:border-border-strong">
              Show all teams
            </button>
          </div>
        ) : (
          <div
            ref={plotRef} title={maxOffset > 0 ? "Swipe or drag sideways for earlier weeks" : undefined} className={cn("sbt-plot h-64 w-full touch-pan-y select-none rounded-md focus-visible:ring-2 focus-visible:ring-ring md:h-72", maxOffset > 0 && "cursor-grab active:cursor-grabbing", animating && phase < PHASE.areas && "sbt-areas-pending")}
            onWheel={onWheel} onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp} onPointerLeave={onPointerUp}
          >
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={rows} margin={{ top: 16, right: 16, bottom: 0, left: 0 }}>
                <defs>
                  {/* Diagonal hatch for weekends: distinct from the flat shading used for partial and projected days. */}
                  <pattern id={WEEKEND_PATTERN_ID} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                    <line x1="0" y1="0" x2="0" y2="6" stroke="var(--foreground)" strokeOpacity="0.09" strokeWidth="1.5" />
                  </pattern>
                </defs>
                <CartesianGrid vertical={false} stroke="var(--border)" />
                {/* Weekend hatch; explained by its legend swatch, not a label on the plot. */}
                {weekendTs.map((ts) => (
                  <ReferenceArea key={`w-${ts}`} x1={ts - HALF_DAY} x2={ts + HALF_DAY} fill={`url(#${WEEKEND_PATTERN_ID})`} stroke="none" />
                ))}
                <XAxis
                  dataKey="ts" type="number" scale="time" domain={domain} ticks={ticks}
                  tickFormatter={tickLabel} tickLine={false} axisLine={false}
                  tick={AXIS_TICK} minTickGap={12} tickMargin={8}
                />
                <YAxis
                  width={52} tickLine={false} axisLine={false} tickCount={4}
                  tickFormatter={(v: number) => formatAmount(v, unit, { compact: true })}
                  tick={AXIS_TICK}
                />
                {/* Projected region: shaded, separated from recorded days by a hairline. */}
                {hasProjection && domain && (
                  <>
                    <ReferenceArea
                      x1={projectedStart - HALF_DAY} x2={domain[1]} fill="var(--foreground)" fillOpacity={0.035} stroke="none"
                      label={{ value: "Projected", position: "insideTop", ...AREA_LABEL }}
                    />
                    <ReferenceLine x={projectedStart - HALF_DAY} stroke="var(--border-strong)" strokeDasharray="3 3" />
                  </>
                )}
                {partialDates.map((d) => {
                  const ts = toTs(d);
                  return (
                    <ReferenceArea key={d} x1={ts - HALF_DAY} x2={ts + HALF_DAY} fill="var(--foreground)" fillOpacity={0.045} stroke="none" />
                  );
                })}
                <Tooltip
                  cursor={{ stroke: "var(--border-strong)" }}
                  content={({ active, payload, label }) => {
                    if (!active || !payload?.length) return null;
                    const row = payload[0]?.payload as DailyRow | undefined;
                    if (!row) return null;
                    const isProjected = row.kind === "projected";
                    const items = series
                      .map((s) => {
                        const recorded = row[teamKey(s.id)];
                        const projected = row[projectedKey(s.id)];
                        // On a partial day both exist: recorded so far and the projected full-day total.
                        const value = typeof recorded === "number" ? recorded : typed(projected);
                        if (value === undefined) return null;
                        const fullDay = row.partial && typeof recorded === "number" && typeof projected === "number" ? projected : undefined;
                        return { s, value, projected: typeof recorded !== "number", fullDay };
                      })
                      .filter((x): x is { s: Series; value: number; projected: boolean; fullDay: number | undefined } => x !== null)
                      .sort((a, b) => b.value - a.value);
                    if (items.length === 0) return null;
                    const mixed = items.some(i => i.projected) && items.some(i => !i.projected);
                    const total = items.reduce((s, i) => s + i.value, 0);
                    const fullDayTotal = row.partial && items.every((i) => i.fullDay !== undefined) ? items.reduce((s, i) => s + (i.fullDay ?? 0), 0) : undefined;
                    return (
                      <div className="min-w-48 rounded-md border border-border bg-popover px-3 py-2 font-mono text-xs text-popover-foreground">
                        <div className="mb-1.5 flex items-center justify-between gap-3">
                          <span className="text-foreground">{dayLabel(Number(label), { month: true })}</span>
                          <span className="text-muted-foreground">
                            {mixed ? "recorded + projected" : isProjected ? "projected" : row.partial ? "partial day" : "recorded"}
                          </span>
                        </div>
                        {row.partial && !isProjected && (
                          <div className="mb-1 flex justify-between gap-4 text-[11px] text-muted-foreground">
                            <span>so far</span><span>full day, projected</span>
                          </div>
                        )}
                        <ul className="space-y-1">
                          {items.map(({ s, value, projected, fullDay }) => (
                            <li key={s.id} className={cn(dimming && s.id !== selectedId && "opacity-70")}>
                              <div className="flex items-center justify-between gap-4">
                                <span className="flex items-center gap-1.5 text-muted-foreground">
                                  <LineKey color={s.color} dashed={projected || !!s.folded} />
                                  {s.name}
                                </span>
                                <span className="num flex items-center gap-2 text-right text-foreground">
                                  {formatAmount(value, unit, { compact: true })}
                                  {fullDay !== undefined && (
                                    <span className="flex items-center gap-1 text-muted-foreground">
                                      <LineKey color={s.color} dashed />
                                      {formatAmount(fullDay, unit, { compact: true })}
                                    </span>
                                  )}
                                </span>
                              </div>
                              {s.folded && (
                                <div className="mt-0.5 pl-5 text-[11px] leading-snug text-muted-foreground">{foldedList(s.folded)}</div>
                              )}
                            </li>
                          ))}
                        </ul>
                        {items.length > 1 && (
                          <div className="mt-1.5 flex justify-between gap-4 border-t border-border pt-1.5">
                            <span className="text-muted-foreground">{isProjected ? "Projected total" : "Total"}</span>
                            <span className="num flex gap-2 text-right text-foreground">
                              {formatAmount(total, unit, { compact: true })}
                              {fullDayTotal !== undefined && <span>{formatAmount(fullDayTotal, unit, { compact: true })}</span>}
                            </span>
                          </div>
                        )}
                      </div>
                    );
                  }}
                />
                {/* Wide invisible stroke under each team line so a click anywhere along it (not just on a dot) selects the team. */}
                {series.filter((s) => !s.folded).map((s) => (
                  <Line
                    key={`hit-${s.id}`} type="monotone" dataKey={teamKey(s.id)} name={s.name}
                    stroke={s.color} strokeWidth={16} strokeOpacity={0} strokeLinecap="round" strokeLinejoin="round"
                    dot={false} activeDot={false} connectNulls={false} isAnimationActive={false}
                    tooltipType="none" legendType="none" style={{ cursor: "pointer" }}
                    onClick={() => select(s)}
                  />
                ))}
                {series.map((s) => {
                  const selected = s.id === selectedId;
                  const dim = dimming && !selected;
                  const clickable = !s.folded;
                  const begin = (drawRank.get(s.id) ?? 0) * ENTER_STAGGER_MS;
                  return (
                    <Line
                      key={s.id} type="monotone" dataKey={teamKey(s.id)} name={s.name}
                      stroke={s.color} strokeWidth={selected ? 2.5 : 2} strokeOpacity={dim ? 0.2 : 0.95}
                      strokeDasharray={s.folded ? "6 4" : undefined}
                      strokeLinecap="round" strokeLinejoin="round"
                      dot={showDots ? (props) => {
                        const { key, cx, cy, index } = props as { key?: React.Key | null; cx?: number; cy?: number; index?: number };
                        const k = key ?? undefined;
                        if (cx === undefined || cy === undefined) return <g key={k} />;
                        return (
                          <circle
                            key={k} cx={cx} cy={cy} r={4} fill={s.color} fillOpacity={dim ? 0.2 : 1} stroke="var(--card)" strokeWidth={2}
                            style={animating ? popStyle(begin + (index ?? 0) * DOT_STEP_MS) : undefined}
                          />
                        );
                      } : false}
                      connectNulls={false}
                      isAnimationActive={animating ? "auto" : false} animationBegin={begin} animationDuration={LINE_MS} animationEasing="ease-out"
                      style={{ cursor: clickable ? "pointer" : "default" }}
                      onClick={() => select(s)}
                      activeDot={{
                        r: selected ? 5 : 4, strokeWidth: 2, stroke: "var(--card)", fill: s.color,
                        fillOpacity: dim ? 0.2 : 1, cursor: clickable ? "pointer" : "default",
                        onClick: () => select(s),
                      }}
                    />
                  );
                })}
                {hasProjection && series.map((s) => {
                  const selected = s.id === selectedId;
                  const dim = dimming && !selected;
                  const clickable = !s.folded;
                  const begin = (drawRank.get(s.id) ?? 0) * ENTER_STAGGER_MS;
                  return (
                    <Line
                      key={`p-${s.id}`} type="monotone" dataKey={projectedKey(s.id)} name={`${s.name} (projected)`}
                      stroke={s.color} strokeWidth={selected ? 2.5 : 2} strokeOpacity={dim ? 0.15 : 0.7} strokeDasharray="5 4"
                      strokeLinecap="round" strokeLinejoin="round"
                      dot={(props) => {
                        const { key, cx, cy, index, payload } = props as { key?: React.Key | null; cx?: number; cy?: number; index?: number; payload?: DailyRow };
                        const k = key ?? undefined;
                        // The anchor point on the last recorded day already has a solid dot.
                        // Hollow dots only where the value is a projection: projected days and the partial day's full-day total.
                        const show = payload && hasProjectedAmount(payload, s.id);
                        if (!showProjectedDots || !show || cx === undefined || cy === undefined) return <g key={k} />;
                        return (
                          <circle
                            key={k} cx={cx} cy={cy} r={4} fill="var(--card)" stroke={s.color} strokeOpacity={dim ? 0.2 : 0.9} strokeWidth={2}
                            style={animating ? popStyle(begin + ((index ?? 0) - projectedIdx0) * DOT_STEP_MS) : undefined}
                          />
                        );
                      }}
                      connectNulls={false}
                      isAnimationActive={animating ? "auto" : false} animationBegin={begin + LINE_MS} animationDuration={PROJ_MS} animationEasing="ease-out"
                      style={{ cursor: clickable ? "pointer" : "default" }}
                      onClick={() => select(s)}
                      activeDot={{
                        r: selected ? 5 : 4, strokeWidth: 2, stroke: s.color, fill: "var(--card)",
                        strokeOpacity: dim ? 0.2 : 1, cursor: clickable ? "pointer" : "default",
                        onClick: () => select(s),
                      }}
                    />
                  );
                })}
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Legends only: what each mark means is a swatch, and the detail sits in each swatch's tooltip. */}
      <footer className="flex flex-wrap items-center gap-x-4 gap-y-1.5 px-5 pb-5 pt-3">
        <EncodingLegend
          hasProjection={hasProjection} projectedDays={projectedDays}
          weekend={weekendTs.length > 0} partialDates={partialDates}
        />
        <ChartLegend series={series} selectedId={selectedId} onSelect={onSelect} />
      </footer>
    </section>
  );
}

const typed = (v: unknown) => (typeof v === "number" ? v : undefined);

/** "Design, Legal, Ops +4 more" for the folded teams. */
function foldedList(teams: Team[]): string {
  const shown = teams.slice(0, 4).map((t) => t.name);
  const rest = teams.length - shown.length;
  return `${shown.join(", ")}${rest > 0 ? ` +${rest} more` : ""}`;
}

/** Short stroke of the series color, the way the line is drawn; dashed when the value is projected or folded. */
function LineKey({ color, dashed }: { color: string; dashed?: boolean }) {
  return (
    <svg width="12" height="4" viewBox="0 0 12 4" aria-hidden className="shrink-0">
      <line x1="0" y1="2" x2="12" y2="2" stroke={color} strokeWidth="2" strokeLinecap="round" strokeDasharray={dashed ? "3 2" : undefined} />
    </svg>
  );
}

/** Mark key in neutral ink (recorded, projected, partial, weekend), so it reads independently of team colors. */
function EncodingLegend({ hasProjection, projectedDays, weekend, partialDates }: { hasProjection: boolean; projectedDays: number; weekend: boolean; partialDates: string[] }) {
  const partialTitle = `Partial ${partialDates.length === 1 ? "day" : "days"} (${partialDates.map(dateLabel).join(", ")}): some sources have not reported yet`;
  return (
    <ul className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground" aria-label="Chart key">
      <li className="flex items-center gap-1.5" title="Recorded usage">
        <svg width="22" height="10" viewBox="0 0 22 10" aria-hidden><line x1="1" y1="5" x2="21" y2="5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /><circle cx="11" cy="5" r="4" fill="currentColor" stroke="var(--card)" strokeWidth="2" /></svg>
        Recorded
      </li>
      {hasProjection && (
        <li className="flex items-center gap-1.5" title={`Dashed lines and hollow dots are projections (${projectedDays} ${projectedDays === 1 ? "day" : "days"}), not recorded usage`}>
          <svg width="22" height="10" viewBox="0 0 22 10" aria-hidden><line x1="1" y1="5" x2="21" y2="5" stroke="currentColor" strokeOpacity="0.7" strokeWidth="2" strokeDasharray="4 3" strokeLinecap="round" /><circle cx="11" cy="5" r="3.5" fill="var(--card)" stroke="currentColor" strokeWidth="2" /></svg>
          Projected
        </li>
      )}
      {partialDates.length > 0 && (
        <li className="flex items-center gap-1.5" title={partialTitle}>
          <span className="size-2.5 shrink-0 rounded-sm bg-foreground/15" aria-hidden />
          Partial
          <span className="sr-only">{partialTitle}</span>
        </li>
      )}
      {weekend && (
        <li className="flex items-center gap-1.5" title="Weekends; usage is usually lower">
          <svg width="10" height="10" viewBox="0 0 10 10" className="shrink-0 rounded-sm" aria-hidden>
            <rect width="10" height="10" fill="var(--foreground)" fillOpacity="0.04" />
            <path d="M-2 4 L4 -2 M-2 9 L9 -2 M3 12 L12 3 M8 12 L12 8" stroke="var(--foreground)" strokeOpacity="0.35" strokeWidth="1.25" />
          </svg>
          Weekend
        </li>
      )}
    </ul>
  );
}

const CHIP = "flex h-6 items-center gap-1.5 rounded-md border border-transparent px-2 text-xs text-foreground transition-colors duration-300 hover:bg-popover";

/** Team chips with square swatches. The Other chip selects nothing; it opens a list of the teams it sums. */
function ChartLegend({ series, selectedId, onSelect }: { series: Series[]; selectedId: string | null; onSelect: (id: string) => void }) {
  return (
    <ul className="flex max-h-16 flex-wrap gap-1 overflow-y-auto sm:ml-auto" aria-label="Teams">
      {series.map((s) => {
        const selected = s.id === selectedId;
        const dim = selectedId !== null && !selected;
        const swatch = (
          <span
            className={cn("size-2 shrink-0 rounded-sm", s.folded && "border border-dashed bg-transparent")}
            style={s.folded ? { borderColor: s.color, opacity: dim ? 0.35 : 1 } : { background: s.color, opacity: dim ? 0.35 : 1 }}
            aria-hidden
          />
        );
        if (s.folded) {
          return (
            <li key={s.id}>
              <Popover.Root>
                <Popover.Trigger className={cn(CHIP, "data-popup-open:border-border data-popup-open:bg-popover", dim && "text-muted-foreground")} aria-label={`${s.name}: which teams are summed`} title={`The ${MAX_LINES} largest teams by spend are drawn; the rest are summed here`}>
                  {swatch}
                  {s.name}
                </Popover.Trigger>
                <Popover.Portal>
                  <Popover.Positioner side="top" align="end" sideOffset={6} className="isolate z-50">
                    <Popover.Popup className="w-56 rounded-lg border border-border bg-popover p-1 text-popover-foreground shadow-[0_8px_32px_rgba(0,0,0,0.5)] duration-150 data-open:animate-in data-open:fade-in-0 data-closed:animate-out data-closed:fade-out-0">
                      <p className="eyebrow px-2 pb-1 pt-1.5">Summed into Other</p>
                      <ul className="max-h-56 overflow-y-auto">
                        {s.folded.map((t) => (
                          <li key={t.id} className="flex items-center gap-2 rounded-md px-2 py-1 text-xs">
                            <span className="size-2 shrink-0 rounded-sm" style={{ background: t.color }} aria-hidden />
                            <span className="truncate">{t.name}</span>
                          </li>
                        ))}
                      </ul>
                      <p className="px-2 pb-1.5 pt-1 text-[11px] text-muted-foreground">Hide a team to swap one in.</p>
                    </Popover.Popup>
                  </Popover.Positioner>
                </Popover.Portal>
              </Popover.Root>
            </li>
          );
        }
        return (
          <li key={s.id}>
            <button
              type="button" onClick={() => onSelect(s.id)} aria-pressed={selected}
              className={cn(CHIP, selected && "border-border bg-popover font-medium", dim && "text-muted-foreground")}
            >
              {swatch}
              {s.name}
            </button>
          </li>
        );
      })}
    </ul>
  );
}

export function SpendByTeamChartSkeleton() {
  return (
    <section className="rounded-xl border border-border bg-card">
      <div className="flex items-center justify-between px-5 pt-5">
        <Skeleton className="h-4 w-36" />
        <Skeleton className="h-3 w-48" />
      </div>
      <div className="px-5 pt-4"><Skeleton className="h-64 w-full md:h-72" /></div>
      <div className="flex gap-1.5 px-5 pb-5 pt-3">
        <Skeleton className="h-6 w-20 rounded-md" />
        <Skeleton className="h-6 w-16 rounded-md" />
        <Skeleton className="h-6 w-24 rounded-md" />
      </div>
    </section>
  );
}
