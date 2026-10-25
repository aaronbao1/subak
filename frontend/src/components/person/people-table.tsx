"use client";
import Link from "next/link";
import { ChevronRight, Users } from "lucide-react";
import type { Team, Unit } from "@/lib/contracts";
import { formatAmount, formatPct } from "@/lib/format";
import { Table, TableBody, TableCell, TableFooter, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { useMounted } from "@/components/shared/motion";
import { riseAt, rowStep } from "@/components/team/count-up";
import { SignalChip } from "./signal-badges";
import type { PersonSummary } from "./derive";

interface Props {
  team: Team;
  summaries: PersonSummary[];
  unit: Unit;
  /** Where this section sits in the page's entrance sequence, in ms. Rows follow with up to 120ms of stagger. */
  enterAt?: number;
}

/** Everyone on the team: spend to date, projection, share of the team number, week-over-week change and the signals behind it. */
export function PeopleTable({ team, summaries, unit, enterAt = 0 }: Props) {
  const mounted = useMounted();
  const rise = mounted ? "animate-rise" : "opacity-0";
  const rows = [...summaries].sort((a, b) => (b.projected ?? b.spent) - (a.projected ?? a.spent));
  const step = rowStep(rows.length, 120);
  const rowAt = (i: number) => riseAt(enterAt + i * step);
  const totalSpent = rows.reduce((s, r) => s + r.spent, 0);
  const withProjection = rows.filter((r) => r.projected != null);
  const totalProjected = withProjection.length ? withProjection.reduce((s, r) => s + (r.projected as number), 0) : undefined;
  const totalShare = rows.length && rows.every(r => r.share != null) ? rows.reduce((sum, r) => sum + r.share!, 0) : undefined;

  return (
    <section className="space-y-3" aria-labelledby="people-heading">
      <div className={rise} style={riseAt(enterAt)}>
        <h2 id="people-heading" className="text-base font-medium">People</h2>
        <p className="mt-1 text-xs text-muted-foreground">
          {rows.length} {rows.length === 1 ? "person" : "people"} currently on {team.name}. Shared spend and historical team changes can make these person totals differ from the team total.
        </p>
      </div>

      {rows.length === 0 ? (
        <div className={cn("flex flex-col items-center gap-2 rounded-xl border border-border py-16 text-center", rise)} style={riseAt(enterAt)}>
          <Users className="size-4 text-muted-foreground" aria-hidden strokeWidth={1.5} />
          <div className="eyebrow">No people attributed yet</div>
          <p className="max-w-sm text-sm text-muted-foreground">Usage is recorded at team level until the backend maps seats and API keys to people.</p>
        </div>
      ) : (
        <>
          <div className={cn("hidden overflow-hidden rounded-xl border border-border bg-card md:block", rise)} style={riseAt(enterAt)}>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Person</TableHead>
                  <TableHead className="text-right">Spent to date</TableHead>
                  <TableHead className="text-right">Projection</TableHead>
                  <TableHead className="text-right">Share</TableHead>
                  <TableHead className="text-right">vs last week</TableHead>
                  <TableHead>Signals</TableHead>
                  <TableHead className="w-12"><span className="sr-only">Open</span></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((r, i) => (
                  <TableRow key={r.person.id} className={cn("group relative", rise)} style={rowAt(i)}>
                    <TableCell>
                      <Link
                        href={`/teams/${team.id}/people/${r.person.id}`}
                        className="block min-w-0 outline-none after:absolute after:inset-0 focus-visible:after:ring-2 focus-visible:after:ring-ring focus-visible:after:ring-inset"
                      >
                        <div className="truncate font-medium">{r.person.name}</div>
                        <div className="truncate text-xs text-muted-foreground">{r.person.role ?? "—"}{r.person.primaryTool ? ` · ${r.person.primaryTool}` : ""}</div>
                      </Link>
                    </TableCell>
                    <TableCell className="num text-right">{formatAmount(r.spent, unit)}</TableCell>
                    <TableCell className="num text-right">
                      {r.projected != null ? formatAmount(r.projected, unit) : <span className="font-sans text-muted-foreground">No projection</span>}
                    </TableCell>
                    <TableCell className="num text-right text-muted-foreground">{r.share != null ? formatPct(r.share * 100) : "—"}</TableCell>
                    <TableCell className="text-right"><WeekChange value={r.weekChange} /></TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {r.signals.length === 0 ? <span className="text-xs text-muted-foreground">No change signalled</span> : r.signals.slice(0, 2).map((s) => <SignalChip key={s.id} item={s} />)}
                      </div>
                    </TableCell>
                    <TableCell className="pr-4">
                      <ChevronRight className="size-4 text-muted-foreground" aria-hidden strokeWidth={1.5} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
              <TableFooter>
                <TableRow className={cn("hover:bg-transparent", rise)} style={rowAt(rows.length - 1)}>
                  <TableCell className="text-xs">Attributed people subtotal</TableCell>
                  <TableCell className="num text-right text-xs">{formatAmount(totalSpent, unit)}</TableCell>
                  <TableCell className="num text-right text-xs">
                    {totalProjected != null ? formatAmount(totalProjected, unit) : <span className="text-muted-foreground">—</span>}
                    {withProjection.length < rows.length && totalProjected != null && (
                      <span className="ml-1.5 font-sans font-normal text-muted-foreground">{withProjection.length} with a projection</span>
                    )}
                  </TableCell>
                  <TableCell className="num text-right text-xs text-muted-foreground">{totalShare != null ? formatPct(totalShare * 100) : "—"}</TableCell>
                  <TableCell colSpan={3} />
                </TableRow>
              </TableFooter>
            </Table>
          </div>

          {/* Cards below md so nothing scrolls horizontally on a phone */}
          <ul className="grid gap-3 md:hidden">
            {rows.map((r, i) => (
              <li key={r.person.id} className={rise} style={rowAt(i)}>
                <Link
                  href={`/teams/${team.id}/people/${r.person.id}`}
                  className="block rounded-xl border border-border bg-card p-4 outline-none transition-colors duration-300 hover:border-border-strong focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium">{r.person.name}</div>
                      <div className="mt-0.5 text-xs text-muted-foreground">{r.person.role ?? "—"}</div>
                    </div>
                    <WeekChange value={r.weekChange} className="text-sm" />
                  </div>
                  <dl className="mt-4 grid grid-cols-3 gap-3">
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

/** Week-over-week change in average daily spend. A rise past 15% reads in --warning; a fall is muted; the rest is plain ink. */
export function WeekChange({ value, className }: { value?: number; className?: string }) {
  if (value === undefined) return <span className={cn("text-muted-foreground", className)}>—</span>;
  const pctText = `${value > 0 ? "+" : ""}${Math.round(value * 100)}%`;
  return (
    <span className={cn("num", value > 0.15 ? "text-warning" : value < -0.15 ? "text-muted-foreground" : "text-foreground/80", className)} title="Average daily spend on complete days this week vs last week">
      {pctText}
    </span>
  );
}

function Stat({ label, value, muted }: { label: string; value: string; muted?: boolean }) {
  return (
    <div className="min-w-0">
      <dt className="eyebrow">{label}</dt>
      <dd className={cn("num mt-1 truncate text-sm", muted && "text-muted-foreground")}>{value}</dd>
    </div>
  );
}
