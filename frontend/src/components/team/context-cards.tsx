"use client";
import { useMemo, useState } from "react";
import Link from "next/link";
import type { ContextItem, Person, Team } from "@/lib/contracts";
import { ArrowDownRight, ArrowUpRight, ChevronRight, CircleHelp, History, Minus } from "lucide-react";
import { SourceBadge, SourceLogos, sourceOf } from "@/components/context/source-brand";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useMounted } from "@/components/shared/motion";
import { EFFECT_TEXT } from "@/components/shared/tone";
import { riseAt, rowStep } from "./count-up";
import { SourceSheet } from "./source-sheet";
import { CLAIM_LABEL, EFFECT_LABEL, fmtDate } from "./labels";

interface Props {
  team: Team;
  items: ContextItem[];
  /** Every context item, so a "Replaced by" line can name an item that belongs to another team. */
  allItems: ContextItem[];
  /** Lets a person-scoped item name who it is about. */
  people?: Person[];
  /** Where this section sits in the page's entrance sequence, in ms. Rows follow with up to 80ms of stagger. */
  enterAt?: number;
  /** Where "All evidence" goes; defaults to the Evidence page filtered to this team. */
  evidenceHref?: string;
}

/** The inline list shows at most this many rows; the rest live on the Evidence page. */
const INLINE_LIMIT = 5;

const EVIDENCE_LINK = "text-sm underline underline-offset-4 decoration-border-strong transition-colors duration-300 hover:decoration-foreground";

const EFFECT_ICON = {
  increase: { Icon: ArrowUpRight, tone: EFFECT_TEXT.increase },
  decrease: { Icon: ArrowDownRight, tone: EFFECT_TEXT.decrease },
  neutral: { Icon: Minus, tone: EFFECT_TEXT.neutral },
  unknown: { Icon: CircleHelp, tone: EFFECT_TEXT.unknown },
} as const;

/** Compact list of this team's context: effect arrow, title, who, date. Summary and sources open on click. */
export function ContextCards({ team, items, allItems, people = [], enterAt = 0, evidenceHref }: Props) {
  const href = evidenceHref ?? `/evidence?team=${encodeURIComponent(team.id)}`;
  const [openDoc, setOpenDoc] = useState<string | undefined>();
  const [expanded, setExpanded] = useState<string | undefined>();
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
    <section className="space-y-3" aria-labelledby="context-heading">
      <div className={cn("flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2", rise)} style={riseAt(enterAt)}>
        <h2 id="context-heading" className="text-base font-medium">
          Context {sorted.length > 0 && <span className="num ml-1 text-sm font-normal text-muted-foreground">{sorted.length}</span>}
        </h2>
        <Link href={href} className={cn("shrink-0 text-foreground/80 hover:text-foreground", EVIDENCE_LINK)}>
          All evidence →
        </Link>
      </div>

      {sorted.length === 0 ? (
        <div className={cn("flex flex-col items-center gap-2 rounded-xl border border-border py-12 text-center", rise)} style={riseAt(enterAt)}>
          <div className="eyebrow">No context yet</div>
          <p className="max-w-sm text-sm text-muted-foreground">Nothing linked to {team.name} this period.</p>
        </div>
      ) : (
        <>
          <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-card">
            {shown.map((item, i) => (
              <li key={item.id} id={item.id} className={cn("scroll-mt-20", rise)} style={riseAt(enterAt + i * step)}>
                <ContextRow
                  item={item}
                  allItems={allItems}
                  people={people}
                  open={expanded === item.id}
                  onToggle={() => setExpanded((cur) => (cur === item.id ? undefined : item.id))}
                  onViewSource={setOpenDoc}
                />
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

function ContextRow({ item, allItems, people, open, onToggle, onViewSource }: {
  item: ContextItem; allItems: ContextItem[]; people: Person[]; open: boolean; onToggle: () => void; onViewSource: (documentId: string) => void;
}) {
  const superseded = !!item.supersededBy;
  const newer = superseded ? allItems.find((c) => c.id === item.supersededBy) : undefined;
  const { Icon, tone } = superseded ? { Icon: History, tone: "text-muted-foreground" } : EFFECT_ICON[item.expectedEffect];
  const named = (item.personIds ?? []).map((id) => people.find((p) => p.id === id)?.name).filter(Boolean) as string[];
  const who = item.attribution ?? item.sources[0]?.author ?? (named.length ? named.join(", ") : undefined);
  const date = item.effectiveFrom ?? item.sources[0]?.date;
  const panelId = `${item.id}-detail`;

  return (
    <div>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        aria-controls={panelId}
        className="flex min-h-12 w-full items-center gap-3 px-4 py-2.5 text-left outline-none transition-colors duration-300 hover:bg-popover focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset"
      >
        <Icon aria-label={superseded ? "Superseded" : EFFECT_LABEL[item.expectedEffect]} strokeWidth={1.75} className={cn("size-4 shrink-0", tone)} />
        <span className="flex min-w-0 flex-1 items-center gap-2">
          <span className={cn("truncate text-sm", superseded ? "text-muted-foreground line-through decoration-muted-foreground" : "text-foreground")}>
            {item.title}
          </span>
          <SourceLogos sources={item.sources} className={cn(superseded && "opacity-50")} />
        </span>
        <span className="hidden min-w-0 shrink items-center gap-x-1.5 text-xs text-muted-foreground sm:flex">
          {superseded ? <span>Superseded</span> : item.claimType && <span>{CLAIM_LABEL[item.claimType]}</span>}
          {who && <><span aria-hidden>·</span><span className="max-w-40 truncate">{who}</span></>}
        </span>
        {date && <span className="num w-14 shrink-0 text-right text-xs text-muted-foreground">{fmtDate(date)}</span>}
        <ChevronRight aria-hidden strokeWidth={1.5} className={cn("size-4 shrink-0 text-muted-foreground transition-transform duration-150", open && "rotate-90")} />
      </button>

      {open && (
        <div id={panelId} className="space-y-3 px-4 pb-4 pl-11 text-sm">
          <p className={superseded ? "text-muted-foreground" : "text-foreground/80"}>{item.summary}</p>
          {superseded && (
            <p className="text-xs text-muted-foreground">
              Replaced by <span className="text-foreground/80">{newer?.title ?? item.supersededBy}</span>. Not current.
            </p>
          )}
          {item.uncertainty && <p className="text-xs text-muted-foreground">Open question: {item.uncertainty}</p>}
          <div className="flex flex-wrap gap-x-3 text-xs text-muted-foreground sm:hidden">
            {item.claimType && <span>{CLAIM_LABEL[item.claimType]}</span>}
            {who && <span>{who}</span>}
          </div>
          {item.sources.length > 0 && (
            <ul className="divide-y divide-border border-t border-border">
              {item.sources.map((src, i) => (
                <li key={`${src.documentId}-${i}`} className="flex items-center gap-3 py-2">
                  <SourceBadge integration={sourceOf(src)} size="xs" className="shrink-0" />
                  <span className="min-w-0 flex-1 truncate text-xs text-muted-foreground" title={src.excerpt}>{src.title}</span>
                  {src.date && <span className="num shrink-0 text-xs text-muted-foreground">{fmtDate(src.date)}</span>}
                  <Button variant="ghost" size="xs" className="-mr-2 text-muted-foreground hover:text-foreground" onClick={() => onViewSource(src.documentId)}>Open</Button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
