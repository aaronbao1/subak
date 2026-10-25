"use client";
import Link from "next/link";
import { ArrowDownRight, ArrowUpRight, CheckCircle2, ChevronRight, CircleDashed, CircleHelp, Minus, Quote } from "lucide-react";
import type { ContextItem, Person, SourceRef, Team } from "@/lib/contracts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { CLAIM_LABEL, CONFIDENCE_LABEL, fmtDate, KIND_LABEL } from "@/components/team/labels";
import { Avatar, primarySource, SOURCE_META, SourceBadge, SourceLogo, sourceOf, wash } from "./source-brand";

const EFFECT = {
  increase: { Icon: ArrowUpRight, label: "Increases spend", className: "text-warning" },
  decrease: { Icon: ArrowDownRight, label: "Decreases spend", className: "text-muted-foreground" },
  neutral: { Icon: Minus, label: "Neutral", className: "text-muted-foreground" },
  unknown: { Icon: CircleHelp, label: "Effect unknown", className: "text-muted-foreground" },
} as const;

export function EffectChip({ effect, className }: { effect: ContextItem["expectedEffect"]; className?: string }) {
  const { Icon, label, className: tone } = EFFECT[effect];
  return (
    <span className={cn("inline-flex shrink-0 items-center gap-1 text-xs", tone, className)} title={label}>
      <Icon aria-hidden strokeWidth={1.75} className="size-3.5" />
      {label}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* Quote blocks, one per medium                                        */
/* ------------------------------------------------------------------ */

/**
 * The evidence itself, laid out the way it looked where it came from: a chat message with its author,
 * an email with its subject line, a task with its state, or a passage from a document with its section.
 */
export function SourceQuote({ source, compact, className }: { source: SourceRef; compact?: boolean; className?: string }) {
  const integration = sourceOf(source);
  const meta = SOURCE_META[integration];
  const text = source.excerpt;
  if (!text) return null;
  const date = source.date ? fmtDate(source.date) : undefined;

  if (meta.medium === "message") {
    const isMail = integration === "gmail" || integration === "email";
    return (
      <figure className={cn("rounded-lg border border-border px-3 py-2.5", className)} style={{ background: wash(meta.accent, 6) }}>
        {isMail && !compact && (
          <div className="mb-2 flex flex-wrap items-baseline gap-x-2 gap-y-0.5 border-b border-border/70 pb-2 text-[11px] text-muted-foreground">
            <span><span className="text-muted-foreground/70">From</span> <span className="text-foreground/90">{source.author ?? "Unknown sender"}</span></span>
            {source.locator && <span><span className="text-muted-foreground/70">To</span> <span className="text-foreground/90">{source.locator}</span></span>}
            <span className="min-w-0 basis-full truncate"><span className="text-muted-foreground/70">Subject</span> <span className="text-foreground/90">{source.title.replace(/^email:\s*/i, "")}</span></span>
          </div>
        )}
        <div className="flex gap-2.5">
          <Avatar name={source.author ?? "?"} accent={meta.accent} className={cn(compact && "size-6 text-[9px]")} />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-baseline gap-x-2 text-xs">
              <span className="font-medium text-foreground">{source.author ?? "Unknown"}</span>
              {!isMail && source.locator && <span className="text-muted-foreground">{source.locator}</span>}
              {date && <span className="num text-[11px] text-muted-foreground">{date}</span>}
            </div>
            <blockquote className={cn("mt-0.5 text-sm leading-relaxed text-foreground/90", compact && "line-clamp-2 text-xs")}>{text}</blockquote>
          </div>
        </div>
      </figure>
    );
  }

  if (meta.medium === "task") {
    const done = /done|complete|closed/i.test(source.locator ?? "");
    const StateIcon = done ? CheckCircle2 : CircleDashed;
    return (
      <figure className={cn("rounded-lg border border-border px-3 py-2.5", className)} style={{ background: wash(meta.accent, 6) }}>
        <div className="flex items-start gap-2.5">
          <StateIcon aria-hidden strokeWidth={1.75} className="mt-0.5 size-4 shrink-0" style={{ color: meta.accent }} />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-baseline gap-x-2 text-xs">
              <span className="font-medium text-foreground">{source.title.replace(/^(asana|linear|monday(\.com)?):\s*/i, "")}</span>
              {source.locator && <span className="text-muted-foreground">{source.locator}</span>}
              {date && <span className="num text-[11px] text-muted-foreground">{date}</span>}
            </div>
            <blockquote className={cn("mt-0.5 text-sm leading-relaxed text-foreground/90", compact && "line-clamp-2 text-xs")}>{text}</blockquote>
            {source.author && !compact && <div className="mt-1 text-[11px] text-muted-foreground">by {source.author}</div>}
          </div>
        </div>
      </figure>
    );
  }

  return (
    <figure className={cn("relative rounded-lg border border-border px-3 py-2.5 pl-4", className)} style={{ background: wash(meta.accent, 5) }}>
      <span aria-hidden className="absolute inset-y-2.5 left-0 w-0.5 rounded-full" style={{ background: meta.accent }} />
      <blockquote className={cn("text-sm leading-relaxed text-foreground/90", compact && "line-clamp-2 text-xs")}>
        <Quote aria-hidden strokeWidth={1.75} className="mr-1 inline size-3 -translate-y-1 text-muted-foreground/70" />
        {text}
      </blockquote>
      <figcaption className="mt-1.5 flex flex-wrap items-center gap-x-2 text-[11px] text-muted-foreground">
        <span className="truncate text-foreground/80">{source.title}</span>
        {source.locator && <span>{source.locator}</span>}
        {date && <span className="num">{date}</span>}
        {source.author && !compact && <span>· {source.author}</span>}
      </figcaption>
    </figure>
  );
}

/* ------------------------------------------------------------------ */
/* Full card (team and person pages)                                   */
/* ------------------------------------------------------------------ */

interface CardProps {
  item: ContextItem;
  /** Every context item, so a "Replaced by" line can name an item that belongs to another team. */
  allItems: ContextItem[];
  people?: Person[];
  onViewSource: (documentId: string) => void;
  className?: string;
}

export function ContextCard({ item, allItems, people = [], onViewSource, className }: CardProps) {
  const integration = primarySource(item);
  const meta = SOURCE_META[integration];
  const superseded = !!item.supersededBy;
  const newer = superseded ? allItems.find((c) => c.id === item.supersededBy) : undefined;
  const claim = item.claimType ?? "interpretation";
  const about = (item.personIds ?? []).map((id) => people.find((p) => p.id === id)?.name ?? id);
  const [lead, ...rest] = item.sources;
  const accent = superseded ? "var(--border-strong)" : meta.accent;

  return (
    <article
      className={cn(
        "relative flex h-full flex-col overflow-hidden rounded-xl border border-border bg-card transition-colors duration-300 hover:border-border-strong",
        superseded && "border-dashed bg-transparent",
        className,
      )}
    >
      <span aria-hidden className="absolute inset-y-0 left-0 w-0.5" style={{ background: accent }} />

      <div className="flex-1 space-y-3.5 p-5 pl-6">
        <div className="flex items-center justify-between gap-3">
          <SourceBadge integration={integration} locator={lead?.locator && meta.medium === "message" ? lead.locator : undefined} className={cn(superseded && "opacity-70")} />
          <div className="flex items-center gap-2">
            {superseded ? <Badge variant="outline" className="text-muted-foreground">Superseded</Badge> : <EffectChip effect={item.expectedEffect} />}
          </div>
        </div>

        <h3 className={cn("text-[15px] leading-snug font-medium text-foreground", superseded && "text-muted-foreground line-through decoration-muted-foreground")}>
          {item.title}
        </h3>

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

        {lead && <SourceQuote source={lead} className={cn(superseded && "opacity-60 grayscale")} />}

        <p className={cn("text-sm leading-relaxed", superseded ? "text-muted-foreground" : "text-foreground/80")}>{item.summary}</p>

        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
          <span title={claim === "interpretation" ? "Assistant interpretation, not a source statement" : `${CLAIM_LABEL[claim]} from a source`} className={cn(claim !== "interpretation" && "text-foreground/80")}>
            {CLAIM_LABEL[claim]}
          </span>
          <span aria-hidden>·</span>
          <span title={CONFIDENCE_LABEL[item.confidence]}>{CONFIDENCE_LABEL[item.confidence]}</span>
          <span aria-hidden>·</span>
          <span>{KIND_LABEL[item.kind]}</span>
          {(item.effectiveFrom || item.effectiveTo) && (
            <>
              <span aria-hidden>·</span>
              <span className="num">
                {item.effectiveFrom ? fmtDate(item.effectiveFrom) : "…"}
                {item.effectiveTo ? ` – ${fmtDate(item.effectiveTo)}` : " onward"}
              </span>
            </>
          )}
          {item.scope === "company" && <><span aria-hidden>·</span><span>Company-wide</span></>}
          {about.length > 0 && <><span aria-hidden>·</span><span>About <span className="text-foreground/80">{about.join(", ")}</span></span></>}
        </div>

        {item.uncertainty && (
          <p className="text-xs text-muted-foreground"><span className="text-foreground/80">Unresolved:</span> {item.uncertainty}</p>
        )}
      </div>

      {item.sources.length > 0 && (
        <footer className="border-t border-border">
          <ul className="divide-y divide-border">
            {lead && <SourceLine source={lead} onView={() => onViewSource(lead.documentId)} />}
            {rest.length > 0 && (
              <li>
                <details className="group">
                  <summary className="flex cursor-pointer list-none items-center gap-2 px-5 py-2.5 text-xs text-muted-foreground transition-colors duration-300 hover:text-foreground [&::-webkit-details-marker]:hidden">
                    <ChevronRight className="size-4 transition-transform group-open:rotate-90" aria-hidden strokeWidth={1.5} />
                    {rest.length} more {rest.length === 1 ? "source" : "sources"}
                  </summary>
                  <ul className="divide-y divide-border border-t border-border">
                    {rest.map((s, i) => (
                      <li key={`${s.documentId}-${i}`} className="px-5 py-3">
                        <SourceQuote source={s} compact />
                        <div className="mt-2 flex items-center justify-between gap-3">
                          <SourceBadge integration={sourceOf(s)} locator={s.title} size="xs" />
                          <Button variant="ghost" size="xs" className="-mr-2 text-muted-foreground hover:text-foreground" onClick={() => onViewSource(s.documentId)}>Open</Button>
                        </div>
                      </li>
                    ))}
                  </ul>
                </details>
              </li>
            )}
          </ul>
        </footer>
      )}
    </article>
  );
}

function SourceLine({ source, onView }: { source: SourceRef; onView: () => void }) {
  const integration = sourceOf(source);
  const meta = SOURCE_META[integration];
  return (
    <li className="flex items-center justify-between gap-3 px-5 py-2">
      <span className="flex min-w-0 items-center gap-2 text-xs text-muted-foreground">
        <SourceLogo integration={integration} className="size-3.5" />
        <span className="truncate">{source.title}</span>
        {source.date && <span className="num shrink-0">· {fmtDate(source.date, { year: true })}</span>}
      </span>
      <Button variant="ghost" size="xs" className="-mr-2 shrink-0 text-muted-foreground hover:text-foreground" onClick={onView}>
        Open {meta.noun} <ChevronRight className="size-3.5" strokeWidth={1.5} />
      </Button>
    </li>
  );
}

/* ------------------------------------------------------------------ */
/* Compact card (overview)                                             */
/* ------------------------------------------------------------------ */

export function ContextCardCompact({ item, team, person, onOpen, className }: { item: ContextItem; team?: Team; person?: Person; onOpen: () => void; className?: string }) {
  const integration = primarySource(item);
  const meta = SOURCE_META[integration];
  const lead = item.sources[0];
  return (
    <article
      className={cn(
        "group relative flex h-full flex-col gap-3 overflow-hidden rounded-xl border border-border bg-card p-4 pl-5 text-left transition-colors duration-300 hover:border-border-strong",
        className,
      )}
    >
      <span aria-hidden className="absolute inset-y-0 left-0 w-0.5" style={{ background: meta.accent }} />
      <div className="flex items-center justify-between gap-3">
        <SourceBadge integration={integration} size="xs" locator={lead?.locator && meta.medium === "message" ? lead.locator : undefined} />
        <EffectChip effect={item.expectedEffect} className="text-[11px]" />
      </div>
      <button type="button" onClick={onOpen} className="text-left focus-visible:outline-none">
        <h3 className="line-clamp-2 text-sm leading-snug font-medium text-foreground group-hover:underline group-hover:decoration-border-strong group-hover:underline-offset-4">{item.title}</h3>
      </button>
      {lead?.excerpt && <SourceQuote source={lead} compact />}
      <div className="mt-auto flex items-center justify-between gap-3 pt-1 text-[11px] text-muted-foreground">
        <span className="flex min-w-0 items-center gap-1.5">
          {team ? (
            <Link href={`/teams/${team.id}`} className="flex min-w-0 items-center gap-1.5 hover:text-foreground">
              <span aria-hidden className="size-1.5 shrink-0 rounded-full" style={{ background: team.color }} />
              <span className="truncate">{team.name}</span>
            </Link>
          ) : (
            <span>Company-wide</span>
          )}
          {person && <span className="truncate">· {person.name}</span>}
        </span>
        {lead?.date && <span className="num shrink-0">{fmtDate(lead.date)}</span>}
      </div>
    </article>
  );
}
