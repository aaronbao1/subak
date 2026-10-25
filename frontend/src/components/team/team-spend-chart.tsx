"use client";
import { useEffect, useMemo, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, Rectangle, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis,
  type BarShapeProps, type TooltipContentProps,
} from "recharts";
import { X } from "lucide-react";
import type { CostComponent, Forecast, Provenance, SpendingRecord, Team, Unit } from "@/lib/contracts";
import { formatAmount } from "@/lib/format";
import { projectedDays } from "@/components/dashboard/derive";
import { isWeekend, WEEKEND_PATTERN_ID } from "@/components/shared/components";
import { useMounted, usePrefersReducedMotion } from "@/components/shared/motion";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { COMPONENT_COLOR, COMPONENT_LABEL, COMPONENT_ORDER, fmtDate, PROVENANCE_LABEL, ProvenanceBadge } from "./labels";
import { riseAt } from "./count-up";

interface Props {
  team: Team;
  records: SpendingRecord[];
  /** Supplies the dashed projected days after the last recorded one, when the forecast breaks its total down by day. */
  forecast?: Forecast;
  unit: Unit;
  /** Where this card sits in the page's entrance sequence, in ms. The day buttons follow 60ms later. */
  enterAt?: number;
}

/* First paint: each stacked layer rises from the baseline over 900ms, 70ms after the one below it; the dashed
   projected layer goes last (begins at 280ms, ends at 1180ms). After that every re-render paints instantly. */
const BAR_DURATION_MS = 900;
const BAR_STAGGER_MS = 70;
const BAR_SEQUENCE_MS = BAR_STAGGER_MS * COMPONENT_ORDER.length + BAR_DURATION_MS;

type SegmentKey = CostComponent | "projectedBar";

type DayRow = {
  date: string; complete: boolean; projected: boolean; weekend: boolean; total: number;
  /** Projected full-day total on a partial day. */
  projectedFullDay?: number;
  /** Dashed segment height: the whole bar on a projected day, the still-expected remainder on a partial day. */
  projectedBar: number;
  /** The topmost non-zero segment; only that one gets the rounded data end. */
  topKey?: SegmentKey;
} & Record<CostComponent, number>;

const COMPONENT_NOTE: Partial<Record<CostComponent, string>> = {
  included_usage: "Usage covered by the subscription; shown for information",
};

const AXIS_TICK = { fontSize: 11, fill: "var(--muted-foreground)", fontFamily: "var(--font-mono)" };

/** Included usage is informational, not billed: neutral fill with a dashed outline, in the legend and the bars alike. */
const isInformational = (c: CostComponent) => c === "included_usage";

/** Rounded 4px at the data end of the topmost segment only; square everywhere else. 2px surface stroke is the gap. */
function segmentShape(key: SegmentKey) {
  return function Segment(props: BarShapeProps) {
    const { payload, x, y, width, height, fill, fillOpacity, stroke, strokeOpacity, strokeWidth, strokeDasharray } = props;
    if (!height || height <= 0) return <g />;
    const top = (payload as DayRow | undefined)?.topKey === key;
    return (
      <Rectangle
        x={x} y={y} width={width} height={height}
        fill={fill} fillOpacity={fillOpacity}
        stroke={stroke} strokeOpacity={strokeOpacity} strokeWidth={strokeWidth} strokeDasharray={strokeDasharray}
        radius={top ? [4, 4, 0, 0] : 0}
      />
    );
  };
}

