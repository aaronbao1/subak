"use client";
import { useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis, type TooltipContentProps } from "recharts";
import { AlertTriangle, X } from "lucide-react";
import type { CostComponent, Provenance, SpendingRecord, Team, Unit } from "@/lib/contracts";
import { formatAmount } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { COMPONENT_COLOR_VAR, COMPONENT_LABEL, COMPONENT_ORDER, fmtDate, ProvenanceBadge } from "./labels";

interface Props {
  team: Team;
  records: SpendingRecord[];
  unit: Unit;
}

type DayRow = { date: string; complete: boolean; total: number } & Record<CostComponent, number>;

/**
 * Component colors are scoped here (validated categorical slots 1-4, light and dark stepped separately).
 * The theme's --chart-1..5 tokens are grayscale and fail the chroma floor for four stacked series.
 */
const SCOPED_STYLE = `
.team-spend-chart{--comp-subscription:#2a78d6;--comp-included:#1baf7a;--comp-extra:#eda100;--comp-api:#eb6834}
.dark .team-spend-chart{--comp-subscription:#3987e5;--comp-included:#199e70;--comp-extra:#c98500;--comp-api:#d95926}
`;

/** Daily stacked bars by cost component. Click a day for the breakdown with provenance and source. */
export function TeamSpendChart({ team, records, unit }: Props) {
  const [selected, setSelected] = useState<string | undefined>();

  const days = useMemo<DayRow[]>(() => {
    const byDate = new Map<string, DayRow>();
    for (const r of records) {
      let row = byDate.get(r.date);
      if (!row) {
        row = { date: r.date, complete: true, total: 0, subscription: 0, included_usage: 0, extra_usage: 0, api: 0 };
        byDate.set(r.date, row);
      }
      row[r.component] += r.amount;
      row.total += r.amount;
      if (!r.complete) row.complete = false;
    }
    return [...byDate.values()].sort((a, b) => a.date.localeCompare(b.date));
  }, [records]);

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
  const yTicks = useMemo(() => niceTicks(Math.max(0, ...days.map((d) => d.total))), [days]);

  const partialDays = days.filter((d) => !d.complete);
  const selectedDay = selected ? days.find((d) => d.date === selected) : undefined;
  const selectedRecords = selected ? records.filter((r) => r.date === selected) : [];

  if (days.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Daily spend</CardTitle>
          <CardDescription>No spending has been recorded for {team.name} yet.</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card className="team-spend-chart">
      <style dangerouslySetInnerHTML={{ __html: SCOPED_STYLE }} />
      <CardHeader>
        <CardTitle>Daily spend</CardTitle>
        <CardDescription>
          {fmtDate(days[0].date)} – {fmtDate(days[days.length - 1].date, { year: true })}, stacked by cost component. Click a day for its breakdown.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={days}
              margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
              barCategoryGap="25%"
              onClick={(state) => {
                const label = state?.activeLabel;
                if (typeof label === "string") setSelected((cur) => (cur === label ? undefined : label));
              }}
              className="cursor-pointer"
            >
              <CartesianGrid vertical={false} stroke="var(--border)" />
              <XAxis
                dataKey="date"
                tickFormatter={(v: string) => fmtDate(v)}
                tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
                tickLine={false}
                axisLine={{ stroke: "var(--border)" }}
                interval="preserveStartEnd"
                minTickGap={24}
              />
              <YAxis
                ticks={yTicks}
                domain={[0, yTicks[yTicks.length - 1]]}
                tickFormatter={(v: number) => formatAmount(v, unit, { compact: true })}
                tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
                tickLine={false}
                axisLine={false}
                width={52}
              />
              <Tooltip
                cursor={{ fill: "var(--muted)", fillOpacity: 0.6 }}
                content={(p) => <SpendTooltip {...p} unit={unit} />}
              />
              {COMPONENT_ORDER.map((c) => (
                <Bar
                  key={c}
                  dataKey={c}
                  name={COMPONENT_LABEL[c]}
                  stackId="day"
                  fill={COMPONENT_COLOR_VAR[c]}
                  stroke="var(--card)"
                  strokeWidth={1.5}
                  isAnimationActive={false}
                  maxBarSize={28}
                >
                  {days.map((d) => (
                    <Cell
                      key={d.date}
                      fillOpacity={d.complete ? (selected && selected !== d.date ? 0.55 : 1) : (selected && selected !== d.date ? 0.25 : 0.4)}
                      strokeDasharray={d.complete ? undefined : "3 2"}
                      stroke={d.complete ? "var(--card)" : "var(--muted-foreground)"}
                    />
                  ))}
                </Bar>
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Legend with a provenance badge per component */}
        <ul className="flex flex-wrap gap-x-4 gap-y-2 text-xs" aria-label="Legend">
          {COMPONENT_ORDER.map((c) => (
            <li key={c} className="flex items-center gap-1.5">
              <span aria-hidden className="size-2.5 rounded-[2px]" style={{ background: COMPONENT_COLOR_VAR[c] }} />
              <span>{COMPONENT_LABEL[c]}</span>
              {[...(legendProvenance.get(c) ?? [])].map((p) => <ProvenanceBadge key={p} provenance={p} />)}
            </li>
          ))}
        </ul>

        {partialDays.length > 0 && (
          <p className="flex items-start gap-1.5 text-xs text-muted-foreground">
            <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
            <span>
              Faded, dashed bars are partial days: the source is known to be incomplete for{" "}
              {partialDays.map((d) => fmtDate(d.date)).join(", ")}.
            </span>
          </p>
        )}

        {selectedDay && (
          <DayBreakdown day={selectedDay} records={selectedRecords} unit={unit} onClose={() => setSelected(undefined)} />
        )}
      </CardContent>
    </Card>
  );
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

function SpendTooltip({ active, payload, label, unit }: TooltipContentProps & { unit: Unit }) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload as DayRow | undefined;
  return (
    <div className="rounded-md border bg-popover px-3 py-2 text-xs shadow-md">
      <div className="mb-1 font-medium">
        {fmtDate(String(label), { year: true })}
        {row && !row.complete && <span className="ml-1 font-normal text-muted-foreground">(partial)</span>}
      </div>
      <ul className="space-y-0.5">
        {[...payload].reverse().map((p) => (
          <li key={String(p.dataKey)} className="flex items-center justify-between gap-4">
            <span className="flex items-center gap-1.5 text-muted-foreground">
              <span aria-hidden className="size-2 rounded-[2px]" style={{ background: p.color }} />
              {p.name}
            </span>
            <span className="tabular-nums">{formatAmount(Number(p.value ?? 0), unit)}</span>
          </li>
        ))}
      </ul>
      {row && (
        <div className="mt-1 flex justify-between gap-4 border-t pt-1 font-medium">
          <span>Total</span><span className="tabular-nums">{formatAmount(row.total, unit)}</span>
        </div>
      )}
    </div>
  );
}

function DayBreakdown({ day, records, unit, onClose }: { day: DayRow; records: SpendingRecord[]; unit: Unit; onClose: () => void }) {
  const groups = COMPONENT_ORDER.map((c) => ({ component: c, records: records.filter((r) => r.component === c) })).filter((g) => g.records.length > 0);
  return (
    <div className="rounded-lg border bg-muted/30 p-3 text-sm" aria-live="polite">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="font-medium">{fmtDate(day.date, { year: true })}</div>
          <div className="text-xs text-muted-foreground">
            Total {formatAmount(day.total, unit)}
            {!day.complete && <span className="ml-2 inline-flex items-center gap-1 text-foreground"><AlertTriangle className="size-3" /> Partial day: the source is incomplete for this date</span>}
          </div>
        </div>
        <Button variant="ghost" size="icon-xs" onClick={onClose} aria-label="Close day breakdown"><X /></Button>
      </div>
      <ul className="mt-3 divide-y">
        {groups.map(({ component, records: rs }) => (
          <li key={component} className="grid gap-1 py-2 sm:grid-cols-[1fr_auto] sm:items-start">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-1.5">
                <span aria-hidden className="size-2.5 rounded-[2px]" style={{ background: COMPONENT_COLOR_VAR[component] }} />
                <span className="font-medium">{COMPONENT_LABEL[component]}</span>
                {[...new Set(rs.map((r) => r.provenance))].map((p) => <ProvenanceBadge key={p} provenance={p} />)}
                {rs.some((r) => !r.complete) && <span className="text-[10px] text-muted-foreground">partial</span>}
              </div>
              <div className="mt-0.5 text-xs text-muted-foreground break-words">
                {[...new Set(rs.map((r) => `${r.source}${r.provider ? ` · ${r.provider}` : ""}`))].join("; ")}
              </div>
            </div>
            <div className={cn("tabular-nums sm:text-right", rs.some((r) => r.provenance !== "reported_charge") && "text-muted-foreground")}>
              {formatAmount(rs.reduce((s, r) => s + r.amount, 0), unit)}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
