"use client";
import Link from "next/link";
import { ChevronRight, Users } from "lucide-react";
import type { Team, Unit } from "@/lib/contracts";
import { formatAmount, formatPct } from "@/lib/format";
import { Table, TableBody, TableCell, TableFooter, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { useMounted } from "@/components/shared/motion";
import { riseAt, rowStep } from "@/components/team/count-up";
import { DeltaChip, ShareMeter, Sparkline } from "@/components/team/viz";
import { SignalChip } from "./signal-badges";
import type { PersonSummary } from "./derive";

interface Props {
  team: Team;
  summaries: PersonSummary[];
  unit: Unit;
  /** Where this section sits in the page's entrance sequence, in ms. Rows follow with up to 120ms of stagger. */
  enterAt?: number;
}

/** Everyone on the team: spend, projection, share as a meter, a 14-day sparkline with the weekly delta, and the top signal. */
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
        <h2 id="people-heading" className="text-base font-medium">
          People {rows.length > 0 && <span className="num ml-1 text-sm font-normal text-muted-foreground">{rows.length}</span>}
        </h2>
      </div>

      {rows.length === 0 ? (
        <div className={cn("flex flex-col items-center gap-2 rounded-xl border border-border py-16 text-center", rise)} style={riseAt(enterAt)}>
          <Users className="size-4 text-muted-foreground" aria-hidden strokeWidth={1.5} />
          <div className="eyebrow">No people attributed yet</div>
          <p className="max-w-sm text-sm text-muted-foreground">Usage stays at team level until seats map to people.</p>
        </div>
      ) : (
        <>
          <div className={cn("hidden overflow-hidden rounded-xl border border-border bg-card md:block", rise)} style={riseAt(enterAt)}>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Person</TableHead>
                  <TableHead className="text-right">Spent</TableHead>
                  <TableHead className="text-right">Projection</TableHead>
                  <TableHead className="text-right" title="Share of the team's projected total">Share</TableHead>
                  <TableHead className="text-right" title="Daily spend, last 14 days; change is this week vs last week">Trend</TableHead>
                  <TableHead>Signal</TableHead>
                  <TableHead className="w-12"><span className="sr-only">Open</span></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((r, i) => (
                  <TableRow key={r.person.id} className={cn("group relative", rise)} style={rowAt(i)}>
                    <TableCell>
                      <Link
                        href={`/teams/${team.id}/people/${r.person.id}`}
                        title={[r.person.role, r.person.primaryTool].filter(Boolean).join(" · ") || undefined}
                        className="block min-w-0 truncate font-medium outline-none after:absolute after:inset-0 focus-visible:after:ring-2 focus-visible:after:ring-ring focus-visible:after:ring-inset"
                      >
                        {r.person.name}
                      </Link>
                    </TableCell>
                    <TableCell className="num text-right">{formatAmount(r.spent, unit)}</TableCell>
                    <TableCell className="num text-right">
                      {r.projected != null ? formatAmount(r.projected, unit) : <span className="font-sans text-muted-foreground">No projection</span>}
                    </TableCell>
                    <TableCell className="text-right"><ShareMeter share={r.share} color={team.color} grow={mounted} delay={enterAt + i * step} className="w-full" /></TableCell>
                    <TableCell className="text-right">
                      <span className="inline-flex items-center justify-end gap-3">
                        <Sparkline values={r.recentDaily ?? []} partialLast={r.recentPartial} className="text-muted-foreground" />
                        <DeltaChip value={r.weekChange} className="w-12 justify-end" />
                      </span>
                    </TableCell>
                    <TableCell className="max-w-48">
                      {r.signals.length === 0 ? <span className="text-xs text-muted-foreground">—</span> : <SignalChip item={r.signals[0]} />}
                    </TableCell>
                    <TableCell className="pr-4">
                      <ChevronRight className="size-4 text-muted-foreground" aria-hidden strokeWidth={1.5} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
              <TableFooter>
                <TableRow className={cn("hover:bg-transparent", rise)} style={rowAt(rows.length - 1)}>
                  <TableCell className="text-xs" title="Shared spend and past team changes can make this differ from the team total">Attributed subtotal</TableCell>
                  <TableCell className="num text-right text-xs">{formatAmount(totalSpent, unit)}</TableCell>
                  <TableCell className="num text-right text-xs">
                    {totalProjected != null ? formatAmount(totalProjected, unit) : <span className="text-muted-foreground">—</span>}
                    {withProjection.length < rows.length && totalProjected != null && (
                      <span className="ml-1.5 font-sans font-normal text-muted-foreground" title="People with a projection">{withProjection.length}/{rows.length}</span>
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
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0 truncate text-sm font-medium">{r.person.name}</div>
                    <span className="inline-flex items-center gap-2">
                      <Sparkline values={r.recentDaily ?? []} partialLast={r.recentPartial} className="text-muted-foreground" />
                      <DeltaChip value={r.weekChange} className="text-sm" />
                    </span>
                  </div>
                  <div className="mt-3 flex items-baseline justify-between gap-3 text-xs text-muted-foreground">
                    <span>Spent <span className="num text-foreground">{formatAmount(r.spent, unit)}</span></span>
                    <span>Projected <span className={cn("num", r.projected != null ? "text-foreground" : "")}>{r.projected != null ? formatAmount(r.projected, unit) : "none"}</span></span>
                  </div>
                  <div className="mt-2 flex items-center justify-between gap-3">
                    <span className="text-xs text-muted-foreground">Share</span>
                    <ShareMeter share={r.share} color={team.color} />
                  </div>
                  {r.signals.length > 0 && <div className="mt-3"><SignalChip item={r.signals[0]} /></div>}
                </Link>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
