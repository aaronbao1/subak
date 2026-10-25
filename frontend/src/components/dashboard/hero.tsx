import type { Unit } from "@/lib/contracts";
import { Skeleton } from "@/components/ui/skeleton";
import { formatAmount, formatPct, pct } from "@/lib/format";
import { cn } from "@/lib/utils";
import { dateLabel, type TeamSummary } from "./derive";
import { teamStatus } from "./status";

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
  hasPlaceholder: boolean;
  isDemo: boolean;
  /** Per-team summaries, so the hero can name the teams whose projection exceeds their allocation. */
  summaries?: TeamSummary[];
}

/**
 * One panel that answers "is the company on track this period?".
 * Total spend is the single hero figure; projected and allotted sit beside it as smaller figures.
 * Spent is drawn solid, the projection as a dashed extension, the total allocation as the reference.
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
  const partialCoverage = hasProjection && p.projectedTeamCount < p.teamCount;
  // Spent: red once it passes the allocation, amber within 10% of it. Projected: red over, green within.
  const spentTone: Tone = envelope === undefined ? "neutral" : p.spent > envelope ? "over" : p.spent >= envelope * 0.9 ? "close" : "neutral";
  const projectedTone: Tone = envelope === undefined || projected === undefined ? "neutral" : projected > envelope ? "over" : "under";
  const excludedNote = partialCoverage ? excludedSentence(p.unavailableCount, p.unavailableTeams ?? []) : undefined;
  const likelyOver = (p.summaries ?? []).filter((s) => teamStatus(s.budget?.allocated, s.projected, s.high) === "likely_over").map((s) => s.team.name);

  return (
    <section aria-label="Company spend summary" className="min-w-0 rounded-xl border border-border bg-card p-5">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <span className="eyebrow">Company spend</span>
        <span className="truncate text-xs text-muted-foreground" title={p.periodRange}>
          {p.periodLabel ?? "Period not set"}
          {p.periodRange && <span className="num hidden sm:inline"> · {p.periodRange}</span>}
        </span>
        <span className="num text-xs text-muted-foreground" title={p.asOf}>{p.asOf ? `as of ${dateLabel(p.asOf)}` : "no complete day yet"}</span>
        {(p.isDemo || p.hasPlaceholder) && (
          <span className="ml-auto flex items-center gap-1.5">
            {p.isDemo && <Tag>demo data</Tag>}
            {p.hasPlaceholder && <Tag>placeholder projections</Tag>}
          </span>
        )}
      </div>

      {/* One big number (total spend), then projected as a secondary figure, then the allotment as a sub-number. */}
      <dl className="mt-5 grid grid-cols-2 items-end gap-x-6 gap-y-5 sm:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)_minmax(0,1fr)] md:gap-x-10">
        <Figure
          size="primary" label="Total spend to date" value={formatAmount(p.spent, p.unit)}
          className="col-span-2 sm:col-span-1"
          delta={hasEnvelope
            ? { tone: spentTone, text: `${formatPct(pct(p.spent, envelope as number))} of allotment recorded` }
            : { tone: "neutral", text: "Add budgets to compare against an allotment" }}
        />
        <Figure
          size="secondary"
          label="Projected for period"
          value={hasProjection ? formatAmount(projected as number, p.unit) : "No projection"}
          muted={!hasProjection}
          delta={over !== undefined
            ? isOver
              ? { tone: projectedTone, text: `+${formatAmount(over, p.unit)} over allotment` }
              : { tone: projectedTone, text: `${formatPct(pct(projected as number, envelope as number))} of allotment` }
            : undefined}
          note={excludedNote}
        />
        <Figure
          size="tertiary"
          label="Allotted"
          value={hasEnvelope ? formatAmount(envelope as number, p.unit) : "No budgets yet"}
          muted={!hasEnvelope}
        />
      </dl>

      {hasEnvelope && (
        <EnvelopeBar spent={p.spent} projected={projected} envelope={envelope as number} />
      )}

      {(likelyOver.length > 0 || (p.unavailableCount > 0 && !partialCoverage)) && (
        <p className="mt-2 text-xs text-muted-foreground">
          {likelyOver.length > 0 && (
            <span className="inline-flex items-center gap-1.5">
              <span className="size-1.5 shrink-0 rounded-full bg-destructive" aria-hidden />
              {likelyOverSentence(likelyOver)}
            </span>
          )}
          {likelyOver.length > 0 && p.unavailableCount > 0 && !partialCoverage && " · "}
          {p.unavailableCount > 0 && !partialCoverage && excludedSentence(p.unavailableCount, p.unavailableTeams ?? [])}
        </p>
      )}
    </section>
  );
}

