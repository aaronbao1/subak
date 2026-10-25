"use client";
import { useMemo } from "react";
import {
  CartesianGrid, Line, LineChart, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import type { Team, Unit } from "@/lib/contracts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { formatAmount } from "@/lib/format";
import { dateLabel, teamKey, toTs, type DailyRow } from "./derive";

const HALF_DAY = 43_200_000;

export interface SpendByTeamChartProps {
  teams: Team[];
  rows: DailyRow[];
  partialDates: string[];
  unit: Unit;
  selectedId: string | null;
  onSelect: (teamId: string) => void;
}

export function SpendByTeamChart({ teams, rows, partialDates, unit, selectedId, onSelect }: SpendByTeamChartProps) {
  const domain = useMemo<[number, number] | undefined>(() => {
    if (rows.length === 0) return undefined;
    return [rows[0].ts - HALF_DAY, rows[rows.length - 1].ts + HALF_DAY];
  }, [rows]);

  // Roughly one tick per week so 90 days never collide; always include the first and last day.
  const ticks = useMemo(() => {
    if (rows.length === 0) return [];
    const step = Math.max(1, Math.ceil(rows.length / 7));
    const out = rows.filter((_, i) => i % step === 0).map((r) => r.ts);
    const last = rows[rows.length - 1].ts;
    if (out[out.length - 1] !== last) out.push(last);
    return out;
  }, [rows]);

  const teamById = useMemo(() => new Map(teams.map((t) => [teamKey(t.id), t])), [teams]);
  const dimming = selectedId !== null;

  return (
    <Card className="min-w-0">
      <CardHeader>
        <CardTitle>Daily spend by team</CardTitle>
        <CardDescription>Click a line or a team below to see its breakdown.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {rows.length === 0 ? (
          <div className="flex h-72 items-center justify-center text-sm text-muted-foreground">No spending recorded yet.</div>
        ) : (
          <div className="h-72 w-full md:h-80">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={rows} margin={{ top: 12, right: 12, bottom: 0, left: 0 }}>
                <CartesianGrid vertical={false} stroke="var(--border)" />
                <XAxis
                  dataKey="ts" type="number" scale="time" domain={domain} ticks={ticks}
                  tickFormatter={(v: number) => dateLabel(v)} tickLine={false} axisLine={false}
                  tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} minTickGap={16}
                />
                <YAxis
                  width={64} tickLine={false} axisLine={false}
                  tickFormatter={(v: number) => formatAmount(v, unit)}
                  tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
                />
                {partialDates.map((d) => {
                  const ts = toTs(d);
                  return (
                    <ReferenceArea
                      key={d} x1={ts - HALF_DAY} x2={ts + HALF_DAY} fill="var(--muted-foreground)" fillOpacity={0.08} stroke="none"
                      label={{ value: "partial", position: "insideTop", fontSize: 10, fill: "var(--muted-foreground)" }}
                    />
                  );
                })}
                <Tooltip
                  cursor={{ stroke: "var(--border)" }}
                  content={({ active, payload, label }) => {
                    if (!active || !payload?.length) return null;
                    const items = payload
                      .filter((p) => typeof p.value === "number")
                      .map((p) => ({ team: teamById.get(String(p.dataKey)), value: p.value as number }))
                      .filter((p) => p.team)
                      .sort((a, b) => b.value - a.value);
                    const total = items.reduce((s, i) => s + i.value, 0);
                    const row = payload[0]?.payload as DailyRow | undefined;
                    return (
                      <div className="rounded-md border bg-popover px-3 py-2 text-xs shadow-sm">
                        <div className="mb-1 flex items-center gap-2 font-medium">
                          {dateLabel(Number(label))}
                          {row?.partial && <span className="text-muted-foreground">partial</span>}
                        </div>
                        <ul className="space-y-0.5">
                          {items.map(({ team, value }) => (
                            <li key={team!.id} className={cn("flex items-center justify-between gap-4", dimming && team!.id !== selectedId && "text-muted-foreground")}>
                              <span className="flex items-center gap-1.5">
                                <span className="size-2 rounded-full" style={{ background: team!.color }} />
                                {team!.name}
                              </span>
                              <span className="tabular-nums">{formatAmount(value, unit)}</span>
                            </li>
                          ))}
                        </ul>
                        {items.length > 1 && (
                          <div className="mt-1 flex justify-between gap-4 border-t pt-1 text-muted-foreground">
                            <span>Total</span><span className="tabular-nums">{formatAmount(total, unit)}</span>
                          </div>
                        )}
                      </div>
                    );
                  }}
                />
                {teams.map((t) => {
                  const selected = t.id === selectedId;
                  const dim = dimming && !selected;
                  return (
                    <Line
                      key={t.id} type="monotone" dataKey={teamKey(t.id)} name={t.name}
                      stroke={t.color} strokeWidth={selected ? 2.75 : 1.75} strokeOpacity={dim ? 0.25 : 1}
                      strokeLinecap="round" strokeLinejoin="round"
                      dot={false} connectNulls={false} isAnimationActive={false}
                      style={{ cursor: "pointer" }}
                      onClick={() => onSelect(t.id)}
                      activeDot={{
                        r: selected ? 6 : 4.5, strokeWidth: 2, stroke: "var(--background)", fill: t.color,
                        fillOpacity: dim ? 0.25 : 1, cursor: "pointer",
                        onClick: () => onSelect(t.id),
                      }}
                    />
                  );
                })}
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}

        <ChartLegend teams={teams} selectedId={selectedId} onSelect={onSelect} />

        {partialDates.length > 0 && (
          <p className="text-xs text-muted-foreground">
            Shaded {partialDates.length === 1 ? "day is" : "days are"} partial ({partialDates.map(dateLabel).join(", ")}): some sources have not reported yet.
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function ChartLegend({ teams, selectedId, onSelect }: { teams: Team[]; selectedId: string | null; onSelect: (id: string) => void }) {
  return (
    <ul className="flex max-h-20 flex-wrap gap-x-1 gap-y-0.5 overflow-y-auto" aria-label="Teams">
      {teams.map((t) => {
        const selected = t.id === selectedId;
        const dim = selectedId !== null && !selected;
        return (
          <li key={t.id}>
            <button
              type="button" onClick={() => onSelect(t.id)} aria-pressed={selected}
              className={cn(
                "flex items-center gap-1.5 rounded-md px-2 py-1 text-xs transition-colors hover:bg-muted",
                selected && "bg-muted font-medium", dim && "text-muted-foreground",
              )}
            >
              <span className="size-2 shrink-0 rounded-full" style={{ background: t.color, opacity: dim ? 0.35 : 1 }} />
              {t.name}
            </button>
          </li>
        );
      })}
    </ul>
  );
}

export function SpendByTeamChartSkeleton() {
  return (
    <Card>
      <CardHeader><Skeleton className="h-5 w-40" /><Skeleton className="h-4 w-64" /></CardHeader>
      <CardContent><Skeleton className="h-72 w-full md:h-80" /></CardContent>
    </Card>
  );
}
