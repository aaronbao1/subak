"use client";
import { useMemo, useState } from "react";
import { ArrowDownRight, ArrowUpRight, CircleHelp, FileText, History, Minus } from "lucide-react";
import type { ContextItem, SourceRef, Team } from "@/lib/contracts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { CLAIM_LABEL, CONFIDENCE_LABEL, EFFECT_LABEL, fmtDate } from "./labels";
import { SourceSheet } from "./source-sheet";

interface Props {
  team: Team;
  items: ContextItem[];
  /** Every context item, so a "Superseded by" line can name an item that belongs to another team. */
  allItems: ContextItem[];
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

/** One card per context item for this team; superseded items are muted and sorted last. */
export function ContextCards({ team, items, allItems }: Props) {
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
    <section className="space-y-3" aria-labelledby="context-heading">
      <div>
        <h2 id="context-heading" className="text-base font-semibold tracking-tight">Context and evidence</h2>
        <p className="text-sm text-muted-foreground">
          Plans, project documents and correspondence that bear on {team.name}&apos;s spend. Each claim links to its source.
        </p>
      </div>

      {sorted.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-2 py-8 text-center">
            <FileText className="size-5 text-muted-foreground" />
            <div className="font-medium">No context for this team</div>
            <p className="max-w-sm text-sm text-muted-foreground">
              No plans, documents or correspondence have been linked to {team.name} for this period.
            </p>
          </CardContent>
        </Card>
      ) : (
        <ul className="grid gap-3 lg:grid-cols-2">
          {sorted.map((item) => (
            <li key={item.id} id={item.id} className="scroll-mt-20">
              <ContextCard item={item} allItems={allItems} onViewSource={setOpenDoc} />
            </li>
          ))}
        </ul>
      )}

      <SourceSheet documentId={openDoc} onClose={() => setOpenDoc(undefined)} />
    </section>
  );
}

function ContextCard({ item, allItems, onViewSource }: { item: ContextItem; allItems: ContextItem[]; onViewSource: (id: string) => void }) {
  const superseded = !!item.supersededBy;
  const newer = superseded ? allItems.find((c) => c.id === item.supersededBy) : undefined;
  const EffectIcon = EFFECT_ICON[item.expectedEffect];
  const claim = item.claimType ?? "interpretation";

  return (
    <Card size="sm" className={cn("h-full", superseded && "bg-muted/40 ring-dashed text-muted-foreground")}>
      <CardHeader>
        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          <Badge variant={claim === "interpretation" ? "secondary" : "outline"} className="font-normal" title={claim === "interpretation" ? "Assistant interpretation, not a source statement" : undefined}>
            {CLAIM_LABEL[claim]}
          </Badge>
          <span className="text-muted-foreground">{KIND_LABEL[item.kind]}</span>
          {superseded && (
            <Badge variant="outline" className="ml-auto gap-1 font-normal text-muted-foreground"><History className="size-3" /> Superseded</Badge>
          )}
        </div>
        <CardTitle className={cn(superseded && "text-muted-foreground line-through decoration-muted-foreground/40")}>{item.title}</CardTitle>
        {superseded && (
          <CardDescription className="text-xs">
            Superseded by{" "}
            {newer ? (
              <a href={`#${newer.id}`} className="font-medium text-foreground underline underline-offset-2">{newer.title}</a>
            ) : (
              <span className="font-medium">{item.supersededBy}</span>
            )}
            . Not current; shown for traceability.
          </CardDescription>
        )}
      </CardHeader>
      <CardContent className="space-y-3">
        <p className={cn("text-sm", superseded && "text-muted-foreground")}>{item.summary}</p>

        <div className="flex flex-wrap items-center gap-1.5">
          <Badge variant="outline" className="gap-1 font-normal" title={EFFECT_LABEL[item.expectedEffect]}>
            <EffectIcon className="size-3" />
            {item.expectedEffect === "unknown" ? "Effect unknown" : `${item.expectedEffect[0].toUpperCase()}${item.expectedEffect.slice(1)}`}
          </Badge>
          <Badge variant="outline" className="font-normal" title={CONFIDENCE_LABEL[item.confidence]}>
            {item.confidence} confidence
          </Badge>
          {(item.effectiveFrom || item.effectiveTo) && (
            <span className="text-xs text-muted-foreground">
              Effective {item.effectiveFrom ? fmtDate(item.effectiveFrom, { year: true }) : "…"}
              {item.effectiveTo ? ` – ${fmtDate(item.effectiveTo, { year: true })}` : " onward"}
            </span>
          )}
        </div>

        {item.uncertainty && (
          <p className="text-xs text-muted-foreground"><span className="font-medium">Still unresolved:</span> {item.uncertainty}</p>
        )}

        {item.sources.length > 0 && (
          <div className="space-y-2 border-t pt-3">
            <div className="text-[11px] uppercase tracking-wide text-muted-foreground">Sources</div>
            <ul className="space-y-2">
              {item.sources.map((s, i) => (
                <SourceRow key={`${s.documentId}-${i}`} source={s} onView={() => onViewSource(s.documentId)} />
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function SourceRow({ source, onView }: { source: SourceRef; onView: () => void }) {
  return (
    <li className="flex flex-col gap-1.5 sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0 space-y-0.5">
        <div className="text-sm font-medium">
          {source.title}
          {source.locator && <span className="ml-1 text-xs font-normal text-muted-foreground">{source.locator}</span>}
        </div>
        {source.date && <div className="text-xs text-muted-foreground">{fmtDate(source.date, { year: true })}</div>}
        {source.excerpt && (
          <blockquote className="border-l-2 pl-2 text-xs text-muted-foreground italic">&ldquo;{source.excerpt}&rdquo;</blockquote>
        )}
      </div>
      <Button variant="outline" size="xs" className="shrink-0 self-start" onClick={onView}>
        <FileText /> View source
      </Button>
    </li>
  );
}
