"use client";
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import type { Team, Unit } from "@/lib/contracts";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { CLAIM_LABEL, CONFIDENCE_LABEL, fmtDate, Tag } from "@/components/team/labels";
import { EffectChip } from "@/components/context/context-card";
import { primarySource, SourceBadge, sourceOf } from "@/components/context/source-brand";
import { SIGNAL_LABEL } from "@/components/person/signal-badges";
import type { EvidenceRow, ItemAdjustment } from "./derive";
import { attributionText, CATEGORY_LABEL, dateRangeText, magnitudeText, signedAmount } from "./labels";

interface Props {
  row: EvidenceRow;
  unit: Unit;
  onViewSource: (documentId: string) => void;
  className?: string;
}

const MONO_LINE = "num flex flex-wrap items-center gap-x-2 gap-y-1 text-xs";
/** Above this many team adjustments (company-scope items), the per-team lines collapse into one summary. */
const MANY_TEAMS = 2;
const CHIP_LIMIT = 6;

/**
 * One line for an item that moved many teams: the signed total and count, then the per-team amounts as inline
 * text (largest magnitude first, at most CHIP_LIMIT, "+N more"), and the forecast's note once rather than per team.
 */
/** Per-team notes usually differ only by a trailing amount ("…: +$81"); drop it so the note dedupes to one line. */
const TRAILING_AMOUNT = /\s*[:—–-]\s*[+−-]?\$?[\d,.]+\s*[A-Za-z%]*\s*$/;

function AdjustmentSummary({ adjustments, teams, title }: { adjustments: ItemAdjustment[]; teams: Team[]; title: string }) {
  const total = adjustments.reduce((s, a) => s + a.amount, 0);
  const unit = adjustments[0].unit;
  const sorted = [...adjustments].sort((a, b) => Math.abs(b.amount) - Math.abs(a.amount));
  const shown = sorted.slice(0, CHIP_LIMIT);
  const more = sorted.length - shown.length;
  const notes = [...new Set(adjustments.map((a) => a.note?.replace(TRAILING_AMOUNT, "").trim()).filter((n): n is string => !!n && n !== title))];
  return (
    <div className={cn(MONO_LINE, "flex-col items-start gap-y-1")}>
      <p className="inline-flex flex-wrap items-center gap-x-1.5">
        <span className="text-muted-foreground">Moves</span>
        <span className="text-foreground">{adjustments.length} team projections</span>
        <span className="text-muted-foreground">by</span>
        <span className={cn("text-foreground", total > 0 && "text-warning")}>{signedAmount(total, unit)}</span>
        <span className="text-muted-foreground">in total</span>
      </p>
      <ul className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-muted-foreground">
        {shown.map((a, i) => (
          <li key={`${a.teamId}-${a.level}`} className="inline-flex items-center gap-x-2">
            {i > 0 && <span aria-hidden>·</span>}
            <span><span className="text-foreground/80">{teams.find((t) => t.id === a.teamId)?.name ?? a.teamId}</span> {signedAmount(a.amount, a.unit)}</span>
          </li>
        ))}
        {more > 0 && <li className="inline-flex items-center gap-x-2"><span aria-hidden>·</span><span>+{more} more</span></li>}
      </ul>
      {notes.map((n) => <p key={n} className="text-muted-foreground">— {n}</p>)}
    </div>
  );
}

/**
 * One piece of evidence: what it claims, who it touches, how big the stated effect is, and how much a forecast
 * actually moved for it. Superseded items stay in the feed, struck through and pointing at their replacement.
 */