/** Daily stacked bars by cost component; projected days follow as dashed outlines. Select a recorded day for its breakdown. */
export function TeamSpendChart({ team, records, forecast, unit, enterAt = 0 }: Props) {
  const [selected, setSelected] = useState<string | undefined>();
  const mounted = useMounted();
  const reduce = usePrefersReducedMotion();
  const rise = mounted ? "animate-rise" : "opacity-0";
  // Recharts animates the columns on first paint only. The one-way flag flips once the sequence is over (or on
  // the first day selection, whichever comes first) so a later selection or resize never re-animates.
  // (A plain ref can't be read during render under this repo's react-hooks/refs rule, hence state.)
  const [firstPaint, setFirstPaint] = useState(true);
  useEffect(() => {
    const t = setTimeout(() => setFirstPaint(false), BAR_SEQUENCE_MS);
    return () => clearTimeout(t);
  }, []);
  const animateBars = firstPaint && !reduce;

  const days = useMemo<DayRow[]>(() => {
    const byDate = new Map<string, DayRow>();
    for (const r of records) {
      let row = byDate.get(r.date);
      if (!row) {
        row = { date: r.date, complete: true, projected: false, weekend: isWeekend(r.date), total: 0, projectedBar: 0, subscription: 0, included_usage: 0, extra_usage: 0, api: 0 };
        byDate.set(r.date, row);
      }
      row[r.component] += r.amount;
      row.total += r.amount;
      if (!r.complete) row.complete = false;
    }
    const completeDates = new Set([...byDate.values()].filter((r) => r.complete).map((r) => r.date));
    for (const d of projectedDays(forecast, completeDates)) {
      const existing = byDate.get(d.date);
      if (existing) {
        existing.projectedFullDay = d.projected;
        existing.projectedBar = Math.max(0, d.projected - existing.total);
      } else {
        byDate.set(d.date, { date: d.date, complete: true, projected: true, weekend: isWeekend(d.date), total: d.projected, projectedBar: d.projected, subscription: 0, included_usage: 0, extra_usage: 0, api: 0 });
      }
    }
    const rows = [...byDate.values()].sort((a, b) => a.date.localeCompare(b.date));
    for (const row of rows) {
      const keys: SegmentKey[] = [...COMPONENT_ORDER, "projectedBar"];
      row.topKey = [...keys].reverse().find((k) => row[k] > 0);
    }
    return rows;
  }, [records, forecast]);
  const projectedCount = days.filter((d) => d.projected).length;
  const weekendDays = days.filter((d) => d.weekend);

  /** Provenance seen per component across the team's records, for the legend. */
  const legendProvenance = useMemo(() => {
    const m = new Map<CostComponent, Set<Provenance>>();
    for (const r of records) {
      if (!m.has(r.component)) m.set(r.component, new Set());
      m.get(r.component)!.add(r.provenance);
    }
    return m;
  }, [records]);

  // Nice tick values so compact labels never collide (e.g. 1,500 and 2,000 both rounding to "$2K").
  const yTicks = useMemo(() => niceTicks(Math.max(0, ...days.map((d) => Math.max(d.total, d.projectedFullDay ?? 0)))), [days]);

  const partialDays = days.filter((d) => !d.complete);
  const recordedDays = days.filter((d) => !d.projected);
  const selectedDay = selected ? days.find((d) => d.date === selected && !d.projected) : undefined;
  const selectedRecords = selected ? records.filter((r) => r.date === selected) : [];
  const toggle = (date: string) => {
    setFirstPaint(false);
    setSelected((cur) => (cur === date ? undefined : date));
  };

  if (days.length === 0) {
    return (
      <section className="rounded-xl border border-border bg-card p-5">
        <h2 className="text-base font-medium">Daily spend</h2>
        <p className="mt-1 text-sm text-muted-foreground">No spending has been recorded for {team.name} yet.</p>
      </section>
    );
  }

  return (
    <section className={cn("rounded-xl border border-border bg-card", rise)} style={riseAt(enterAt)} aria-labelledby="spend-heading">
      <div className="flex flex-col gap-3 p-5 pb-0 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 id="spend-heading" className="text-base font-medium">Daily spend</h2>
          <p className="mt-1 text-xs text-muted-foreground">
            <span className="num">{fmtDate(days[0].date)} – {fmtDate(days[days.length - 1].date, { year: true })}</span>
          </p>
        </div>
        {/* Legend: square swatch per component; provenance and notes live in the swatch's tooltip */}
        <ul className="flex flex-wrap gap-x-4 gap-y-2 text-xs text-muted-foreground sm:justify-end" aria-label="Legend">
          {COMPONENT_ORDER.map((c) => (
            <li key={c} className="inline-flex items-center gap-2" title={legendTitle(c, legendProvenance.get(c))}>
              <span aria-hidden className={cn("size-2 rounded-[2px]", isInformational(c) && "border border-dashed border-muted-foreground")} style={{ background: COMPONENT_COLOR[c] }} />
              <span>{COMPONENT_LABEL[c]}</span>
            </li>
          ))}
          {projectedCount > 0 && (
            <li className="inline-flex items-center gap-2" title="Day-by-day projection from the forecast; nothing recorded yet">
              <span aria-hidden className="size-2 rounded-[2px] border border-dashed border-muted-foreground" />
              <span>Projected</span>
            </li>
          )}
          {partialDays.length > 0 && (
            <li className="inline-flex items-center gap-2" title={`Source incomplete: ${partialDays.map((d) => fmtDate(d.date)).join(", ")}`}>
              <span aria-hidden className="size-2 rounded-[2px] bg-muted-foreground/50" />
              <span>Partial</span>
            </li>
          )}
          {weekendDays.length > 0 && (
            <li className="inline-flex items-center gap-2" title="Saturday and Sunday">
              <span aria-hidden className="size-2 rounded-[2px] border border-border-strong bg-[repeating-linear-gradient(45deg,transparent_0_1px,var(--border-strong)_1px_2px)]" />
              <span>Weekend</span>
            </li>
          )}
        </ul>
      </div>

      <div className="h-64 w-full px-3 pt-4 sm:h-72">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={days}
            margin={{ top: 4, right: 8, left: 0, bottom: 0 }}
            barCategoryGap="30%"
            onClick={(state) => {
              const label = state?.activeLabel;
              if (typeof label !== "string" || days.find((d) => d.date === label)?.projected) return;
              toggle(label);
            }}
            className="cursor-pointer"
          >
            <defs>
              {/* Diagonal hatch for weekends, the same mark the overview chart uses. */}
              <pattern id={WEEKEND_PATTERN_ID} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                <line x1="0" y1="0" x2="0" y2="6" stroke="var(--foreground)" strokeOpacity="0.09" strokeWidth="1.5" />
              </pattern>
            </defs>
            <CartesianGrid vertical={false} stroke="var(--border)" />
            {weekendDays.map((d) => (
              <ReferenceArea key={`w-${d.date}`} x1={d.date} x2={d.date} fill={`url(#${WEEKEND_PATTERN_ID})`} stroke="none" />
            ))}
            <XAxis
              dataKey="date"
              tickFormatter={(v: string) => fmtDate(v)}
              tick={AXIS_TICK}
              tickLine={false}
              axisLine={false}
              interval="preserveStartEnd"
              minTickGap={28}
              tickMargin={8}
            />
            <YAxis
              ticks={yTicks}
              domain={[0, yTicks[yTicks.length - 1]]}
              tickFormatter={(v: number) => formatAmount(v, unit, { compact: true })}
              tick={AXIS_TICK}
              tickLine={false}
              axisLine={false}
              width={48}
            />
            <Tooltip
              cursor={{ fill: "var(--foreground)", fillOpacity: 0.04 }}
              content={(p) => <SpendTooltip {...p} unit={unit} />}
            />
            {COMPONENT_ORDER.map((c, i) => (
              <Bar
                key={c}
                dataKey={c}
                name={COMPONENT_LABEL[c]}
                stackId="day"
                fill={COMPONENT_COLOR[c]}
                stroke={isInformational(c) ? "var(--muted-foreground)" : "var(--card)"}
                strokeOpacity={isInformational(c) ? 0.8 : 1}
                strokeWidth={isInformational(c) ? 1 : 2}
                strokeDasharray={isInformational(c) ? "3 3" : undefined}
                isAnimationActive={animateBars}
                animationBegin={i * BAR_STAGGER_MS}
                animationDuration={BAR_DURATION_MS}
                animationEasing="ease-out"
                maxBarSize={24}
                shape={segmentShape(c)}
              >
                {days.map((d) => {
                  const dimmed = !!selected && selected !== d.date;
                  // Partial days are recorded but known incomplete: a lighter fill, named in the legend and tooltip.
                  const base = d.complete ? 1 : 0.5;
                  return <Cell key={d.date} fillOpacity={dimmed ? base * 0.35 : base} />;
                })}
              </Bar>
            ))}
            {projectedCount > 0 && (
              <Bar
                dataKey="projectedBar" name="Projected" stackId="day"
                fill="var(--muted-foreground)" fillOpacity={0.1}
                stroke="var(--muted-foreground)" strokeOpacity={0.8} strokeWidth={1} strokeDasharray="3 3"
                isAnimationActive={animateBars}
                animationBegin={COMPONENT_ORDER.length * BAR_STAGGER_MS}
                animationDuration={BAR_DURATION_MS}
                animationEasing="ease-out"
                maxBarSize={24}
                shape={segmentShape("projectedBar")}
              >
                {days.map((d) => {
                  const dimmed = !!selected && selected !== d.date;
                  return <Cell key={d.date} fillOpacity={d.projectedBar > 0 ? (dimmed ? 0.04 : 0.1) : 0} strokeOpacity={d.projectedBar > 0 ? (dimmed ? 0.3 : 0.8) : 0} />;
                })}
              </Bar>
            )}
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Keyboard-reachable day selection: one button per recorded day. */}
      <div className={cn("px-5 pt-3", rise)} style={riseAt(enterAt + 60)}>
        <div role="group" aria-label="Select a recorded day" className="flex gap-1 overflow-x-auto pb-1">
          {recordedDays.map((d) => {
            const active = selected === d.date;
            return (
              <button
                key={d.date}
                type="button"
                aria-pressed={active}
                onClick={() => toggle(d.date)}
                title={d.complete ? fmtDate(d.date, { year: true }) : `${fmtDate(d.date, { year: true })} · partial day`}
                className={cn(
                  "num h-6 shrink-0 rounded-md px-1.5 text-[11px] whitespace-nowrap transition-colors duration-300 outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  active ? "bg-brand-soft text-foreground" : "text-muted-foreground hover:bg-popover hover:text-foreground",
                )}
              >
                {fmtDate(d.date)}{!d.complete && <span aria-hidden className="ml-1 font-sans text-muted-foreground">·</span>}
              </button>
            );
          })}
        </div>
      </div>

      <div className="p-5 pt-2">
        {selectedDay && (
          <DayBreakdown day={selectedDay} records={selectedRecords} unit={unit} onClose={() => setSelected(undefined)} />
        )}
      </div>
    </section>
  );
}

