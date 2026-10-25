"use client";
import { useState, type ReactNode } from "react";
import Link from "next/link";
import type { Unit } from "@/lib/contracts";
import { Skeleton } from "@/components/ui/skeleton";
import type { StatTone } from "@/components/shared/stat-tile";
import { useCountUp, useMounted, usePrefersReducedMotion, useProgress } from "@/components/shared/motion";
import { teamStatus } from "@/components/team/labels";
import { formatAmount, formatPct, pct } from "@/lib/format";
import { cn } from "@/lib/utils";
import { dateLabel, type TeamSummary } from "./derive";

/*
 * Timeline on first paint (ms):
 *      0 →  900   total spend counts up from 0; the recorded (solid) bar segment grows to the spent width;
 *                 the "97% of $206,000 allotted" caption counts alongside it
 *   1400 → 2400   projected counts from the current spend to the projection while the dashed segment
 *                 extends from the recorded end with a pulsing marker; an overrun appears once the marker
 *                 passes the Allotted mark; the bar caption reads "Calculating projection…"
 *   2400          caption switches to "Projected 91% of the allotment"
 * Later changes (an applied proposal) tick the numbers in place and re-grow only the segment whose value moved.
 */
const COUNT_MS = 900;
const CALC_DELAY_MS = COUNT_MS + 500;
const CALC_MS = 1000;

export interface HeroProps {
  unit: Unit;
  spent: number;
  /** Sum of allocations; undefined when there are no budgets. */
  envelope?: number;
  /** Sum of available full-period projections; undefined when none is available. */
  projected?: number;
  projectedTeamCount: number;
  unavailableCount: number;
  /** Names of teams with no projection, so the hero can say which ones are excluded from the projected figure. */
  unavailableTeams?: string[];
  teamCount: number;
  periodLabel?: string;
  periodRange?: string;
  asOf?: string;
  /** Accepted for existing callers; no longer rendered. */
  hasPlaceholder?: boolean;
  /** Per-team summaries, so the hero can name the teams whose projection exceeds their allocation. */
  summaries?: TeamSummary[];
}

/**
 * One panel that answers "is the company on track this period?".
 * Total spend is the single hero figure, with the share of the allotment it represents directly underneath;
 * the projection sits beside it as a smaller figure and visibly derives from the current spend on load.
 * Spent is drawn solid, the projection as a dashed extension, the total allocation as the "Allotted" marker.
 * When the projection exceeds the allocation the scale widens so the overrun is visible past the marker.
 * (`envelope` is the contract's name for the summed allocations; the UI says "allotment".)
 */
