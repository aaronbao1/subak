"use client";
import { useMemo, useState } from "react";
import { ArrowDownRight, ArrowUpRight, ChevronRight, CircleHelp, FileText, Minus } from "lucide-react";
import type { ContextItem, Person, SourceRef, Team } from "@/lib/contracts";
import { CompanyWideChip, IntegrationChip } from "@/components/person/signal-badges";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { CLAIM_LABEL, CONFIDENCE_LABEL, EFFECT_LABEL, fmtDate } from "./labels";
import { SourceSheet } from "./source-sheet";

interface Props {
  team: Team;
  items: ContextItem[];
  /** Every context item, so a "Replaced by" line can name an item that belongs to another team. */
  allItems: ContextItem[];
  /** Lets a person-scoped item name who it is about. */
  people?: Person[];
}

const KIND_LABEL: Record<ContextItem["kind"], string> = {
  plan: "Plan",
  project_doc: "Project document",
  research_note: "Research note",
  correspondence: "Correspondence",
};

const EFFECT_ICON = {
  increase: ArrowUpRight,
  decrease: ArrowDownRight,
  neutral: Minus,
  unknown: CircleHelp,
} as const;

const EFFECT_SHORT: Record<ContextItem["expectedEffect"], string> = {
  increase: "Increases spend",
  decrease: "Decreases spend",
  neutral: "Neutral",
  unknown: "Effect unknown",
};

const CONFIDENCE_SHORT = { high: "High confidence", medium: "Medium confidence", low: "Low confidence" } as const;

/** One card per context item for this team; superseded items are muted and sorted last. */
export function ContextCards({ team, items, allItems, people = [] }: Props) {
  const [openDoc, setOpenDoc] = useState<string | undefined>();

  const sorted = useMemo(
    () =>
      [...items].sort((a, b) => {
        const sa = a.supersededBy ? 1 : 0;
        const sb = b.supersededBy ? 1 : 0;
        if (sa !== sb) return sa - sb;
        return (b.effectiveFrom ?? "").localeCompare(a.effectiveFrom ?? "");
      }),
    [items],
  );

  return (
    <section className="space-y-4" aria-labelledby="context-heading">
      <div>
        <h2 id="context-heading" className="text-base font-medium">Context and evidence</h2>
        <p className="mt-1 text-xs text-muted-foreground">
          Plans, project documents, and signals from Slack, Asana and Monday that bear on {team.name}&apos;s spend. Each claim links to its source.
        </p>
      </div>

      {sorted.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-xl border border-border py-16 text-center">
          <div className="eyebrow">No context for this team</div>
          <p className="max-w-sm text-sm text-muted-foreground">No plans, documents or correspondence have been linked to {team.name} for this period.</p>
        </div>
      ) : (
        <ul className="grid gap-4 lg:grid-cols-2">
          {sorted.map((item) => (
            <li key={item.id} id={item.id} className="scroll-mt-20">
              <ContextCard item={item} allItems={allItems} people={people} onViewSource={setOpenDoc} />
            </li>
          ))}
        </ul>
      )}

      <SourceSheet documentId={openDoc} onClose={() => setOpenDoc(undefined)} />
    </section>
  );
}