function legendTitle(c: CostComponent, provenance?: Set<Provenance>) {
  const parts = [COMPONENT_NOTE[c], provenance?.size ? [...provenance].map((p) => PROVENANCE_LABEL[p]).join(", ") : undefined].filter(Boolean);
  return parts.length ? parts.join(" · ") : undefined;
}

/**
 * Ticks at a 1/2/5 step chosen for 3-6 ticks, with steps in the hundreds (and hundred-thousands) bumped to the
 * next power of ten so every tick formats to a distinct compact label with zero fraction digits.
 */
function niceTicks(max: number): number[] {
  if (max <= 0) return [0, 1];
  const rough = max / 4;
  const pow = 10 ** Math.floor(Math.log10(rough));
  const base = rough / pow;
  let step = (base <= 1 ? 1 : base <= 2 ? 2 : base <= 5 ? 5 : 10) * pow;
  if (step >= 100 && step < 1_000) step = 1_000;
  if (step >= 100_000 && step < 1_000_000) step = 1_000_000;
  const top = Math.ceil(max / step) * step;
  const ticks: number[] = [];
  for (let v = 0; v <= top; v += step) ticks.push(v);
  return ticks;
}

const TOOLTIP = "min-w-48 rounded-md border border-border bg-popover px-3 py-2 text-xs shadow-[0_8px_32px_rgba(0,0,0,0.5)]";