export function Hero(p: HeroProps) {
  const hasEnvelope = typeof p.envelope === "number" && p.envelope > 0;
  const hasProjection = typeof p.projected === "number";
  const envelope = hasEnvelope ? (p.envelope as number) : undefined;
  const projected = hasProjection ? (p.projected as number) : undefined;
  const over = envelope !== undefined && projected !== undefined ? projected - envelope : undefined;
  const isOver = over !== undefined && over > 0;
  // Spent: red once it passes the allocation, amber within 10% of it. Projected: red over, green within.
  const spentTone: StatTone = envelope === undefined ? "neutral" : p.spent > envelope ? "over" : p.spent >= envelope * 0.9 ? "close" : "neutral";
  const projectedTone: StatTone = envelope === undefined || projected === undefined ? "neutral" : projected > envelope ? "over" : "under";
  const likelyOver = (p.summaries ?? []).filter((s) => teamStatus(s.budget, s.forecast, s.spent) === "likely_over").map((s) => s.team.name);
  const excluded = p.unavailableCount > 0 ? excludedSentence(p.unavailableCount, p.unavailableTeams ?? []) : undefined;

  // The first projection is derived from the current spend (delayed count from spent); once it has changed, later values tick in place.
  const [initialProjected] = useState(projected);
  const [projectionChanged, setProjectionChanged] = useState(false);
  if (!projectionChanged && projected !== initialProjected) setProjectionChanged(true);
  const firstProjection = !projectionChanged;
  const projectedShown = useCountUp(projected ?? 0, firstProjection ? { from: p.spent, delay: CALC_DELAY_MS, duration: CALC_MS } : { duration: COUNT_MS });
  const envelopeShown = useCountUp(envelope ?? 0, { duration: COUNT_MS });
  const spentShown = useCountUp(p.spent, { duration: COUNT_MS });
  const spentPctShown = useCountUp(envelope !== undefined ? pct(p.spent, envelope) : 0, { duration: COUNT_MS });
  // Eased 0..1 for the dashed segment; keyed on the projection so only that segment re-grows when it changes.
  const calc = useProgress(firstProjection
    ? { duration: CALC_MS, delay: CALC_DELAY_MS, key: projected ?? 0, enabled: projected !== undefined }
    : { duration: COUNT_MS, key: projected ?? 0, enabled: projected !== undefined });
  const reduce = usePrefersReducedMotion();
  const mounted = useMounted();
  const calculating = mounted && !reduce && projected !== undefined && calc < 1;

  const projectionCaption = over !== undefined
    ? isOver ? `Projected ${formatAmount(over, p.unit)} over the allotment` : `Projected ${formatPct(pct(projected as number, envelope as number))} of the allotment`
    : "No projection to compare";

  return (
    <section aria-label="Company spend summary" className="min-w-0 rounded-xl border border-border bg-card p-5">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <span className="eyebrow">Company spend</span>
        <span className="truncate text-xs text-muted-foreground" title={p.periodRange}>
          {p.periodLabel ?? "Period not set"}
          {p.periodRange && <span className="num hidden sm:inline"> · {p.periodRange}</span>}
        </span>
        <span className="num text-xs text-muted-foreground" title={p.asOf}>{p.asOf ? `as of ${dateLabel(p.asOf)}` : "no complete day yet"}</span>      </div>

      {/*
        Two figures on one shared number line. Rows: labels, numbers, captions. Both numbers are vertically
        centered in the middle row, so the straight connector between them points exactly at the projection.
        Below sm the grid is one column and DOM order (label, number, caption per figure) stacks naturally.
      */}
      <div className="mt-5 grid grid-cols-1 gap-x-5 gap-y-2 sm:grid-cols-[minmax(0,auto)_minmax(120px,1fr)_minmax(0,auto)] md:gap-x-6">
        {/* Current spend */}
        <span className="eyebrow sm:col-start-1 sm:row-start-1 sm:self-end">Total spend to date</span>
        <span className="num truncate text-5xl leading-none font-medium text-foreground sm:col-start-1 sm:row-start-2 sm:self-center md:text-[56px]">
          <Reserved final={formatAmount(p.spent, p.unit)}>{formatAmount(spentShown, p.unit)}</Reserved>
        </span>
        <Caption tone={spentTone} className="sm:col-start-1 sm:row-start-3">
          {hasEnvelope
            ? <span className="num">{formatPct(spentPctShown)} of {formatAmount(envelopeShown, p.unit)} allotted</span>
            : "Add budgets to compare against an allotment"}
        </Caption>

        {/* Current → projected connector, centered on the number row. */}
        {hasProjection && (
          <>
            <Connector progress={calc} calculating={calculating} landed={mounted && calc >= 1} className="hidden sm:col-start-2 sm:row-start-2 sm:block sm:self-center" />
            <span className="num hidden text-center text-[11px] text-muted-foreground sm:col-start-2 sm:row-start-3 sm:block">from current spend</span>
          </>
        )}

        {/* Projection */}
        <span className="mt-3 inline-flex items-center gap-1.5 sm:col-start-3 sm:row-start-1 sm:mt-0 sm:self-end">
          <span className="eyebrow">Projected for period</span>
          {calculating && <span className="animate-pulse-dot size-1.5 rounded-full bg-foreground" aria-hidden />}
          {calculating && <span className="num text-[11px] text-muted-foreground" aria-live="polite">updating</span>}
        </span>
        <span className={cn("num truncate leading-none font-medium sm:col-start-3 sm:row-start-2 sm:self-center", hasProjection ? "text-[28px] text-foreground md:text-[32px]" : "text-lg text-muted-foreground")}>
          {hasProjection ? <Reserved final={formatAmount(projected as number, p.unit)}>{formatAmount(projectedShown, p.unit)}</Reserved> : "No projection"}
        </span>
        {over !== undefined && (
          <Caption tone={projectedTone} className={cn("transition-opacity duration-300 sm:col-start-3 sm:row-start-3", calculating && "opacity-0")}>
            <span className="num">{isOver ? `+${formatAmount(over, p.unit)} over allotment` : `${formatAmount(-over, p.unit)} under allotment`}</span>
          </Caption>
        )}
      </div>

      {hasEnvelope && (
        <>
          <EnvelopeBar spent={p.spent} projected={projected} envelope={envelope as number} progress={calc} calculating={calculating} />
          <p className="num mt-2 min-h-4 text-[11px] text-muted-foreground" aria-live="polite">
            {!mounted ? "" : calculating ? "Calculating projection…" : projectionCaption}
          </p>
        </>
      )}

      {/* One caption row: the teams likely over (and any excluded) on the left, the way to the evidence on the right. */}
      <div className="mt-2 flex flex-wrap items-baseline gap-x-4 gap-y-1 text-xs text-muted-foreground">
        {(likelyOver.length > 0 || excluded) && (
          <p className="min-w-0">
            {likelyOver.length > 0 && (
              <span className="inline-flex items-center gap-1.5">
                <span className="size-1.5 shrink-0 rounded-full bg-destructive" aria-hidden />
                {likelyOverSentence(likelyOver)}
              </span>
            )}
            {likelyOver.length > 0 && excluded && " · "}
            {excluded}
          </p>
        )}
        <Link
          href="/evidence"
          className="ml-auto shrink-0 underline underline-offset-4 decoration-border-strong transition-colors duration-300 hover:text-foreground hover:decoration-foreground"
        >
          See the evidence behind the projection →
        </Link>
      </div>
    </section>
  );
}