function EnvelopeBar({ spent, projected, envelope }: { spent: number; projected?: number; envelope: number }) {
  const scaleMax = Math.max(envelope, spent, projected ?? 0);
  const w = (v: number) => `${Math.max(0, Math.min(100, (v / scaleMax) * 100))}%`;
  const projectionEnd = projected !== undefined ? Math.max(projected, spent) : spent;
  const withinEnd = Math.min(projectionEnd, envelope);
  const overrun = projectionEnd > envelope;
  const envelopeAtEnd = envelope >= scaleMax;

  return (
    <div className="relative mt-5 w-full" role="img" aria-label="Spent and projected against the total allocation">
      <div className="relative h-1.5 w-full overflow-hidden rounded-sm bg-muted">
        {/* Projected extension within the allocation (dashed, light). */}
        {projected !== undefined && withinEnd > spent && (
          <div
            className="absolute inset-y-0 border border-dashed border-foreground/50 bg-foreground/15"
            style={{ left: w(spent), width: `calc(${w(withinEnd)} - ${w(spent)})` }}
          />
        )}
        {/* Overrun past the allocation, calm but unmistakable. */}
        {overrun && (
          <div
            className="absolute inset-y-0 bg-destructive/60"
            style={{ left: w(envelope), width: `calc(${w(projectionEnd)} - ${w(envelope)})` }}
          />
        )}
        {/* Recorded spend, solid. */}
        <div className="absolute inset-y-0 left-0 bg-foreground/85" style={{ width: w(spent) }} />
      </div>
      {/* Total-allocation marker; sits at the end of the track unless the scale had to widen. */}
      {!envelopeAtEnd && (
        <div className="absolute -top-1 -bottom-1 w-px bg-foreground/70" style={{ left: w(envelope) }} aria-hidden />
      )}
    </div>
  );
}

/**
 * "Excludes 1 team with no projection yet: Engineering" / "Excludes 4 teams with no projection yet: A, B, C +1 more".
 * Falls back to the count alone when names are not supplied.
 */
export function excludedSentence(count: number, names: string[]): string {
  const noun = count === 1 ? "team" : "teams";
  const shown = names.slice(0, 3);
  const rest = names.length - shown.length;
  const list = shown.length ? `: ${shown.join(", ")}${rest > 0 ? ` +${rest} more` : ""}` : "";
  return `Excludes ${count} ${noun} with no projection yet${list}`;
}

/** "1 team likely over: Research" / "4 teams likely over: A, B, C +1 more". */
export function likelyOverSentence(names: string[]): string {
  const noun = names.length === 1 ? "team" : "teams";
  const shown = names.slice(0, 3);
  const rest = names.length - shown.length;
  return `${names.length} ${noun} likely over: ${shown.join(", ")}${rest > 0 ? ` +${rest} more` : ""}`;
}

type Tone = "neutral" | "over" | "close" | "under";
/** Tone lives on a small dot and the delta text only; the figure itself stays in ink. */
const TONE_TEXT: Record<Tone, string> = {
  neutral: "text-muted-foreground",
  over: "text-destructive",
  close: "text-warning",
  under: "text-success",
};
const TONE_DOT: Record<Tone, string> = {
  neutral: "bg-muted-foreground",
  over: "bg-destructive",
  close: "bg-warning",
  under: "bg-success",
};

type Size = "primary" | "secondary" | "tertiary";
const SIZE_CLASS: Record<Size, string> = {
  primary: "text-[48px] md:text-[56px]",
  secondary: "text-[28px]",
  tertiary: "text-[20px]",
};
const MUTED_SIZE_CLASS: Record<Size, string> = {
  primary: "text-[28px]",
  secondary: "text-[20px]",
  tertiary: "text-base",
};

function Figure({ label, value, muted, note, delta, size = "secondary", className }: {
  label: string; value: string; muted?: boolean; note?: string;
  delta?: { tone: Tone; text: string }; size?: Size; className?: string;
}) {
  return (
    <div className={cn("min-w-0", className)}>
      <dt className="eyebrow truncate">{label}</dt>
      <dd className={cn("num mt-2 truncate font-medium leading-none", muted ? cn("text-muted-foreground", MUTED_SIZE_CLASS[size]) : cn("text-foreground", SIZE_CLASS[size]))}>
        {value}
      </dd>
      {delta && (
        <dd className={cn("mt-2 flex items-center gap-1.5 text-xs", TONE_TEXT[delta.tone])}>
          <span className={cn("size-1.5 shrink-0 rounded-full", TONE_DOT[delta.tone])} aria-hidden />
          <span className="num truncate">{delta.text}</span>
        </dd>
      )}
      {note && <dd className="mt-1 text-xs leading-snug text-muted-foreground">{note}</dd>}
    </div>
  );
}

function Tag({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex h-6 items-center rounded-md border border-border bg-popover px-2 text-xs text-muted-foreground">{children}</span>
  );
}

export function HeroSkeleton() {
  return (
    <section className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-center gap-3">
        <Skeleton className="h-3 w-28" />
        <Skeleton className="h-3 w-40" />
      </div>
      <div className="mt-5 grid grid-cols-2 items-end gap-x-6 gap-y-5 sm:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)_minmax(0,1fr)] md:gap-x-10">
        <div className="col-span-2 space-y-2 sm:col-span-1"><Skeleton className="h-3 w-28" /><Skeleton className="h-14 w-56" /><Skeleton className="h-3 w-40" /></div>
        <div className="space-y-2"><Skeleton className="h-3 w-24" /><Skeleton className="h-7 w-32" /><Skeleton className="h-3 w-28" /></div>
        <div className="space-y-2"><Skeleton className="h-3 w-16" /><Skeleton className="h-5 w-24" /></div>
      </div>
      <Skeleton className="mt-5 h-1.5 w-full rounded-sm" />
      <Skeleton className="mt-2 h-3 w-48" />
    </section>
  );
}
