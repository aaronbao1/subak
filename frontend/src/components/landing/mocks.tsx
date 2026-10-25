"use client";
import { useId, type CSSProperties, type ReactNode } from "react";
import { cn } from "@/lib/utils";
import { EASE_CSS, riseDelay, useCountUp, useProgress } from "@/components/shared/motion";
import { useRevealed } from "./reveal";

/*
 * Static, honest product mocks for the landing page. Built in JSX, no store import, demo numbers only.
 * They follow the dashboard's own rules: eyebrow above the number, mono tabular figures, 1px borders,
 * team colors from the fixed --chart-1..8 slots, text never wearing a series color.
 *
 * Motion: each mock starts when its <Reveal> enters the viewport (or on mount in the hero). Numbers count
 * with useCountUp, the allocation bar grows with animate-grow-x, chart lines draw left to right with
 * useProgress. Reduced motion: the hooks return the end state and the global rule zeroes CSS durations.
 */

const TEAMS = [
  { name: "Platform", spend: "$41,800", share: "44.0%", source: "Reported", color: "var(--chart-1)" },
  { name: "Research", spend: "$28,500", share: "30.0%", source: "Reported", color: "var(--chart-2)" },
  { name: "Support", spend: "$15,200", share: "16.0%", source: "Estimate", color: "var(--chart-3)" },
  { name: "Growth", spend: "$9,500", share: "10.0%", source: "Usage only", color: "var(--chart-4)" },
] as const;

/* Cumulative spend per team, 9 points on a 640x180 plane (y grows downward). */
const SERIES: ReadonlyArray<{ color: string; points: readonly number[] }> = [
  { color: "var(--chart-1)", points: [170, 158, 150, 136, 124, 110, 96, 80, 62] },
  { color: "var(--chart-2)", points: [172, 166, 160, 152, 146, 136, 128, 118, 106] },
  { color: "var(--chart-3)", points: [174, 170, 166, 160, 156, 150, 142, 138, 130] },
  { color: "var(--chart-4)", points: [176, 174, 172, 168, 166, 162, 158, 154, 148] },
];

const PLANE_W = 640;
const PLANE_H = 180;

/* Demo figures: $95,000 spent of a $200,000 allotment, projected to land exactly on it. */
const SPENT = 95_000;
const PROJECTED = 200_000;
const RECORDED_PCT = (SPENT / PROJECTED) * 100; // 47.5

/* Hero timeline offsets, relative to the mock's `delay`. */
const PROJECTION_DELAY_MS = 500;
const DRAW_DELAY_MS = 600;
const DRAW_DURATION_MS = 1100;
const DRAW_STAGGER_MS = 60;
const ROW_STAGGER_MS = 40;

const money = (v: number) => `$${Math.round(v).toLocaleString("en-US")}`;
const delayMs = (ms: number): CSSProperties => ({ ["--rise-delay" as string]: `${ms}ms` });

function toPolyline(points: readonly number[]) {
  const step = PLANE_W / (points.length - 1);
  return points.map((y, i) => `${Math.round(i * step)},${y}`).join(" ");
}

function Swatch({ color, className }: { color: string; className?: string }) {
  return <span aria-hidden className={cn("inline-block size-2 shrink-0 rounded-[2px]", className)} style={{ background: color }} />;
}

/**
 * One chart series: the polyline draws left to right behind a clip that widens with eased progress, and the
 * end marker (an HTML dot, so it stays round under preserveAspectRatio="none") pops once the line has passed.
 * A clip is used instead of stroke-dasharray because `vectorEffect="non-scaling-stroke"` on a non-uniformly
 * scaled SVG makes dash units browser-dependent; the clip is exact everywhere.
 */