/*
 * The link between the two figures. A hairline runs from the hero number down into the projected number.
 * While the projection calculates: three chevrons light in sequence, and a comet with a short tail travels the
 * line in step with the count-up (driven by the same eased progress). When it lands, the arrowhead pops to full ink.
 */
const W = 200, H = 24, CY0 = H / 2, CY1 = H / 2, CX0 = 6, CX1 = W - 16;
const along = (t: number) => ({ x: CX0 + (CX1 - CX0) * t, y: CY0 + (CY1 - CY0) * t });
const ANGLE = (Math.atan2(CY1 - CY0, CX1 - CX0) * 180) / Math.PI;
const CHEVRONS = [0.28, 0.5, 0.72];

function Connector({ progress, calculating, landed, className }: { progress: number; calculating: boolean; landed: boolean; className?: string }) {
  const head = along(Math.max(0, Math.min(1, progress)));
  const tail = along(Math.max(0, progress - 0.22));
  return (
    <div className={className} aria-hidden>
      {/* Stretches to the column width; the line and arrow stay perfectly horizontal. */}
      <svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet" className="block overflow-visible">
        <defs>
          <linearGradient id="hero-comet-tail" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stopColor="var(--foreground)" stopOpacity="0" />
            <stop offset="1" stopColor="var(--foreground)" stopOpacity="0.9" />
          </linearGradient>
        </defs>
        <circle cx={CX0} cy={CY0} r={2.5} fill="var(--foreground)" fillOpacity={0.6} />
        {/* Base line. */}
        <line x1={CX0} y1={CY0} x2={CX1} y2={CY1} stroke="var(--foreground)" strokeOpacity={0.22} strokeWidth={1.25} strokeLinecap="round" />
        {/* Lit portion behind the comet; it fills in as the calculation advances and stays lit once landed. */}
        {(calculating || landed) && (
          <line x1={CX0} y1={CY0} x2={landed ? CX1 : head.x} y2={landed ? CY1 : head.y} stroke="var(--foreground)" strokeOpacity={0.5} strokeWidth={1.25} strokeLinecap="round" />
        )}
        {/* Chevrons. */}
        {CHEVRONS.map((t, i) => {
          const c = along(t);
          return (
            <path
              key={t} d="M-4,-5.5 L2,0 L-4,5.5" fill="none" stroke="var(--foreground)" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round"
              transform={`translate(${c.x} ${c.y}) rotate(${ANGLE})`}
              className={cn(calculating && "animate-chevron")}
              style={calculating ? { ["--rise-delay" as string]: `${i * 160}ms` } : { opacity: landed ? 0.6 : 0.22 }}
            />
          );
        })}
        {/* Comet with tail; appears once the calculation is actually moving. */}
        {calculating && progress > 0 && (
          <>
            <line x1={tail.x} y1={tail.y} x2={head.x} y2={head.y} stroke="url(#hero-comet-tail)" strokeWidth={2.5} strokeLinecap="round" />
            <circle cx={head.x} cy={head.y} r={4} fill="var(--foreground)" stroke="var(--card)" strokeWidth={2} />
          </>
        )}
        {/* Arrowhead into the projected figure. */}
        <polygon
          key={landed ? "landed" : "pending"}
          points={`${CX1 + 1},${CY1 - 6} ${CX1 + 11},${CY1} ${CX1 + 1},${CY1 + 6}`}
          fill="var(--foreground)" className={cn(landed && "animate-land")} style={{ opacity: landed ? 1 : 0.25 }}
        />
      </svg>
    </div>
  );
}

