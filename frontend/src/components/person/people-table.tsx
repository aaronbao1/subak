"use client";
import Link from "next/link";
import { ChevronRight, Users } from "lucide-react";
import type { Team, Unit } from "@/lib/contracts";
import { formatAmount, formatPct } from "@/lib/format";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { SignalChip } from "./signal-badges";
import type { PersonSummary } from "./derive";

const HEAD = "h-9 px-3 text-[11px] font-medium tracking-wide uppercase text-muted-foreground";

interface Props {
  team: Team;
  summaries: PersonSummary[];
  unit: Unit;
}

/** Everyone on the team: spend to date, projection, share of the team number, week-over-week change and the signals behind it. */
export function PeopleTable({ team, summaries, unit }: Props) {
  const rows = [...summaries].sort((a, b) => (b.projected ?? b.spent) - (a.projected ?? a.spent));
  const totalSpent = rows.reduce((s, r) => s + r.spent, 0);
  const withProjection = rows.filter((r) => r.projected != null);
  const totalProjected = withProjection.length ? withProjection.reduce((s, r) => s + (r.projected as number), 0) : undefined;

  return (
    <section className="space-y-3" aria-labelledby="people-heading">
      <div>
        <h2 id="people-heading" className="text-sm font-medium">People</h2>
        <p className="mt-0.5 text-xs text-muted-foreground">
          {rows.length} {rows.length === 1 ? "person" : "people"} on {team.name}. The team&apos;s numbers are the sum of these rows; signals come from Slack, Asana and Monday.
        </p>
      </div>

      {rows.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed py-10 text-center">
          <Users className="size-5 text-muted-foreground" />
          <div className="text-sm font-medium">No people attributed yet</div>
          <p className="max-w-sm text-sm text-muted-foreground">Usage is recorded at team level until the backend maps seats and API keys to people.</p>
        </div>
      ) : (
        <>
          <div className="hidden overflow-hidden rounded-xl border md:block">
            <Table>
              <TableHeader>
                <TableRow className="border-border/60 hover:bg-transparent">
                  <TableHead className={cn(HEAD, "pl-4")}>Person</TableHead>
                  <TableHead className={cn(HEAD, "text-right")}>Spent to date</TableHead>
                  <TableHead className={cn(HEAD, "text-right")}>Projection</TableHead>
                  <TableHead className={cn(HEAD, "text-right")}>Share</TableHead>
                  <TableHead className={cn(HEAD, "text-right")}>vs last week</TableHead>
                  <TableHead className={HEAD}>Signals</TableHead>
                  <TableHead className={cn(HEAD, "w-10")} />
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((r) => (
                  <TableRow key={r.person.id} className="group relative border-border/60 hover:bg-muted/30">
                    <TableCell className="h-12 px-3 pl-4">
                      <Link href={`/teams/${team.id}/people/${r.person.id}`} className="block min-w-0 outline-none after:absolute after:inset-0 focus-visible:after:ring-2 focus-visible:after:ring-ring/60 focus-visible:after:ring-inset">
                        <div className="truncate font-medium">{r.person.name}</div>
                        <div className="truncate text-[11px] text-muted-foreground">{r.person.role ?? "—"}{r.person.primaryTool ? ` · ${r.person.primaryTool}` : ""}</div>
                      </Link>
                    </TableCell>
                    <TableCell className="px-3 text-right tabular-nums">{formatAmount(r.spent, unit)}</TableCell>
                    <TableCell className="px-3 text-right tabular-nums">
                      {r.projected != null ? formatAmount(r.projected, unit) : <span className="text-muted-foreground/70">No projection</span>}
                    </TableCell>
                    <TableCell className="px-3 text-right tabular-nums text-muted-foreground">{r.share != null ? formatPct(r.share * 100) : "—"}</TableCell>
                    <TableCell className="px-3 text-right tabular-nums"><WeekChange value={r.weekChange} /></TableCell>
                    <TableCell className="px-3">
                      <div className="flex flex-wrap gap-1">
                        {r.signals.length === 0 ? <span className="text-[11px] text-muted-foreground">No change signalled</span> : r.signals.slice(0, 2).map((s) => <SignalChip key={s.id} item={s} />)}
                      </div>
                    </TableCell>
                    <TableCell className="px-3 pr-4 text-muted-foreground/50 transition-colors group-hover:text-muted-foreground"><ChevronRight className="size-4" /></TableCell>
                  </TableRow>
                ))}
                <TableRow className="border-border/60 bg-muted/20 hover:bg-muted/20">
                  <TableCell className="h-10 px-3 pl-4 text-xs font-medium">Team total</TableCell>
                  <TableCell className="px-3 text-right text-xs tabular-nums">{formatAmount(totalSpent, unit)}</TableCell>
                  <TableCell className="px-3 text-right text-xs tabular-nums">
                    {totalProjected != null ? formatAmount(totalProjected, unit) : <span className="text-muted-foreground/70">—</span>}
                    {withProjection.length < rows.length && totalProjected != null && <span className="ml-1 text-[10px] text-muted-foreground">({withProjection.length} of {rows.length})</span>}
                  </TableCell>
                  <TableCell className="px-3 text-right text-xs text-muted-foreground tabular-nums">{totalProjected != null ? "100%" : "—"}</TableCell>
                  <TableCell colSpan={3} />
                </TableRow>
              </TableBody>
            </Table>
          </div>

          <ul className="grid gap-2 md:hidden">
            {rows.map((r) => (
              <li key={r.person.id}>
                <Link href={`/teams/${team.id}/people/${r.person.id}`} className="block rounded-xl border bg-card p-4 outline-none transition-colors hover:bg-muted/30 focus-visible:ring-2 focus-visible:ring-ring/60">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium">{r.person.name}</div>
                      <div className="mt-0.5 text-xs text-muted-foreground">{r.person.role ?? "—"}</div>
                    </div>
                    <WeekChange value={r.weekChange} />
                  </div>
                  <dl className="mt-3 grid grid-cols-3 gap-3">
                    <Stat label="Spent" value={formatAmount(r.spent, unit)} />
                    <Stat label="Projection" value={r.projected != null ? formatAmount(r.projected, unit) : "None"} muted={r.projected == null} />
                    <Stat label="Share" value={r.share != null ? formatPct(r.share * 100) : "—"} muted={r.share == null} />
                  </dl>
                  {r.signals.length > 0 && <div className="mt-3 flex flex-wrap gap-1">{r.signals.slice(0, 2).map((s) => <SignalChip key={s.id} item={s} />)}</div>}
                </Link>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

export function WeekChange({ value, className }: { value?: number; className?: string }) {
  if (value === undefined) return <span className={cn("text-muted-foreground/70", className)}>—</span>;
  const pctText = `${value > 0 ? "+" : ""}${Math.round(value * 100)}%`;
  return (
    <span className={cn("tabular-nums", value > 0.15 ? "text-warning" : value < -0.15 ? "text-muted-foreground" : "text-foreground/80", className)} title="Average daily spend on complete days this week vs last week">
      {pctText}
    </span>
  );
}

function Stat({ label, value, muted }: { label: string; value: string; muted?: boolean }) {
  return (
    <div className="min-w-0">
      <dt className="text-[11px] tracking-wide text-muted-foreground">{label}</dt>
      <dd className={cn("mt-0.5 truncate text-sm tabular-nums", muted && "text-muted-foreground/70")}>{value}</dd>
    </div>
  );
}
