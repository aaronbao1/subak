"use client";
import { cn } from "@/lib/utils";
import { fmtDate } from "@/components/team/labels";
import type { EvidenceRow, MacroBuckets } from "./derive";
import { EFFECT_FILL } from "@/components/shared/tone";
import { EFFECT_TEXT } from "./marks";

const DAY_MS = 86_400_000;
const toTs = (iso: string) => { const [y, m, d] = iso.split("-").map(Number); return Date.UTC(y, m - 1, d); };
const LANES = 3;

/**
 * Company-wide changes on one strip: a dot per item at its start date, a hairline for its span, a tick for today.
 * Ended or superseded items are hollow. Dots link into the feed; the exact title and date are in the tooltip.
 */
export function MacroWatch({ buckets, today, windowDays }: { buckets: MacroBuckets; today: string; windowDays: number }) {
  const all = [...buckets.past, ...buckets.soon, ...buckets.later];
  const dated = all.filter((r) => r.item.effectiveFrom || r.item.effectiveTo);
  const undated = all.length - dated.length;

  if (all.length === 0) return null;

  const t0 = toTs(today);
  const stamps = dated.flatMap((r) => [r.item.effectiveFrom, r.item.effectiveTo].filter((d): d is string => !!d).map(toTs));
  const lo = Math.min(t0, ...stamps);
  const hi = Math.max(t0 + windowDays * DAY_MS, ...stamps);
  const x = (t: number) => ((t - lo) / Math.max(1, hi - lo)) * 100;

  const ended = new Set(buckets.past.map((r) => r.item.id));
  const placed = [...dated]
    .sort((a, b) => (a.item.effectiveFrom ?? a.item.effectiveTo ?? "").localeCompare(b.item.effectiveFrom ?? b.item.effectiveTo ?? ""))
    .reduce<{ row: EvidenceRow; from: number; to?: number; lane: number }[]>((acc, row) => {
      const from = x(toTs(row.item.effectiveFrom ?? row.item.effectiveTo!));
      const to = row.item.effectiveFrom && row.item.effectiveTo ? x(toTs(row.item.effectiveTo)) : undefined;
      const lane = [0, 1, 2].find((l) => !acc.some((p) => p.lane === l && Math.abs(p.from - from) < 6)) ?? acc.length % LANES;
      acc.push({ row, from, to, lane });
      return acc;
    }, []);

  const next = buckets.soon.find((r) => r.item.effectiveFrom && toTs(r.item.effectiveFrom) >= t0) ?? buckets.later[0];

  return (
    <section aria-labelledby="macro-heading" className="rounded-xl border border-border bg-card px-5 py-4">
      <div className="flex items-baseline justify-between gap-3">
        <h2 id="macro-heading" className="text-sm font-medium">Macro watch</h2>
        {undated > 0 && <span className="num text-[11px] text-muted-foreground">+{undated} undated</span>}
      </div>

      {dated.length > 0 && (
        <div className="mt-3">
          <div className="relative h-12">
            <span aria-hidden className="absolute inset-x-0 bottom-1 h-px bg-border" />
            <span aria-hidden className="absolute top-0 bottom-0 w-px bg-border-strong" style={{ left: `${x(t0)}%` }} />
            <ol>
              {placed.map(({ row, from, to, lane }) => {
                const hollow = row.superseded || ended.has(row.item.id);
                const bottom = 8 + lane * 13;
                const label = `${row.item.title} · ${fmtDate(row.item.effectiveFrom ?? row.item.effectiveTo)}${row.item.effectiveTo && row.item.effectiveFrom ? ` – ${fmtDate(row.item.effectiveTo)}` : ""} · ${row.superseded ? "superseded" : EFFECT_TEXT[row.item.expectedEffect].toLowerCase()}`;
                return (
                  <li key={row.item.id}>
                    {to !== undefined && (
                      <span aria-hidden className="absolute h-px bg-foreground/25" style={{ left: `${from}%`, width: `${Math.max(0, to - from)}%`, bottom: bottom + 3.5 }} />
                    )}
                    <a
                      href={`#${row.item.id}`}
                      title={label}
                      aria-label={label}
                      className={cn(
                        "absolute size-2 -translate-x-1/2 rounded-full ring-2 ring-card transition-transform duration-150 hover:scale-125 focus-visible:outline-none focus-visible:ring-ring",
                        hollow && "border border-muted-foreground bg-card",
                      )}
                      style={{ left: `${from}%`, bottom, background: hollow ? undefined : EFFECT_FILL[row.item.expectedEffect] }}
                    />
                  </li>
                );
              })}
            </ol>
          </div>
          <div className="num relative mt-1 h-4 text-[11px] text-muted-foreground">
            <span className="absolute left-0">{fmtDate(new Date(lo).toISOString().slice(0, 10))}</span>
            <span className="absolute -translate-x-1/2 text-foreground/80" style={{ left: `${Math.min(85, Math.max(15, x(t0)))}%` }}>Today</span>
            <span className="absolute right-0">{fmtDate(new Date(hi).toISOString().slice(0, 10))}</span>
          </div>
        </div>
      )}

      {next && (
        <a href={`#${next.item.id}`} className="mt-3 flex items-baseline gap-2 text-xs underline-offset-4 decoration-border-strong hover:underline">
          <span className="num shrink-0 text-muted-foreground">{fmtDate(next.item.effectiveFrom)}</span>
          <span className="truncate text-foreground/80">{next.item.title}</span>
        </a>
      )}
    </section>
  );
}