const CAPTION_TONE: Record<StatTone, string> = {
  neutral: "text-muted-foreground",
  over: "text-destructive",
  close: "text-warning",
  under: "text-success",
};

/** Caption under a figure; tone colors the dot and text, never the number. */
function Caption({ tone, className, children }: { tone: StatTone; className?: string; children: ReactNode }) {
  return (
    <div className={cn("flex items-center gap-1.5 text-xs leading-snug", CAPTION_TONE[tone], className)}>
      {tone !== "neutral" && <span className="size-1.5 shrink-0 rounded-full bg-current" aria-hidden />}
      <span className="min-w-0">{children}</span>
    </div>
  );
}

/** Lays the final figure out invisibly under the counting one so the tile never shifts while digits grow. */
function Reserved({ final, children }: { final: string; children: ReactNode }) {
  return (
    <span className="relative inline-block">
      <span className="invisible" aria-hidden>{final}</span>
      <span className="absolute inset-0">{children}</span>
    </span>
  );
}

/**
 * Recorded spend (solid), the projection as a dashed extension, the allotment as a labeled marker.
 * `progress` (0..1) moves the leading edge of the projection from the recorded end to the projected end;
 * a pulsing dot rides that edge while `calculating`. The overrun segment only exists once the edge is past the marker.
 */