function LineLayer({
  series,
  index,
  delay,
  enabled,
  clipId,
}: {
  series: (typeof SERIES)[number];
  index: number;
  delay: number;
  enabled: boolean;
  clipId: string;
}) {
  const p = useProgress({ duration: DRAW_DURATION_MS, delay: delay + DRAW_DELAY_MS + index * DRAW_STAGGER_MS, enabled });
  const endY = (series.points[series.points.length - 1] / PLANE_H) * 100;
  const popped = enabled && p >= 0.98;
  return (
    <div className="absolute inset-0">
      <svg className="size-full" viewBox={`0 0 ${PLANE_W} ${PLANE_H}`} preserveAspectRatio="none">
        <defs>
          <clipPath id={clipId}>
            <rect x="0" y="0" width={Math.max(0, PLANE_W * p)} height={PLANE_H} />
          </clipPath>
        </defs>
        <polyline
          clipPath={`url(#${clipId})`}
          points={toPolyline(series.points)}
          fill="none"
          stroke={series.color}
          strokeWidth="2"
          strokeLinejoin="round"
          strokeLinecap="round"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
      <span
        className="absolute size-2 rounded-full ring-2 ring-card"
        style={{
          left: "100%",
          top: `${endY}%`,
          background: series.color,
          transform: `translate(-50%, -50%) scale(${popped ? 1 : 0})`,
          transition: `transform 300ms ${EASE_CSS}`,
        }}
      />
    </div>
  );
}

/**
 * The overview hero: total spend to date, projected and allotted on one line, a thin allocation bar, and a 4-line chart.
 * `delay` (ms) shifts the whole sequence, e.g. to match the frame's own rise in the hero.
 */
export function HeroMock({ compact = false, delay = 0 }: { compact?: boolean; delay?: number }) {
  const revealed = useRevealed();
  const spent = useCountUp(revealed ? SPENT : 0, { delay });
  /* The projection reads as derived from the current: it starts at the spent figure and counts on from there. */
  const projected = useCountUp(revealed ? PROJECTED : SPENT, { from: SPENT, delay: delay + PROJECTION_DELAY_MS });
  const uid = useId().replace(/[^a-zA-Z0-9_-]/g, "");

  return (
    <div className={cn("flex h-full flex-col", compact ? "p-5 md:p-6" : "p-6 md:p-8")}>
      <p className="eyebrow">Total spend to date</p>
      <p className={cn("num mt-2 leading-none text-foreground", compact ? "text-[32px]" : "text-[32px] md:text-[40px]")}>
        {money(spent)}
      </p>
      <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted-foreground md:text-[13px]">
        <span>
          Projected <span className="num text-foreground/80">{money(projected)}</span>
        </span>
        <span>
          Allotted <span className="num text-foreground/80">{money(PROJECTED)}</span>
        </span>
        <span>USD</span>
      </div>
      <div className="relative mt-4 h-1 w-full overflow-hidden rounded-sm bg-popover" aria-hidden>
        {/* Recorded segment grows first; the dashed projected segment extends from its end once the projection starts counting. */}
        <div
          className={cn("absolute inset-y-0 left-0 rounded-sm bg-foreground/60", revealed && "animate-grow-x")}
          style={{ width: `${RECORDED_PCT}%`, ...delayMs(delay), transform: revealed ? undefined : "scaleX(0)" }}
        />
        <div
          className={cn("absolute inset-y-0 right-0 text-foreground/30", revealed && "animate-grow-x")}
          style={{
            left: `${RECORDED_PCT}%`,
            backgroundImage: "repeating-linear-gradient(90deg, currentColor 0 3px, transparent 3px 6px)",
            ...delayMs(delay + PROJECTION_DELAY_MS),
            transform: revealed ? undefined : "scaleX(0)",
          }}
        />
      </div>

      <div className={cn("flex flex-wrap items-center gap-x-4 gap-y-1", compact ? "mt-5" : "mt-6 md:mt-8")}>
        {TEAMS.map((t) => (
          <span key={t.name} className="inline-flex items-center gap-2 text-xs text-muted-foreground">
            <Swatch color={t.color} />
            {t.name}
          </span>
        ))}
      </div>

      <div className="mt-3 flex min-h-0 flex-1 gap-3">
        <div className="eyebrow flex w-9 shrink-0 flex-col justify-between py-px text-right normal-case tracking-normal">
          <span>$60k</span>
          <span>$40k</span>
          <span>$20k</span>
          <span>$0</span>
        </div>
        <div className={cn("relative w-full", compact ? "h-[120px]" : "h-[140px] md:h-[180px]")} aria-hidden>
          <svg className="absolute inset-0 size-full" viewBox={`0 0 ${PLANE_W} ${PLANE_H}`} preserveAspectRatio="none">
            {[4, 61, 118, 176].map((y) => (
              <line key={y} x1="0" x2={PLANE_W} y1={y} y2={y} stroke="var(--border)" strokeWidth="1" vectorEffect="non-scaling-stroke" />
            ))}
          </svg>
          {SERIES.map((s, i) => (
            <LineLayer key={s.color} series={s} index={i} delay={delay} enabled={revealed} clipId={`${uid}-line-${i}`} />
          ))}
        </div>
      </div>
    </div>
  );
}

