"use client";
import { useMemo, useState } from "react";
import Link from "next/link";
import type { ContextItem, Person, Team } from "@/lib/contracts";
import { ContextCard } from "@/components/context/context-card";
import { cn } from "@/lib/utils";
import { useMounted } from "@/components/shared/motion";
import { riseAt, rowStep } from "./count-up";
import { SourceSheet } from "./source-sheet";

interface Props {
  team: Team;
  items: ContextItem[];
  /** Every context item, so a "Replaced by" line can name an item that belongs to another team. */
  allItems: ContextItem[];
  /** Lets a person-scoped item name who it is about. */
  people?: Person[];
  /** Where this section sits in the page's entrance sequence, in ms. Cards follow with up to 80ms of stagger. */
  enterAt?: number;
  /** Where "All evidence" goes; defaults to the Evidence page filtered to this team. */
  evidenceHref?: string;
}

/** The inline list shows at most this many cards; the rest live on the Evidence page. */
const INLINE_LIMIT = 4;

const EVIDENCE_LINK = "text-sm underline underline-offset-4 decoration-border-strong transition-colors duration-300 hover:decoration-foreground";

/** One card per context item for this team; superseded items are muted and sorted last. */
export function ContextCards({ team, items, allItems, people = [], enterAt = 0, evidenceHref }: Props) {
  const href = evidenceHref ?? `/evidence?team=${encodeURIComponent(team.id)}`;
  const [openDoc, setOpenDoc] = useState<string | undefined>();
  const mounted = useMounted();
  const rise = mounted ? "animate-rise" : "opacity-0";

  const sorted = useMemo(
    () =>
      [...items].sort((a, b) => {
        // Current before superseded; claims that move spend before neutral ones; routine absences last; then newest first.
        const rank = (c: ContextItem) =>
          (c.supersededBy ? 100 : 0) +
          (c.expectedEffect === "neutral" ? 20 : c.expectedEffect === "unknown" ? 10 : 0) +
          (c.signal === "out_of_office" ? 5 : 0);
        const d = rank(a) - rank(b);
        if (d !== 0) return d;
        return (b.effectiveFrom ?? "").localeCompare(a.effectiveFrom ?? "");
      }),
    [items],
  );
  const shown = sorted.slice(0, INLINE_LIMIT);
  const more = sorted.length - shown.length;
  const step = rowStep(shown.length, 80, 40);

  return (
    <section className="space-y-4" aria-labelledby="context-heading">
      <div className={cn("flex flex-wrap items-start justify-between gap-x-6 gap-y-2", rise)} style={riseAt(enterAt)}>
        <div className="min-w-0">
          <h2 id="context-heading" className="text-base font-medium">Context and evidence</h2>
          <p className="mt-1 text-xs text-muted-foreground">
            Plans, documents, messages and tasks that bear on {team.name}&apos;s spend, quoted from where they were said. Each claim opens its source.
          </p>
        </div>
        <Link href={href} className={cn("shrink-0 text-foreground/80 hover:text-foreground", EVIDENCE_LINK)}>
          All evidence for {team.name} →
        </Link>
      </div>

      {sorted.length === 0 ? (
        <div className={cn("flex flex-col items-center gap-2 rounded-xl border border-border py-16 text-center", rise)} style={riseAt(enterAt)}>
          <div className="eyebrow">No context for this team</div>
          <p className="max-w-sm text-sm text-muted-foreground">No plans, documents or correspondence have been linked to {team.name} for this period.</p>
        </div>
      ) : (
        <>
          <ul className="grid gap-4 lg:grid-cols-2">
            {shown.map((item, i) => (
              <li key={item.id} id={item.id} className={cn("scroll-mt-20", rise)} style={riseAt(enterAt + i * step)}>
                <ContextCard item={item} allItems={allItems} people={people} onViewSource={setOpenDoc} />
              </li>
            ))}
          </ul>
          {more > 0 && (
            <p className={cn("text-xs text-muted-foreground", rise)} style={riseAt(enterAt + shown.length * step)}>
              <Link href={href} className={cn(EVIDENCE_LINK, "text-xs hover:text-foreground")}>+{more} more in Evidence</Link>
            </p>
          )}
        </>
      )}

      <SourceSheet documentId={openDoc} onClose={() => setOpenDoc(undefined)} />
    </section>
  );
}