export function EvidenceCard({ row, unit, onViewSource, className }: Props) {
  const { item, superseded, newer, teams, people, adjustments } = row;
  const claim = item.claimType ?? "interpretation";
  const integration = primarySource(item);
  const magnitude = magnitudeText(item.magnitude, unit);
  const range = dateRangeText(item);
  const attribution = attributionText(item);
  const sources = item.sources;
  // "Pricing" beside "Pricing change" reads doubled; the signal label already carries the category word.
  const categoryRepeated = !!item.signal && SIGNAL_LABEL[item.signal].toLowerCase().includes(CATEGORY_LABEL[row.category].toLowerCase());

  return (
    <article
      id={item.id}
      aria-labelledby={`${item.id}-title`}
      className={cn(
        "scroll-mt-20 rounded-xl border border-border bg-card transition-colors duration-300 hover:border-border-strong",
        superseded && "border-dashed bg-transparent",
        className,
      )}
    >
      <div className="space-y-3 p-5">
        <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
          <h3 id={`${item.id}-title`} className={cn("min-w-0 text-base leading-snug font-medium", superseded && "text-muted-foreground line-through decoration-muted-foreground")}>
            {item.title}
          </h3>
          {superseded ? <Badge variant="outline" className="shrink-0 text-muted-foreground">Superseded</Badge> : <EffectChip effect={item.expectedEffect} className="shrink-0" />}
        </div>

        {superseded && (
          <p className="text-xs text-muted-foreground">
            Replaced by{" "}
            {newer ? (
              <a href={`#${newer.id}`} className="text-foreground/80 underline underline-offset-4 decoration-border-strong hover:decoration-foreground">{newer.title}</a>
            ) : (
              <span className="text-foreground/80">{item.supersededBy}</span>
            )}
            . Not current; never cited in the projection.
          </p>
        )}

        <p className={cn("text-sm leading-relaxed", superseded ? "text-muted-foreground" : "text-foreground/80")}>{item.summary}</p>

        {/* Badge row: every qualifier is text, so nothing here depends on color. */}
        <div className="flex flex-wrap items-center gap-1.5">
          <Tag title={claim === "interpretation" ? "Assistant interpretation, not a source statement" : `${CLAIM_LABEL[claim]} from a source`} className={cn(claim !== "interpretation" && "text-foreground/80")}>
            {CLAIM_LABEL[claim]}
          </Tag>
          <Tag>{CONFIDENCE_LABEL[item.confidence]}</Tag>
          {!categoryRepeated && <Tag title={item.category ? "Evidence category" : "No category stated; grouped as a project item"}>{CATEGORY_LABEL[row.category]}</Tag>}
          {item.signal && <Tag title="Typed reason the usage moves">{SIGNAL_LABEL[item.signal]}</Tag>}
          {sources.length > 0 && (
            <span className="inline-flex h-6 items-center rounded-md border border-border bg-popover px-2">
              <SourceBadge integration={integration} size="xs" />
            </span>
          )}
        </div>

        {/* Impact line: who it touches, and the stated size. */}
        <div className={cn(MONO_LINE, superseded ? "text-muted-foreground" : "text-foreground/80")}>
          <span className="text-muted-foreground">Affects</span>
          {people.length > 0 ? (
            people.map((p, i) => {
              const team = teams.find((t) => t.id === p.teamId);
              return (
                <span key={p.id} className="inline-flex items-center gap-1.5">
                  {i > 0 && <span aria-hidden className="text-muted-foreground">·</span>}
                  <Link href={`/teams/${p.teamId}/people/${p.id}`} className="underline-offset-4 decoration-border-strong hover:underline">{p.name}</Link>
                  {team && <span className="text-muted-foreground">({team.name})</span>}
                </span>
              );
            })
          ) : row.scope === "company" ? (
            <span>Company-wide · {teams.length} {teams.length === 1 ? "team" : "teams"}</span>
          ) : teams.length > 0 ? (
            teams.map((t, i) => (
              <span key={t.id} className="inline-flex items-center gap-1.5">
                {i > 0 && <span aria-hidden className="text-muted-foreground">·</span>}
                <span aria-hidden className="size-1.5 shrink-0 rounded-full" style={{ background: t.color }} />
                <Link href={`/teams/${t.id}`} className="underline-offset-4 decoration-border-strong hover:underline">{t.name}</Link>
              </span>
            ))
          ) : (
            <span className="text-muted-foreground">no team named</span>
          )}
          <span aria-hidden className="text-muted-foreground">·</span>
          {magnitude ? <span>{magnitude}</span> : <span className="text-muted-foreground">size not stated</span>}
          {item.effectiveFrom && <><span aria-hidden className="text-muted-foreground">·</span><span>from {fmtDate(item.effectiveFrom)}</span></>}
        </div>

        {/* Adjustment line: only when a forecast actually lists this item. */}
        {adjustments.length > 0 && adjustments.length <= MANY_TEAMS && (
          <ul className={cn(MONO_LINE, "flex-col items-start gap-y-0.5")}>
            {adjustments.map((a) => {
              const team = teams.find((t) => t.id === a.teamId);
              return (
                <li key={`${a.teamId}-${a.level}`} title={a.note} className="inline-flex flex-wrap items-center gap-x-1.5">
                  <span className="text-muted-foreground">Moves the</span>
                  <span className="text-foreground">{team?.name ?? a.teamId}</span>
                  <span className="text-muted-foreground">projection</span>
                  <span className={cn("text-foreground", a.amount > 0 && "text-warning")}>{signedAmount(a.amount, a.unit)}</span>
                  {a.level === "person" && <span className="text-muted-foreground">(summed from people)</span>}
                  {a.note && <span className="text-muted-foreground">— {a.note}</span>}
                </li>
              );
            })}
          </ul>
        )}
        {adjustments.length > MANY_TEAMS && <AdjustmentSummary adjustments={adjustments} teams={teams} title={item.title} />}

        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
          {range && <span className="num">{range}</span>}
          {range && attribution && <span aria-hidden>·</span>}
          {attribution && <span className="text-foreground/80">{attribution}</span>}
          {!range && !attribution && <span>No date or attribution stated</span>}
        </div>

        {item.uncertainty && (
          <p className="text-xs text-muted-foreground"><span className="text-foreground/80">Unresolved:</span> {item.uncertainty}</p>
        )}
      </div>

      {sources.length > 0 && (
        <footer className="border-t border-border">
          <details className="group">
            <summary className="flex cursor-pointer list-none items-center gap-2 px-5 py-2.5 text-xs text-muted-foreground transition-colors duration-300 hover:text-foreground [&::-webkit-details-marker]:hidden">
              <ChevronRight className="size-4 transition-transform duration-150 group-open:rotate-90" aria-hidden strokeWidth={1.5} />
              Sources ({sources.length})
            </summary>
            <ul className="divide-y divide-border border-t border-border">
              {sources.map((s, i) => (
                <li key={`${s.documentId}-${i}`} className="flex items-center justify-between gap-3 px-5 py-2.5">
                  <span className="flex min-w-0 flex-col gap-0.5 text-xs">
                    <span className="flex min-w-0 items-center gap-2">
                      <SourceBadge integration={sourceOf(s)} size="xs" />
                      <span className="truncate text-foreground/80">{s.title}</span>
                      {s.date && <span className="num shrink-0 text-muted-foreground">{fmtDate(s.date, { year: true })}</span>}
                    </span>
                    {s.excerpt && <span className="line-clamp-2 text-muted-foreground">&ldquo;{s.excerpt}&rdquo;</span>}
                  </span>
                  <Button variant="ghost" size="xs" className="-mr-2 shrink-0 text-muted-foreground hover:text-foreground" onClick={() => onViewSource(s.documentId)}>
                    Open <ChevronRight className="size-3.5" strokeWidth={1.5} />
                  </Button>
                </li>
              ))}
            </ul>
          </details>
        </footer>
      )}
    </article>
  );
}