/** Team breakdown: one row per team with spend, share of the company total, and where the amount came from. */
export function TeamListMock() {
  const revealed = useRevealed();
  const row = revealed ? "animate-rise" : "opacity-0";
  return (
    <div className="flex h-full flex-col p-5 md:p-6">
      <div className="flex items-baseline justify-between">
        <p className="text-base font-medium">Spend by team</p>
        <p className="eyebrow">USD · to date</p>
      </div>
      <div className="mt-4 overflow-hidden rounded-lg border border-border">
        <div className="eyebrow grid h-9 grid-cols-[1fr_auto_auto_auto] items-center gap-x-6 border-b border-border-strong bg-card px-3">
          <span>Team</span>
          <span className="text-right">Spent</span>
          <span className="text-right">Share</span>
          <span className="hidden text-right sm:block">Source</span>
        </div>
        <ul className="divide-y divide-border">
          {TEAMS.map((t, i) => (
            <li
              key={t.name}
              className={cn("grid h-11 grid-cols-[1fr_auto_auto_auto] items-center gap-x-6 px-3 text-sm", row)}
              style={riseDelay(i, ROW_STAGGER_MS)}
            >
              <span className="flex items-center gap-2.5 text-foreground">
                <Swatch color={t.color} />
                {t.name}
              </span>
              <span className="num text-right text-foreground">{t.spend}</span>
              <span className="num text-right text-muted-foreground">{t.share}</span>
              <span className="hidden text-right text-xs text-muted-foreground sm:block">{t.source}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

const RECEIPT_ROWS: ReadonlyArray<{ term: string; value: ReactNode; num?: boolean }> = [
  {
    term: "From",
    num: true,
    value: (
      <>
        Growth <span className="text-muted-foreground">−$12,000</span>
      </>
    ),
  },
  {
    term: "To",
    num: true,
    value: (
      <>
        Research <span className="text-muted-foreground">+$12,000</span>
      </>
    ),
  },
  {
    term: "Total",
    num: true,
    value: (
      <>
        $200,000 <span className="text-muted-foreground">unchanged</span>
      </>
    ),
  },
  { term: "Why", value: "Research projected past its allotment" },
  {
    term: "Reviewed",
    num: true,
    value: (
      <>
        Projection $200,000 <span className="text-muted-foreground">at review</span>
      </>
    ),
  },
  { term: "Who", value: "Erin Walsh, FP&A" },
];

/** A decision receipt: the kind of proposal, what moved, the projection reviewed, and who applied it. */
export function ReceiptMock() {
  const revealed = useRevealed();
  const row = revealed ? "animate-rise" : "opacity-0";
  return (
    <div className="flex h-full flex-col justify-center p-5 md:p-8">
      <div className="mx-auto w-full max-w-[440px] overflow-hidden rounded-lg border border-border">
        <div className={cn("flex items-center justify-between gap-3 border-b border-border px-4 py-3", row)} style={riseDelay(0, ROW_STAGGER_MS)}>
          <span className="inline-flex h-6 items-center rounded-md border border-border bg-popover px-2 text-xs font-medium text-foreground/80">
            Redistribute
          </span>
          <span className="inline-flex items-center gap-2 text-xs text-muted-foreground">
            <span aria-hidden className="size-1.5 rounded-full bg-success" />
            Applied
          </span>
        </div>
        <dl className="divide-y divide-border text-sm">
          {RECEIPT_ROWS.map((r, i) => (
            <div key={r.term} className={cn("grid grid-cols-[88px_1fr] gap-4 px-4 py-3", row)} style={riseDelay(i + 1, ROW_STAGGER_MS)}>
              <dt className="text-muted-foreground">{r.term}</dt>
              <dd className={cn("text-right text-foreground", r.num && "num")}>{r.value}</dd>
            </div>
          ))}
        </dl>
      </div>
    </div>
  );
}