function ContextCard({ item, allItems, people, onViewSource }: { item: ContextItem; allItems: ContextItem[]; people: Person[]; onViewSource: (id: string) => void }) {
  const about = (item.personIds ?? []).map((id) => people.find((p) => p.id === id)?.name ?? id);
  const via = Array.from(new Set(item.sources.map((s) => s.integration).filter((x): x is NonNullable<typeof x> => !!x && x !== "document")));
  const superseded = !!item.supersededBy;
  const newer = superseded ? allItems.find((c) => c.id === item.supersededBy) : undefined;
  const EffectIcon = EFFECT_ICON[item.expectedEffect];
  const claim = item.claimType ?? "interpretation";

  return (
    <article
      className={cn(
        "flex h-full flex-col rounded-xl border border-border bg-card",
        superseded && "border-dashed bg-transparent text-muted-foreground",
      )}
    >
      <div className="flex-1 space-y-3 p-5">
        <div className="flex items-start justify-between gap-3">
          <h3 className={cn("text-sm leading-snug font-medium", superseded && "text-muted-foreground line-through decoration-muted-foreground")}>
            {item.title}
          </h3>
          {superseded && <Badge variant="outline" className="shrink-0 text-muted-foreground">Superseded</Badge>}
        </div>

        {superseded && (
          <p className="text-xs text-muted-foreground">
            Replaced by{" "}
            {newer ? (
              <a href={`#${newer.id}`} className="text-foreground/80 underline underline-offset-4 decoration-border-strong hover:decoration-foreground">{newer.title}</a>
            ) : (
              <span className="text-foreground/80">{item.supersededBy}</span>
            )}
            . Not current; kept for traceability.
          </p>
        )}

        <p className={cn("text-sm leading-relaxed text-foreground/80", superseded && "text-muted-foreground")}>{item.summary}</p>

        <div className="flex flex-wrap items-center gap-1.5">
          <Badge
            variant={claim === "interpretation" ? "outline" : "default"}
            className={cn(claim === "interpretation" && "text-muted-foreground")}
            title={claim === "interpretation" ? "Assistant interpretation, not a source statement" : `${CLAIM_LABEL[claim]} from a source`}
          >
            {CLAIM_LABEL[claim]}
          </Badge>
          <Badge variant="outline" className="text-muted-foreground" title={EFFECT_LABEL[item.expectedEffect]}>
            <EffectIcon aria-hidden />
            {EFFECT_SHORT[item.expectedEffect]}
          </Badge>
          <Badge variant="outline" className="text-muted-foreground" title={CONFIDENCE_LABEL[item.confidence]}>{CONFIDENCE_SHORT[item.confidence]}</Badge>
          {item.scope === "company" && <CompanyWideChip />}
          {via.map((v) => <IntegrationChip key={v} integration={v} />)}
        </div>

        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
          <span>{KIND_LABEL[item.kind]}</span>
          {(item.effectiveFrom || item.effectiveTo) && (
            <span className="num">
              · {item.effectiveFrom ? fmtDate(item.effectiveFrom, { year: true }) : "…"}
              {item.effectiveTo ? ` – ${fmtDate(item.effectiveTo, { year: true })}` : " onward"}
            </span>
          )}
          {about.length > 0 && <span>· About <span className="text-foreground/80">{about.join(", ")}</span></span>}
        </div>

        {item.uncertainty && (
          <p className="text-xs text-muted-foreground"><span className="text-foreground/80">Unresolved:</span> {item.uncertainty}</p>
        )}
      </div>

      {item.sources.length > 0 && (
        <details className="group border-t border-border">
          <summary className="flex cursor-pointer list-none items-center gap-2 px-5 py-2.5 text-xs text-muted-foreground transition-colors duration-300 hover:text-foreground [&::-webkit-details-marker]:hidden">
            <ChevronRight className="size-4 transition-transform group-open:rotate-90" aria-hidden />
            Sources <span className="num">({item.sources.length})</span>
          </summary>
          <ul className="divide-y divide-border border-t border-border">
            {item.sources.map((s, i) => (
              <SourceRow key={`${s.documentId}-${i}`} source={s} onView={() => onViewSource(s.documentId)} />
            ))}
          </ul>
        </details>
      )}
    </article>
  );
}

function SourceRow({ source, onView }: { source: SourceRef; onView: () => void }) {
  return (
    <li className="flex flex-col gap-2 px-5 py-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
      <div className="min-w-0 space-y-1">
        <div className="text-xs">
          <span className="font-medium text-foreground">{source.title}</span>
          {source.locator && <span className="ml-1.5 text-muted-foreground">{source.locator}</span>}
          {source.date && <span className="num ml-1.5 text-muted-foreground">· {fmtDate(source.date, { year: true })}</span>}
        </div>
        {source.excerpt && (
          <blockquote className="border-l border-border-strong pl-2.5 text-xs leading-relaxed text-muted-foreground">&ldquo;{source.excerpt}&rdquo;</blockquote>
        )}
      </div>
      <Button variant="ghost" size="xs" className="shrink-0 self-start text-muted-foreground hover:text-foreground sm:-mr-2" onClick={onView}>
        <FileText className="text-muted-foreground" /> View source
      </Button>
    </li>
  );
}
