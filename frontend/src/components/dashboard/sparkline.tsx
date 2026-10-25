import type { DailyPoint } from "./derive";

/** Tiny inline-SVG daily trend. Partial days are drawn with a lighter stroke so a dip at the end is not misread. */
export function Sparkline({ points, color, className }: { points: DailyPoint[]; color: string; className?: string }) {
  if (points.length < 2) return <div className={className} aria-hidden />;
  const W = 100, H = 28, PAD = 2;
  const max = Math.max(1, ...points.map((p) => p.amount));
  const x = (i: number) => (i / (points.length - 1)) * W;
  const y = (v: number) => H - PAD - (v / max) * (H - PAD * 2);
  const firstPartial = points.findIndex((p) => p.partial);
  const solidEnd = firstPartial === -1 ? points.length - 1 : Math.max(1, firstPartial);
  const toPath = (from: number, to: number) => points.slice(from, to + 1).map((p, i) => `${i === 0 ? "M" : "L"}${x(from + i).toFixed(1)},${y(p.amount).toFixed(1)}`).join(" ");

  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className={className} aria-hidden>
      <path d={toPath(0, solidEnd)} fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
      {solidEnd < points.length - 1 && (
        <path d={toPath(solidEnd, points.length - 1)} fill="none" stroke={color} strokeOpacity={0.35} strokeWidth={1.5} strokeDasharray="3 3" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
      )}
    </svg>
  );
}
