"use client";
import { useMemo, useState } from "react";
import Link from "next/link";
import type { ContextItem, Person, Team } from "@/lib/contracts";
import { SourceSheet } from "@/components/team/source-sheet";
import { SourceLogo, primarySource } from "./source-brand";
import { ContextCardCompact } from "./context-card";

const LIMIT = 6;
const CONFIDENCE_RANK = { high: 0, medium: 1, low: 2 } as const;

/**
 * Overview section: the handful of plans, messages and tasks that move this period's spend, each with the
 * quote it rests on and the app it came from. Click a title to read the source; team names go to the team page.
 */
export function ContextHighlights({ items, teams, people = [] }: { items: ContextItem[]; teams: Team[]; people?: Person[] }) {
  const [openDoc, setOpenDoc] = useState<string | undefined>();

  const picked = useMemo(() => {
    const live = items.filter((c) => !c.supersededBy && c.sources.length > 0);
    // Lower is better: spend-moving, confident, team-level claims first; routine absences last.
    const score = (c: ContextItem) =>
      (c.expectedEffect === "neutral" ? 2 : c.expectedEffect === "unknown" ? 1 : 0) * 10 +
      CONFIDENCE_RANK[c.confidence] * 3 +
      (c.scope === "person" ? 2 : 0) +
      (c.signal === "out_of_office" ? 6 : 0);
    const sorted = [...live].sort((a, b) => score(a) - score(b) || (b.sources[0]?.date ?? "").localeCompare(a.sources[0]?.date ?? ""));
    // Spread the picks so six cards show six different things: never the same quote twice, and an item earns an
    // early slot only while its app is new, or its team and its kind of signal are both new. The rest fill in after.
    const teamsSeen = new Set<string>();
    const appsSeen = new Set<string>();
    const kindsSeen = new Set<string>();
    const quotesSeen = new Set<string>();
    const first: ContextItem[] = [];
    const later: ContextItem[] = [];
    for (const c of sorted) {
      const team = c.scope === "company" ? "company" : c.teamIds[0] ?? "";
      const app = primarySource(c);
      const kind = c.signal ?? c.kind;
      const quote = c.sources[0]?.excerpt ?? c.id;
      if (quotesSeen.has(quote)) continue;
      const fresh = !appsSeen.has(app) || (!teamsSeen.has(team) && !kindsSeen.has(kind));
      if (first.length < LIMIT && fresh) { teamsSeen.add(team); appsSeen.add(app); kindsSeen.add(kind); quotesSeen.add(quote); first.push(c); }
      else later.push(c);
    }
    return [...first, ...later].slice(0, LIMIT);
  }, [items]);

  const apps = useMemo(() => [...new Set(items.filter((c) => !c.supersededBy).map(primarySource))], [items]);
  const remaining = items.filter((c) => !c.supersededBy).length - picked.length;

  if (picked.length === 0) return null;

  return (
    <section className="space-y-4" aria-labelledby="context-highlights-heading">
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-2">
        <div>
          <h2 id="context-highlights-heading" className="text-base font-medium">Context and evidence</h2>
          <p className="mt-1 text-xs text-muted-foreground">What is changing across teams this week, with the message, task or document behind each claim.</p>
        </div>
        <div className="flex items-center gap-2 text-[11px] text-muted-foreground" aria-label="Connected sources">
          <span>From</span>
          <span className="flex items-center gap-1.5">
            {apps.map((a) => <SourceLogo key={a} integration={a} className="size-3.5" />)}
          </span>
        </div>
      </div>

      <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {picked.map((item) => {
          const team = item.scope === "company" ? undefined : teams.find((t) => t.id === item.teamIds[0]);
          const person = item.personIds?.length ? people.find((p) => p.id === item.personIds![0]) : undefined;
          return (
            <li key={item.id} className="min-w-0">
              <ContextCardCompact item={item} team={team} person={person} onOpen={() => setOpenDoc(item.sources[0]?.documentId)} />
            </li>
          );
        })}
      </ul>

      {remaining > 0 && (
        <p className="text-xs text-muted-foreground">
          {remaining} more {remaining === 1 ? "item" : "items"} on the <Link href="/teams" className="text-foreground/80 underline underline-offset-4 decoration-border-strong hover:decoration-foreground">team pages</Link>, including superseded context kept for traceability.
        </p>
      )}

      <SourceSheet documentId={openDoc} onClose={() => setOpenDoc(undefined)} />
    </section>
  );
}