function SpendTooltip({ active, payload, label, unit }: TooltipContentProps & { unit: Unit }) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload as DayRow | undefined;
  if (row?.projected) {
    return (
      <div className={TOOLTIP}>
        <div className="mb-1.5 flex items-baseline justify-between gap-3">
          <span className="num font-medium">{fmtDate(String(label), { year: true })}</span>
          <span className="text-muted-foreground">Projected</span>
        </div>
        <div className="flex justify-between gap-4 font-medium">
          <span>Projected</span><span className="num">{formatAmount(row.total, unit)}</span>
        </div>
        <p className="mt-1 text-muted-foreground">Nothing recorded yet; no component breakdown.</p>
      </div>
    );
  }
  const parts = payload.filter((p) => p.dataKey !== "projectedBar");
  return (
    <div className={TOOLTIP}>
      <div className="mb-1.5 flex items-baseline justify-between gap-3">
        <span className="num font-medium">{fmtDate(String(label), { year: true })}</span>
        {row && !row.complete && <span className="text-muted-foreground">Partial day, recorded so far</span>}
      </div>
      <ul className="space-y-1">
        {[...parts].reverse().map((p) => (
          <li key={String(p.dataKey)} className="flex items-center justify-between gap-4">
            <span className="inline-flex items-center gap-2 text-muted-foreground">
              <span aria-hidden className="size-2 rounded-[2px]" style={{ background: p.color }} />
              {p.name}
            </span>
            <span className="num">{formatAmount(Number(p.value ?? 0), unit)}</span>
          </li>
        ))}
      </ul>
      {row && (
        <div className="mt-1.5 flex justify-between gap-4 border-t border-border pt-1.5 font-medium">
          <span>Total</span><span className="num">{formatAmount(row.total, unit)}</span>
        </div>
      )}
      {row?.projectedFullDay !== undefined && (
        <div className="flex justify-between gap-4 text-muted-foreground">
          <span>Projected full day</span><span className="num">{formatAmount(row.projectedFullDay, unit)}</span>
        </div>
      )}
    </div>
  );
}

