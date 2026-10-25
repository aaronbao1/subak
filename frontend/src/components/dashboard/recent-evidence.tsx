"use client";
import Link from "next/link";
import { ArrowDownRight, ArrowRight, ArrowUpRight, Minus } from "lucide-react";
import type { ContextItem, Person, Team } from "@/lib/contracts";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { fmtDate } from "@/components/team/labels";
import { EFFECT_TEXT } from "@/components/shared/tone";

const SHOWN = 4;

const EFFECT = {
  increase: { icon: ArrowUpRight, label: "Increases spend" },
  decrease: { icon: ArrowDownRight, label: "Decreases spend" },
  neutral: { icon: Minus, label: "No change" },
  unknown: { icon: Minus, label: "Effect unclear" },
} as const;

/** Who an item is about, in one short phrase. */
function whoText(item: ContextItem, teams: Team[], people: Person[]): string {
  if (item.scope === "company") return "Company-wide";
  const names = (item.personIds ?? []).map((id) => people.find((p) => p.id === id)?.name).filter(Boolean) as string[];
  if (names.length) return names.length > 2 ? `${names.slice(0, 2).join(", ")} +${names.length - 2}` : names.join(", ");
  const team = teams.find((t) => t.id === item.teamIds[0]);
  return item.teamIds.length > 1 ? `${item.teamIds.length} teams` : team?.name ?? "Team";
}

/** One row of the most recent current evidence, with a way through to the full Evidence page. */
export function RecentEvidence({ items, teams, people }: { items: ContextItem[]; teams: Team[]; people: Person[] }) {
  const sorted = items
    .filter((i) => !i.supersededBy)
    .sort((a, b) => (b.effectiveFrom ?? "").localeCompare(a.effectiveFrom ?? ""));
  // Newest first, but one per kind of change before repeating, so the row isn't four out-of-office notes.
  const kind = (i: ContextItem) => `${i.scope ?? "team"}:${i.signal ?? i.category ?? i.kind}`;
  const seen = new Set<string>();
  const recent: ContextItem[] = [];
  for (const i of sorted) if (recent.length < SHOWN && !seen.has(kind(i))) { seen.add(kind(i)); recent.push(i); }
  for (const i of sorted) if (recent.length < SHOWN && !recent.includes(i)) recent.push(i);

  return (
    <section aria-labelledby="recent-evidence-heading" className="min-w-0 rounded-xl border border-border bg-card">
      <header className="flex h-12 items-center justify-between gap-4 px-5">
        <h2 id="recent-evidence-heading" className="text-base font-medium">Recent evidence</h2>
        <Button variant="ghost" size="sm" className="text-muted-foreground" nativeButton={false} render={<Link href="/evidence" />}>
          See all <ArrowRight className="size-4" strokeWidth={1.5} />
        </Button>
      </header>

      {recent.length === 0 ? (
        <div className="flex items-center gap-2 border-t border-border px-5 py-4 text-sm text-muted-foreground">
          <Minus className="size-4" strokeWidth={1.5} aria-hidden />
          No evidence yet. Connected sources will show up here.
        </div>
      ) : (
        <ul className="grid auto-cols-[minmax(240px,1fr)] grid-flow-col gap-px overflow-x-auto border-t border-border bg-border lg:grid-flow-row lg:grid-cols-4 lg:overflow-visible">
          {recent.map((item) => {
            const e = EFFECT[item.expectedEffect];
            const Icon = e.icon;
            return (
              <li key={item.id} className="min-w-0 bg-card">
                <Link href={item.teamIds.length === 1 ? `/evidence?team=${encodeURIComponent(item.teamIds[0])}` : "/evidence"} className="block h-full px-5 py-4 transition-colors duration-300 hover:bg-popover focus-visible:bg-popover focus-visible:outline-none">
                  {/* Effect is an arrow in status color; the word is in the tooltip and for screen readers. */}
                  <span className="flex items-start gap-2">
                    <Icon className={cn("mt-0.5 size-4 shrink-0", EFFECT_TEXT[item.expectedEffect])} strokeWidth={1.5} aria-hidden />
                    <span className="sr-only">{e.label}: </span>
                    <span className="line-clamp-2 text-sm leading-snug text-foreground" title={e.label}>{item.title}</span>
                  </span>
                  <span className="num mt-2 block truncate pl-6 text-xs text-muted-foreground">
                    {whoText(item, teams, people)}{item.effectiveFrom ? ` · ${fmtDate(item.effectiveFrom)}` : ""}
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
