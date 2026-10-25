"use client";
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import type { Unit } from "@/lib/contracts";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { CLAIM_LABEL, CONFIDENCE_LABEL, fmtDate } from "@/components/team/labels";
import { SourceBadge, SourceLogos, sourceOf } from "@/components/context/source-brand";
import { SIGNAL_LABEL } from "@/components/person/signal-badges";
import { rowNet, type EvidenceRow } from "./derive";
import { attributionText, CATEGORY_LABEL, dateRangeText, magnitudeText, signedAmount, signedPct } from "./labels";
import { DivergingBar, EFFECT_TEXT, EffectArrow, InitialsStack, TeamDots } from "./marks";

interface Props {
  row: EvidenceRow;
  unit: Unit;
  /** Largest |applied amount| in the feed, so every row's bar shares one scale. */
  max: number;
  open: boolean;
  onToggle: () => void;
  onViewSource: (documentId: string) => void;
  animate: boolean;
}

const BREAKDOWN_LIMIT = 6;

/**
 * One piece of evidence as a single glanceable row: effect · title · who · applied amount · date.
 * Everything else (summary, sources, basis, attribution, per-team split) opens beneath it.
 */
export function EvidenceRowItem({ row, unit, max, open, onToggle, onViewSource, animate }: Props) {
  const { item, superseded, teams, people } = row;
  const net = superseded ? undefined : rowNet(row);
  const detailId = `${item.id}-detail`;
  // Interpretations (assistant reading, not an observed event) show a hollow arrow and an italic title at rest.
  const interpretation = item.claimType === "interpretation";
  const ariaLabel = [
    interpretation && "Interpretation",
    item.title,
    EFFECT_TEXT[item.expectedEffect],
    superseded ? "Superseded" : net !== undefined ? `${signedAmount(net, unit, { compact: true })} applied` : undefined,
    item.effectiveFrom && fmtDate(item.effectiveFrom),
  ].filter(Boolean).join(" · ");

  return (
    <div id={item.id} className="scroll-mt-20">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={detailId}
        aria-label={ariaLabel}
        onClick={onToggle}
        className={cn(
          "grid h-11 w-full grid-cols-[16px_minmax(0,1fr)_auto_auto] items-center gap-3 px-4 text-left transition-colors duration-300 hover:bg-popover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:ring-inset sm:grid-cols-[16px_minmax(0,1fr)_72px_112px_48px]",
          open && "bg-popover",
        )}
      >
        <EffectArrow effect={item.expectedEffect} muted={superseded} hollow={interpretation} />
        <span className="flex min-w-0 items-center gap-2">
          <span className={cn("truncate text-sm", interpretation && "italic", superseded ? "text-muted-foreground line-through decoration-muted-foreground" : "text-foreground")}>
            {item.title}
          </span>
          <SourceLogos sources={item.sources} className={cn(superseded && "opacity-50")} />
        </span>
        <span className="hidden items-center sm:flex">
          {people.length > 0 ? <InitialsStack people={people} teams={teams} /> : row.scope === "company" ? <span className="text-xs text-muted-foreground">All teams</span> : <TeamDots teams={teams} />}
        </span>
        <Amount row={row} net={net} unit={unit} max={max} animate={animate} />
        <span className="num hidden text-right text-xs text-muted-foreground sm:block">{item.effectiveFrom ? fmtDate(item.effectiveFrom) : "—"}</span>
      </button>
      {open && <Detail id={detailId} row={row} unit={unit} onViewSource={onViewSource} />}
    </div>
  );
}

function Amount({ row, net, unit, max, animate }: { row: EvidenceRow; net?: number; unit: Unit; max: number; animate: boolean }) {
  if (row.superseded) return <span className="text-right text-[11px] text-muted-foreground">Superseded</span>;
  if (net !== undefined) {
    return (
      <span className="flex items-center justify-end gap-2" title="Applied by the forecast">
        <DivergingBar value={net} max={max} className="hidden w-10 sm:block" animate={animate} />
        <span className="num w-14 text-right text-xs text-foreground">{signedAmount(net, unit, { compact: true })}</span>
      </span>
    );
  }
  const m = row.item.magnitude;
  const stated = typeof m?.amount === "number" ? signedAmount(m.amount, unit, { compact: true }) : typeof m?.pct === "number" ? signedPct(m.pct) : undefined;
  return (
    <span className="num text-right text-xs text-muted-foreground" title={stated ? "Stated size, not applied by a forecast" : "Size not stated"}>
      {stated ?? "—"}
    </span>
  );
}

