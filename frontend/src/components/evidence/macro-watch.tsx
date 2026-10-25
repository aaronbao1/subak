"use client";
import { ArrowDownRight, ArrowUpRight, CircleHelp, Minus } from "lucide-react";
import type { ContextItem } from "@/lib/contracts";
import { cn } from "@/lib/utils";
import { fmtDate } from "@/components/team/labels";
import type { EvidenceRow, MacroBuckets } from "./derive";

const EFFECT_ICON = { increase: ArrowUpRight, decrease: ArrowDownRight, neutral: Minus, unknown: CircleHelp } as const;
const EFFECT_TEXT = { increase: "increases spend", decrease: "decreases spend", neutral: "neutral", unknown: "effect unknown" } as const;

/** Company-scope evidence as a compact timeline: date · title · effect. Items are anchors into the feed. */
export function MacroWatch({ buckets, windowDays }: { buckets: MacroBuckets; windowDays: number }) {
  const empty = buckets.soon.length + buckets.later.length + buckets.past.length === 0;
  return (
    <section aria-labelledby="macro-heading" className="rounded-xl border border-border bg-card">
      <header className="flex items-baseline justify-between gap-3 px-5 pt-5 pb-3">
        <div>
          <h2 id="macro-heading" className="text-base font-medium">Macro watch</h2>
          <p className="mt-0.5 text-xs text-muted-foreground">Company-wide changes every team inherits.</p>
        </div>
      </header>

      {empty ? (
        <div className="border-t border-border px-5 py-6">
          <div className="eyebrow">No company-wide changes</div>
          <p className="mt-1.5 text-sm text-muted-foreground">Nothing at company scope is in effect or scheduled in the next {windowDays} days.</p>
        </div>
      ) : (
        <div className="divide-y divide-border border-t border-border">
          <Bucket label={`Next ${windowDays} days`} rows={buckets.soon} emptyText={`Nothing starts in the next ${windowDays} days.`} />
          {buckets.later.length > 0 && <Bucket label="Later" rows={buckets.later} />}
          {buckets.past.length > 0 && <Bucket label="Ended or superseded" rows={buckets.past} muted />}
        </div>
      )}
    </section>
  );
}

function Bucket({ label, rows, emptyText, muted }: { label: string; rows: EvidenceRow[]; emptyText?: string; muted?: boolean }) {
  return (
    <div className="px-5 py-3">
      <div className="eyebrow">{label}</div>
      {rows.length === 0 ? (
        <p className="mt-1.5 text-xs text-muted-foreground">{emptyText}</p>
      ) : (
        <ol className="mt-2 space-y-2">
          {rows.map((r) => <TimelineRow key={r.item.id} item={r.item} superseded={r.superseded} muted={muted} />)}
        </ol>
      )}
    </div>
  );
}

function TimelineRow({ item, superseded, muted }: { item: ContextItem; superseded: boolean; muted?: boolean }) {
  const Icon = EFFECT_ICON[item.expectedEffect];
  return (
    <li className="flex items-start gap-3 text-xs">
      <span className="num w-14 shrink-0 pt-px text-muted-foreground">{item.effectiveFrom ? fmtDate(item.effectiveFrom) : "undated"}</span>
      <span className="relative mt-1.5 size-1.5 shrink-0 rounded-full bg-foreground/60" aria-hidden />
      <a href={`#${item.id}`} className={cn("min-w-0 flex-1 leading-snug underline-offset-4 decoration-border-strong hover:underline", muted || superseded ? "text-muted-foreground" : "text-foreground/90", superseded && "line-through")}>
        {item.title}
      </a>
      <span className={cn("inline-flex shrink-0 items-center gap-1 text-muted-foreground", item.expectedEffect === "increase" && !muted && "text-warning")} title={EFFECT_TEXT[item.expectedEffect]}>
        <Icon aria-hidden className="size-3.5" strokeWidth={1.75} />
        <span className="sr-only">{EFFECT_TEXT[item.expectedEffect]}</span>
      </span>
    </li>
  );
}