/** Breakdown of one recorded day. A divided section inside the panel, not a nested card. */
function DayBreakdown({ day, records, unit, onClose }: { day: DayRow; records: SpendingRecord[]; unit: Unit; onClose: () => void }) {
  const groups = COMPONENT_ORDER.map((c) => ({ component: c, records: records.filter((r) => r.component === c) })).filter((g) => g.records.length > 0);
  return (
    <div className="mt-4 border-t border-border pt-4 text-sm" aria-live="polite">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
            <span className="num font-medium">{fmtDate(day.date, { year: true })}</span>
            <span className="text-xs text-muted-foreground"><span className="num">{formatAmount(day.total, unit)}</span> total</span>
          </div>
          {!day.complete && (
            <div className="mt-0.5 text-xs text-muted-foreground">
              Partial day: the source is incomplete for this date{day.projectedFullDay !== undefined ? <>; projected full day <span className="num">{formatAmount(day.projectedFullDay, unit)}</span></> : ""}
            </div>
          )}
        </div>
        <Button variant="ghost" size="icon-xs" onClick={onClose} aria-label="Close day breakdown" className="-mr-1 text-muted-foreground"><X className="size-4" strokeWidth={1.5} /></Button>
      </div>
      <ul className="mt-3 divide-y divide-border border-t border-border">
        {groups.map(({ component, records: rs }) => {
          const notBilled = rs.some((r) => r.provenance !== "reported_charge");
          return (
            <li key={component} className="grid gap-1 py-2.5 sm:grid-cols-[1fr_auto] sm:items-start sm:gap-4">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span aria-hidden className={cn("size-2 rounded-[2px]", isInformational(component) && "border border-dashed border-muted-foreground")} style={{ background: COMPONENT_COLOR[component] }} />
                  <span className="font-medium">{COMPONENT_LABEL[component]}</span>
                  {[...new Set(rs.map((r) => r.provenance))].map((p) => <ProvenanceBadge key={p} provenance={p} />)}
                  {rs.some((r) => !r.complete) && <span className="text-xs text-muted-foreground">Partial</span>}
                </div>
                <div className="mt-0.5 text-xs text-muted-foreground break-words">
                  {[...new Set(rs.map((r) => `${r.source}${r.provider ? ` · ${r.provider}` : ""}`))].join("; ")}
                </div>
              </div>
              <div className={cn("num sm:text-right", notBilled && "text-muted-foreground")} title={notBilled ? "Not a reported charge" : undefined}>
                {formatAmount(rs.reduce((s, r) => s + r.amount, 0), unit)}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