function EnvelopeBar({ spent, projected, envelope, progress, calculating }: { spent: number; projected?: number; envelope: number; progress: number; calculating: boolean }) {
  const scaleMax = Math.max(envelope, spent, projected ?? 0);
  const w = (v: number) => `${Math.max(0, Math.min(100, (v / scaleMax) * 100))}%`;
  const projectionEnd = projected !== undefined ? Math.max(projected, spent) : spent;
  const lead = spent + (projectionEnd - spent) * progress;
  const withinEnd = Math.min(lead, envelope);
  const overrun = lead > envelope;
  // The label sits to the right of the marker unless the marker is near the end of the track.
  const labelLeft = envelope / scaleMax < 0.85;
  // Envelope changes (an applied proposal) slide the marker and rescale the segments; the calculation itself is driven per frame, so it must not be smoothed.
  const slide = cn(!calculating && "transition-[left,width] duration-300");

  return (
    <div className="relative mt-5 w-full" role="img" aria-label="Spent and projected against the total allocation">
      <div className="relative h-4 font-mono text-[11px] text-muted-foreground" aria-hidden>
        <span className={cn("absolute top-0 whitespace-nowrap leading-4", labelLeft ? "translate-x-1.5" : "-translate-x-full", slide)} style={{ left: w(envelope) }}>Allotted</span>
      </div>
      <div className="relative h-1.5 w-full overflow-hidden rounded-sm bg-muted">
        {/* Projected extension within the allocation (dashed, light), growing with the calculation. */}
        {projected !== undefined && withinEnd > spent && (
          <div
            className={cn("absolute inset-y-0 border border-dashed border-foreground/50 bg-foreground/15", slide)}
            style={{ left: w(spent), width: `calc(${w(withinEnd)} - ${w(spent)})` }}
          />
        )}
        {/* Overrun past the allocation, calm but unmistakable; appears after the marker passes Allotted. */}
        {overrun && (
          <div
            className={cn("absolute inset-y-0 bg-destructive/60", slide)}
            style={{ left: w(envelope), width: `calc(${w(lead)} - ${w(envelope)})` }}
          />
        )}
        {/* Recorded spend, solid. Keyed on its value so it grows from zero on first paint and replays only when spent changes. */}
        <div key={spent} className="animate-grow-x absolute inset-y-0 left-0 bg-foreground/85" style={{ width: w(spent) }} />
      </div>
      {/* Total-allocation marker. */}
      <div className={cn("absolute top-3 -bottom-1 w-px bg-foreground/70", slide)} style={{ left: w(envelope) }} aria-hidden />
      {/* Leading edge of the calculation. */}
      {calculating && (
        <span className="pointer-events-none absolute top-4 size-2.5 -translate-x-1/2 -translate-y-[2px]" style={{ left: w(lead) }} aria-hidden>
          <span className="animate-pulse-dot block size-full rounded-full bg-foreground ring-2 ring-card" />
        </span>
      )}
    </div>
  );
}

/**
 * "1 team with no projection yet, counted at spend to date: Engineering" / "4 teams … : A, B, C +1 more".
 * Falls back to the count alone when names are not supplied.
 */
export function excludedSentence(count: number, names: string[]): string {
  const noun = count === 1 ? "team" : "teams";
  const shown = names.slice(0, 3);
  const rest = names.length - shown.length;
  const list = shown.length ? `: ${shown.join(", ")}${rest > 0 ? ` +${rest} more` : ""}` : "";
  return `${count} ${noun} with no projection yet, counted at spend to date${list}`;
}

/** "1 team likely over: Research" / "4 teams likely over: A, B, C +1 more". */
export function likelyOverSentence(names: string[]): string {
  const noun = names.length === 1 ? "team" : "teams";
  const shown = names.slice(0, 3);
  const rest = names.length - shown.length;
  return `${names.length} ${noun} likely over: ${shown.join(", ")}${rest > 0 ? ` +${rest} more` : ""}`;
}

export function HeroSkeleton() {
  return (
    <section className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-center gap-3">
        <Skeleton className="h-3 w-28" />
        <Skeleton className="h-3 w-40" />
      </div>
      <div className="mt-5 grid grid-cols-1 items-center gap-x-5 gap-y-5 sm:grid-cols-[minmax(0,auto)_minmax(120px,1fr)_minmax(0,auto)] md:gap-x-6">
        <div className="space-y-2"><Skeleton className="h-3 w-28" /><Skeleton className="h-14 w-56" /><Skeleton className="h-3 w-40" /></div>
        <Skeleton className="hidden h-px w-full sm:block" />
        <div className="space-y-2"><Skeleton className="h-3 w-24" /><Skeleton className="h-8 w-32" /><Skeleton className="h-3 w-28" /></div>
      </div>
      <Skeleton className="mt-9 h-1.5 w-full rounded-sm" />
      <Skeleton className="mt-2 h-3 w-48" />
    </section>
  );
}