function Detail({ id, row, unit, onViewSource }: { id: string; row: EvidenceRow; unit: Unit; onViewSource: (documentId: string) => void }) {
  const { item, superseded, newer, teams, people, adjustments } = row;
  const claim = item.claimType ?? "interpretation";
  const magnitude = magnitudeText(item.magnitude, unit);
  const range = dateRangeText(item);
  const attribution = attributionText(item);
  const meta = [
    CLAIM_LABEL[claim],
    CONFIDENCE_LABEL[item.confidence],
    item.signal ? SIGNAL_LABEL[item.signal] : CATEGORY_LABEL[row.category],
    attribution,
    range,
  ].filter(Boolean);

  const sorted = [...adjustments].sort((a, b) => Math.abs(b.amount) - Math.abs(a.amount));
  const shown = sorted.slice(0, BREAKDOWN_LIMIT);
  const max = Math.max(1, ...adjustments.map((a) => Math.abs(a.amount)));

  return (
    <div id={id} className="space-y-3 bg-popover/40 px-4 pt-1 pb-4 pl-11 text-sm">
      {superseded && (
        <p className="text-xs text-muted-foreground">
          Replaced by{" "}
          {newer ? (
            <a href={`#${newer.id}`} className="text-foreground/80 underline underline-offset-4 decoration-border-strong hover:decoration-foreground">{newer.title}</a>
          ) : (
            <span className="text-foreground/80">{item.supersededBy}</span>
          )}
        </p>
      )}

      <p className={cn("leading-relaxed", superseded ? "text-muted-foreground" : "text-foreground/80")}>{item.summary}</p>

      <p className="text-xs text-muted-foreground">{meta.join(" · ")}</p>
      {magnitude && <p className="num text-xs text-muted-foreground">Stated {magnitude}</p>}
      {item.uncertainty && <p className="text-xs text-muted-foreground">Open: {item.uncertainty}</p>}

      {people.length > 0 && (
        <p className="flex flex-wrap gap-x-3 gap-y-1 text-xs">
          {people.map((p) => (
            <Link key={p.id} href={`/teams/${p.teamId}/people/${p.id}`} className="text-foreground/80 underline-offset-4 decoration-border-strong hover:underline">{p.name}</Link>
          ))}
        </p>
      )}

      {shown.length > 0 && !superseded && (
        <ul className="space-y-1.5" aria-label="Applied by team">
          {shown.map((a) => {
            const team = teams.find((t) => t.id === a.teamId);
            return (
              <li key={`${a.teamId}-${a.level}`} className="grid grid-cols-[8px_minmax(0,9rem)_minmax(0,1fr)_4.5rem] items-center gap-2 text-xs" title={a.note ?? (a.level === "person" ? "Summed from people" : undefined)}>
                <span aria-hidden className="size-2 rounded-full" style={{ background: team?.color ?? "var(--border-strong)" }} />
                <span className="truncate text-foreground/80">{team?.name ?? a.teamId}</span>
                <DivergingBar value={a.amount} max={max} />
                <span className="num text-right text-foreground">{signedAmount(a.amount, a.unit, { compact: true })}</span>
              </li>
            );
          })}
          {sorted.length > shown.length && <li className="num pl-4 text-[11px] text-muted-foreground">+{sorted.length - shown.length} more</li>}
        </ul>
      )}

      {item.sources.length > 0 && (
        <ul className="divide-y divide-border rounded-md border border-border">
          {item.sources.map((s, i) => (
            <li key={`${s.documentId}-${i}`} className="flex items-center justify-between gap-3 px-3 py-2" title={s.excerpt}>
              <span className="flex min-w-0 items-center gap-2 text-xs">
                <SourceBadge integration={sourceOf(s)} size="xs" />
                <span className="truncate text-foreground/80">{s.title}</span>
                {s.date && <span className="num shrink-0 text-muted-foreground">{fmtDate(s.date, { year: true })}</span>}
              </span>
              <Button variant="ghost" size="xs" className="-mr-2 shrink-0 text-muted-foreground hover:text-foreground" onClick={() => onViewSource(s.documentId)}>
                Open <ChevronRight className="size-3.5" strokeWidth={1.5} />
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
