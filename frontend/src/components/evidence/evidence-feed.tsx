"use client";
import { useMemo, useState } from "react";
import type { Unit } from "@/lib/contracts";
import { cn } from "@/lib/utils";
import { SourceSheet } from "@/components/team/source-sheet";
import { riseAt, rowStep } from "@/components/team/count-up";
import { groupByScope, SCOPE_GROUP_LABEL, type EvidenceRow } from "./derive";
import { EvidenceCard } from "./evidence-card";

interface Props {
  rows: EvidenceRow[];
  unit: Unit;
  /** Mount flag from the page, so cards rise once and never flash during hydration. */
  mounted: boolean;
  /** Where the feed sits in the page's entrance sequence, in ms. */
  enterAt?: number;
  onClearFilters: () => void;
  filtersActive: boolean;
}

/** The evidence grouped by scope. Cards share one SourceSheet so only one document is open at a time. */
export function EvidenceFeed({ rows, unit, mounted, enterAt = 0, onClearFilters, filtersActive }: Props) {
  const [openDoc, setOpenDoc] = useState<string | undefined>();
  const groups = useMemo(() => groupByScope(rows), [rows]);
  const rise = mounted ? "animate-rise" : "opacity-0";
  // Spread the stagger so the whole feed finishes rising within 300ms however long it is.
  const step = rowStep(rows.length, 300, 40);
  let index = 0;

  if (rows.length === 0) {
    return (
      <div className={cn("flex flex-col items-center gap-2 rounded-xl border border-border bg-card px-6 py-16 text-center", rise)} style={riseAt(enterAt)}>
        <div className="eyebrow">{filtersActive ? "No evidence matches these filters" : "No evidence yet"}</div>
        <p className="max-w-sm text-sm text-muted-foreground">
          {filtersActive
            ? "Widen the scope, effect or category, or pick another team."
            : "No plans, documents or messages have been linked to this period."}
        </p>
        {filtersActive && (
          <button type="button" onClick={onClearFilters} className="mt-2 text-sm underline underline-offset-4 decoration-border-strong transition-colors duration-300 hover:decoration-foreground">
            Clear filters
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {groups.map((g) => (
        <section key={g.scope} aria-labelledby={`evidence-${g.scope}`} className="space-y-3">
          <div className={cn("flex items-baseline gap-2", rise)} style={riseAt(enterAt + index * step)}>
            <h2 id={`evidence-${g.scope}`} className="eyebrow">{SCOPE_GROUP_LABEL[g.scope]}</h2>
            <span className="num text-xs text-muted-foreground">{g.rows.length}</span>
          </div>
          <ul className="space-y-3">
            {g.rows.map((row) => {
              const i = index++;
              return (
                <li key={row.item.id} className={rise} style={riseAt(enterAt + i * step)}>
                  <EvidenceCard row={row} unit={unit} onViewSource={setOpenDoc} />
                </li>
              );
            })}
          </ul>
        </section>
      ))}
      <SourceSheet documentId={openDoc} onClose={() => setOpenDoc(undefined)} />
    </div>
  );
}
