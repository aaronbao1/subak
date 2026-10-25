"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { Unit } from "@/lib/contracts";
import { cn } from "@/lib/utils";
import { SourceSheet } from "@/components/team/source-sheet";
import { riseAt, rowStep } from "@/components/team/count-up";
import { groupByScope, rowNet, SCOPE_GROUP_LABEL, type EvidenceRow } from "./derive";
import { EvidenceRowItem } from "./evidence-row";

interface Props {
  rows: EvidenceRow[];
  unit: Unit;
  /** Mount flag from the page, so rows rise once and never flash during hydration. */
  mounted: boolean;
  /** Where the feed sits in the page's entrance sequence, in ms. */
  enterAt?: number;
  onClearFilters: () => void;
}

const hashId = () => (typeof window === "undefined" ? "" : decodeURIComponent(window.location.hash.slice(1)));

/** The evidence as compact rows grouped by scope, in one panel. A `#id` link (macro watch, "replaced by") opens its row. */
export function EvidenceFeed({ rows, unit, mounted, enterAt = 0, onClearFilters }: Props) {
  const [openDoc, setOpenDoc] = useState<string | undefined>();
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set(hashId() ? [hashId()] : []));
  const groups = useMemo(() => groupByScope(rows), [rows]);
  const max = useMemo(() => Math.max(1, ...rows.filter((r) => !r.superseded).map((r) => Math.abs(rowNet(r) ?? 0))), [rows]);

  useEffect(() => {
    const onHash = () => {
      const id = hashId();
      if (id) setExpanded((s) => new Set(s).add(id));
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const toggle = useCallback((id: string) => setExpanded((s) => {
    const next = new Set(s);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    return next;
  }), []);

  const rise = mounted ? "animate-rise" : "opacity-0";
  const step = rowStep(rows.length, 300, 40);
  let index = 0;

  if (rows.length === 0) {
    return (
      <p className={cn("rounded-xl border border-border bg-card px-5 py-4 text-sm text-muted-foreground", rise)} style={riseAt(enterAt)}>
        Nothing matches these filters.{" "}
        <button type="button" onClick={onClearFilters} className="text-foreground/80 underline underline-offset-4 decoration-border-strong transition-colors duration-300 hover:decoration-foreground">
          Clear
        </button>
      </p>
    );
  }

  return (
    <div className="rounded-xl border border-border bg-card">
      {groups.map((g, gi) => (
        <section key={g.scope} aria-labelledby={`evidence-${g.scope}`} className={cn(gi > 0 && "border-t border-border")}>
          <div className={cn("flex items-baseline gap-2 px-4 pt-4 pb-1.5", rise)} style={riseAt(enterAt + index * step)}>
            <h2 id={`evidence-${g.scope}`} className="eyebrow">{SCOPE_GROUP_LABEL[g.scope]}</h2>
            <span className="num text-[11px] text-muted-foreground">{g.rows.length}</span>
          </div>
          <ul className="pb-2">
            {g.rows.map((row) => {
              const i = index++;
              return (
                <li key={row.item.id} className={rise} style={riseAt(enterAt + i * step)}>
                  <EvidenceRowItem
                    row={row} unit={unit} max={max} animate={mounted}
                    open={expanded.has(row.item.id)} onToggle={() => toggle(row.item.id)} onViewSource={setOpenDoc}
                  />
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
