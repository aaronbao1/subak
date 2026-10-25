import { cn } from "@/lib/utils";

/*
 * Static, honest product mocks for the landing page. Built in JSX, no store import, demo numbers only.
 * They follow the dashboard's own rules: eyebrow above the number, mono tabular figures, 1px borders,
 * team colors from the fixed --chart-1..8 slots, text never wearing a series color.
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

function toPolyline(points: readonly number[]) {
  const step = 640 / (points.length - 1);
  return points.map((y, i) => `${Math.round(i * step)},${y}`).join(" ");
}

function Swatch({ color, className }: { color: string; className?: string }) {
  return <span aria-hidden className={cn("inline-block size-2 shrink-0 rounded-[2px]", className)} style={{ background: color }} />;
}

/** The overview hero: total spend to date, projected and allotted on one line, a thin allocation bar, and a 4-line chart. */
export function HeroMock({ compact = false }: { compact?: boolean }) {
  return (
    <div className={cn("flex h-full flex-col", compact ? "p-5 md:p-6" : "p-6 md:p-8")}>
      <p className="eyebrow">Total spend to date</p>
      <p className={cn("num mt-2 leading-none text-foreground", compact ? "text-[32px]" : "text-[32px] md:text-[40px]")}>
        $95,000
      </p>
      <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted-foreground md:text-[13px]">
        <span>
          Projected <span className="num text-foreground/80">$200,000</span>
        </span>
        <span>
          Allotted <span className="num text-foreground/80">$200,000</span>
        </span>
        <span>USD</span>
      </div>
      <div className="mt-4 h-1 w-full overflow-hidden rounded-sm bg-popover" aria-hidden>
        <div className="h-full w-[47.5%] rounded-sm bg-foreground/60" />
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
        <svg
          className={cn("w-full", compact ? "h-[120px]" : "h-[140px] md:h-[180px]")}
          viewBox="0 0 640 180"
          preserveAspectRatio="none"
          aria-hidden
        >
          {[4, 61, 118, 176].map((y) => (
            <line key={y} x1="0" x2="640" y1={y} y2={y} stroke="var(--border)" strokeWidth="1" vectorEffect="non-scaling-stroke" />
          ))}
          {SERIES.map((s) => (
            <polyline
              key={s.color}
              points={toPolyline(s.points)}
              fill="none"
              stroke={s.color}
              strokeWidth="2"
              strokeLinejoin="round"
              strokeLinecap="round"
              vectorEffect="non-scaling-stroke"
            />
          ))}
        </svg>
      </div>
    </div>
  );
}

/** Team breakdown: one row per team with spend, share of the company total, and where the amount came from. */
export function TeamListMock() {
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
          {TEAMS.map((t) => (
            <li key={t.name} className="grid h-11 grid-cols-[1fr_auto_auto_auto] items-center gap-x-6 px-3 text-sm">
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
      <p className="mt-3 text-xs text-muted-foreground">Team figures are the sum of each team&rsquo;s people. One day is incomplete and marked.</p>
    </div>
  );
}

/** A decision receipt: the kind of proposal, what moved, the projection reviewed, and who applied it. */
export function ReceiptMock() {
  return (
    <div className="flex h-full flex-col justify-center p-5 md:p-8">
      <div className="mx-auto w-full max-w-[440px] overflow-hidden rounded-lg border border-border">
        <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
          <span className="inline-flex h-6 items-center rounded-md border border-border bg-popover px-2 text-xs font-medium text-foreground/80">
            Redistribute
          </span>
          <span className="inline-flex items-center gap-2 text-xs text-muted-foreground">
            <span aria-hidden className="size-1.5 rounded-full bg-success" />
            Applied
          </span>
        </div>
        <dl className="divide-y divide-border text-sm">
          <div className="grid grid-cols-[88px_1fr] gap-4 px-4 py-3">
            <dt className="text-muted-foreground">What</dt>
            <dd className="num text-right text-foreground">
              Growth −$12,000 <span className="text-muted-foreground">→</span> Research +$12,000
            </dd>
          </div>
          <div className="grid grid-cols-[88px_1fr] gap-4 px-4 py-3">
            <dt className="text-muted-foreground">Total</dt>
            <dd className="num text-right text-foreground">
              $200,000 <span className="text-muted-foreground">unchanged</span>
            </dd>
          </div>
          <div className="grid grid-cols-[88px_1fr] gap-4 px-4 py-3">
            <dt className="text-muted-foreground">Why</dt>
            <dd className="text-right text-foreground">Research projected past its allotment</dd>
          </div>
          <div className="grid grid-cols-[88px_1fr] gap-4 px-4 py-3">
            <dt className="text-muted-foreground">Reviewed</dt>
            <dd className="num text-right text-foreground">
              Projection $200,000 <span className="text-muted-foreground">at review</span>
            </dd>
          </div>
          <div className="grid grid-cols-[88px_1fr] gap-4 px-4 py-3">
            <dt className="text-muted-foreground">Who</dt>
            <dd className="text-right text-foreground">FP&amp;A, demo user</dd>
          </div>
        </dl>
      </div>
    </div>
  );
}
