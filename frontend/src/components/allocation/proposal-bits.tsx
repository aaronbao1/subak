"use client";
import { useState, type ReactNode } from "react";
import { Lock } from "lucide-react";
import type { AllocationLine, AllocationProposal, Decision, ProposalKind, Team, Unit } from "@/lib/contracts";
import { Badge } from "@/components/ui/badge";
import { formatAmount, unitLabel } from "@/lib/format";
import { cn } from "@/lib/utils";

/* Shared pieces for proposals and receipts: kind, status, total bar, per-team paired bars, exact table. */

export function kindLabel(p: Pick<AllocationProposal, "kind" | "addedAmount" | "unit">) {
  return p.kind === "add_budget"
    ? `Adds ${formatAmount(p.addedAmount ?? 0, p.unit)} to the total allocation`
    : "Redistributes the existing allocation";
}

export function kindShort(kind: AllocationProposal["kind"]) {
  return kind === "add_budget" ? "Add budget" : "Redistribute";
}

export function kindExplanation(kind: AllocationProposal["kind"]) {
  return kind === "redistribute"
    ? "Total allocation stays the same; money moves between teams."
    : "New funding; no team loses allocation.";
}

export const STATUS_LABEL: Record<AllocationProposal["status"], string> = {
  proposed: "Awaiting review",
  pending: "Applying…",
  applied: "Applied",
  rejected: "Rejected",
  revised: "Revised",
  stale: "Stale",
  failed: "Failed",
};

/** Every state looks different: neutral for open, success / warning / destructive for applied / stale / failed, muted for closed. */
const STATUS_VARIANT: Record<AllocationProposal["status"], "default" | "outline" | "success" | "warning" | "destructive"> = {
  proposed: "default",
  pending: "default",
  applied: "success",
  rejected: "outline",
  revised: "outline",
  stale: "warning",
  failed: "destructive",
};

export function ProposalStatusBadge({ status, className }: { status: AllocationProposal["status"]; className?: string }) {
  return (
    <Badge
      variant={STATUS_VARIANT[status]}
      className={cn(
        "gap-1.5",
        status === "pending" && "border-dashed text-muted-foreground",
        status === "rejected" && "text-muted-foreground",
        status === "revised" && "border-dashed text-muted-foreground line-through decoration-muted-foreground",
        className,
      )}
    >
      {status === "pending" && <span aria-hidden className="size-1.5 animate-pulse rounded-full bg-current" />}
      {(status === "applied" || status === "stale" || status === "failed") && <span aria-hidden className="size-1.5 rounded-full bg-current" />}
      {STATUS_LABEL[status]}
    </Badge>
  );
}

/** "Add budget" / "Redistribute" as a quiet mono label. The distinction is a product rule, so it is always present. */
export function KindLabel({ kind, className }: { kind: AllocationProposal["kind"]; className?: string }) {
  return (
    <span className={cn("eyebrow", className)} title={kindExplanation(kind)}>
      {kindShort(kind)}
    </span>
  );
}

export function signed(n: number, unit: Unit, opts: { compact?: boolean } = {}) {
  if (n === 0) return "no change";
  return `${n > 0 ? "+" : "−"}${formatAmount(Math.abs(n), unit, opts)}`;
}

export type DeltaTone = "success" | "warning" | "destructive" | "muted";

const DELTA_TEXT: Record<DeltaTone, string> = { success: "text-success", warning: "text-warning", destructive: "text-destructive", muted: "text-muted-foreground" };
const DELTA_BG: Record<DeltaTone, string> = { success: "bg-success/10", warning: "bg-warning/10", destructive: "bg-destructive/10", muted: "bg-muted" };

// Allocation deltas: up = success (more budget), down = warning (less budget), zero = muted; red is only for over-allotment.
export function deltaTone(n: number): DeltaTone {
  return n > 0 ? "success" : n < 0 ? "warning" : "muted";
}

export function deltaClass(n: number) {
  return DELTA_TEXT[deltaTone(n)];
}

/**
 * Delta chip: ▲ $5k in status color. Exact signed value in the tooltip. `tone` overrides the allocation rule so other
 * lanes can reuse the shape (e.g. spend deltas, where shared/tone says increase = warning). `kind` is accepted for
 * compatibility and no longer changes the color.
 */
export function DeltaChip({ n, unit, tone, className }: { n: number; unit: Unit; kind?: ProposalKind; tone?: DeltaTone; className?: string }) {
  if (n === 0) {
    return <span className={cn("num inline-flex h-5 items-center px-1.5 text-[11px] text-muted-foreground", className)} aria-label="no change">–</span>;
  }
  const t = tone ?? deltaTone(n);
  return (
    <span
      title={signed(n, unit)}
      className={cn("num inline-flex h-5 items-center gap-0.5 rounded-sm px-1.5 text-[11px] whitespace-nowrap", DELTA_TEXT[t], DELTA_BG[t], className)}
    >
      <span aria-hidden className="text-[9px]">{n > 0 ? "▲" : "▼"}</span>
      <span className="sr-only">{n > 0 ? "up" : "down"} </span>
      {formatAmount(Math.abs(n), unit, { compact: true })}
    </span>
  );
}

export function teamName(teams: Team[], id: string) {
  return teams.find((t) => t.id === id)?.name ?? id;
}

export function teamColor(teams: Team[], id: string) {
  return teams.find((t) => t.id === id)?.color ?? "var(--muted-foreground)";
}

/**
 * Total allocation. Add budget: one bar, the added segment highlighted. Redistribute: a lock and "total unchanged".
 */
export function TotalBar({ before, after, unit, kind, className }: { before: number; after: number; unit: Unit; kind: ProposalKind; className?: string }) {
  if (kind === "redistribute") {
    return (
      <div className={cn("flex items-center justify-between gap-3", className)}>
        <span className="eyebrow">Total</span>
        <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Lock className="size-3.5" aria-hidden strokeWidth={1.5} />
          <span className="num text-sm text-foreground">{formatAmount(after, unit)}</span>
          total unchanged
        </span>
      </div>
    );
  }
  const scale = Math.max(before, after, 1);
  const added = Math.max(0, after - before);
  return (
    <div className={cn("space-y-1.5", className)}>
      <div className="flex items-center justify-between gap-3">
        <span className="eyebrow">Total</span>
        <span className="num flex items-center gap-1.5 text-sm">
          <span className="text-muted-foreground">{formatAmount(before, unit, { compact: true })}</span>
          <span aria-hidden className="text-muted-foreground">→</span>
          <span>{formatAmount(after, unit, { compact: true })}</span>
          <DeltaChip n={after - before} unit={unit} kind={kind} />
        </span>
      </div>
      <div className="flex h-1.5 w-full gap-[2px]" role="img" aria-label={`Total ${formatAmount(before, unit)} to ${formatAmount(after, unit)}`}>
        <span className="h-full bg-muted-foreground/40" style={{ width: `${(Math.min(before, after) / scale) * 100}%` }} />
        {added > 0 && <span className="animate-grow-x h-full origin-left rounded-r-sm bg-success" style={{ width: `${(added / scale) * 100}%` }} />}
      </div>
    </div>
  );
}

/** Tiny total bar for log rows: 64px, added part in success; redistribute shows a lock. */
export function MiniTotal({ before, after, unit, kind, applied }: { before: number; after: number; unit: Unit; kind: ProposalKind; applied: boolean }) {
  const added = applied ? Math.max(0, after - before) : 0;
  const scale = Math.max(before, after, 1);
  return (
    <span className="flex items-center gap-2" title={`${formatAmount(before, unit)} → ${formatAmount(applied ? after : before, unit)}`}>
      {kind === "redistribute" || !applied ? (
        <Lock className="size-3.5 text-muted-foreground" aria-label="total unchanged" strokeWidth={1.5} />
      ) : null}
      <span aria-hidden className="flex h-1 w-16 gap-[2px]">
        <span className="h-full bg-muted-foreground/40" style={{ width: `${(Math.min(before, after) / scale) * 100}%` }} />
        {added > 0 && <span className="h-full rounded-r-sm bg-success" style={{ width: `${(added / scale) * 100}%` }} />}
      </span>
      <span className="num text-xs text-foreground">{formatAmount(applied ? after : before, unit, { compact: true })}</span>
    </span>
  );
}

/** Changed lines first (largest move first), then unchanged by size. */
function orderLines(lines: AllocationLine[]) {
  return [...lines].sort((a, b) => {
    const da = Math.abs(a.after - a.before), db = Math.abs(b.after - b.before);
    if ((da === 0) !== (db === 0)) return da === 0 ? 1 : -1;
    return db - da || b.after - a.after;
  });
}

/**
 * Per-team paired bars: before as a ghost bar, after as a solid bar in the team color, delta chip at the end.
 * An optional tick marks a reviewed projection (red when it runs past the new allocation).
 */
export function PairedBars({ lines, unit, teams, kind, limit, projection, className }: {
  lines: AllocationLine[];
  unit: Unit;
  teams: Team[];
  kind?: ProposalKind;
  limit?: number;
  projection?: (teamId: string) => number | undefined;
  className?: string;
}) {
  const ordered = orderLines(lines);
  const shown = limit ? ordered.slice(0, limit) : ordered;
  const hidden = ordered.length - shown.length;
  const scale = Math.max(1, ...lines.flatMap((l) => [l.before, l.after, projection?.(l.teamId) ?? 0]));
  const hasTick = !!projection && lines.some((l) => projection(l.teamId) !== undefined);
  const w = (n: number) => `${Math.max(0, (n / scale) * 100)}%`;

  return (
    <div className={cn("space-y-2", className)}>
      <ul className="space-y-2.5">
        {shown.map((l, i) => {
          const d = l.after - l.before;
          const proj = projection?.(l.teamId);
          return (
            <li key={l.teamId} className="grid grid-cols-[minmax(0,6.5rem)_1fr_auto] items-center gap-3 text-sm">
              <span className={cn("flex min-w-0 items-center gap-2", d === 0 && "text-muted-foreground")}>
                <span aria-hidden className="size-1.5 shrink-0 rounded-full" style={{ background: teamColor(teams, l.teamId) }} />
                <span className="truncate">{teamName(teams, l.teamId)}</span>
              </span>
              <span
                className="relative flex flex-col gap-[2px]"
                role="img"
                aria-label={`${teamName(teams, l.teamId)}: ${formatAmount(l.before, unit)} to ${formatAmount(l.after, unit)}`}
                title={`${formatAmount(l.before, unit)} → ${formatAmount(l.after, unit)}${proj !== undefined ? ` · projection ${formatAmount(proj, unit)}` : ""}`}
              >
                <span className="h-[3px] rounded-r-sm bg-muted-foreground/30" style={{ width: w(l.before) }} />
                <span
                  className={cn("animate-grow-x h-1.5 origin-left rounded-r-sm", d === 0 && "opacity-50")}
                  style={{ width: w(l.after), background: teamColor(teams, l.teamId), animationDelay: `${i * 60}ms` }}
                />
                {proj !== undefined && (
                  <span
                    aria-hidden
                    className={cn("absolute -top-0.5 h-3 w-[2px] -translate-x-1/2 rounded-full", proj > l.after ? "bg-destructive" : "bg-foreground/70")}
                    style={{ left: w(proj) }}
                  />
                )}
              </span>
              <span className="flex items-center justify-end gap-1.5">
                <span className={cn("num text-xs", d === 0 ? "text-muted-foreground" : "text-foreground")}>{formatAmount(l.after, unit, { compact: true })}</span>
                <DeltaChip n={d} unit={unit} kind={kind} className="min-w-[3.25rem] justify-center" />
              </span>
            </li>
          );
        })}
      </ul>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
        <span className="inline-flex items-center gap-1.5"><span aria-hidden className="h-[3px] w-2 bg-muted-foreground/30" />Before</span>
        <span className="inline-flex items-center gap-1.5"><span aria-hidden className="size-2 rounded-[1px] bg-muted-foreground" />After</span>
        {hasTick && <span className="inline-flex items-center gap-1.5"><span aria-hidden className="h-2.5 w-[2px] bg-foreground/70" />Projection reviewed</span>}
        {hidden > 0 && <span className="ml-auto num">+{hidden} unchanged</span>}
      </div>
    </div>
  );
}

export interface ExtraColumn {
  header: ReactNode;
  cell: (l: AllocationLine) => ReactNode;
}

/** Exact before / after / change per team. Lives behind "Show table". */
export function AllocationTable({ lines, unit, teams, extra = [] }: { lines: AllocationLine[]; unit: Unit; teams: Team[]; kind?: ProposalKind; extra?: ExtraColumn[] }) {
  const th = "eyebrow h-9 px-3 text-right align-middle whitespace-nowrap";
  const td = "num px-3 text-right align-middle";
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-border-strong">
            <th scope="col" className={cn(th, "text-left")}>Team <span className="normal-case tracking-normal">({unitLabel(unit)})</span></th>
            <th scope="col" className={th}>Before</th>
            <th scope="col" className={th}>After</th>
            <th scope="col" className={th}>Change</th>
            {extra.map((c, i) => <th key={i} scope="col" className={th}>{c.header}</th>)}
          </tr>
        </thead>
        <tbody>
          {lines.map((l) => {
            const d = l.after - l.before;
            return (
              <tr key={l.teamId} className={cn("h-9 border-b border-border last:border-0", d === 0 && "text-muted-foreground")}>
                <td className="px-3 align-middle">{teamName(teams, l.teamId)}</td>
                <td className={cn(td, "text-muted-foreground")}>{formatAmount(l.before, unit)}</td>
                <td className={td}>{formatAmount(l.after, unit)}</td>
                <td className={cn(td, deltaClass(d))}>{signed(d, unit)}</td>
                {extra.map((c, i) => <td key={i} className={td}>{c.cell(l)}</td>)}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/** Quiet text toggle that reveals detail below it. */
export function Reveal({ show, hide, children, aside, className }: { show: string; hide: string; children: ReactNode; aside?: ReactNode; className?: string }) {
  const [open, setOpen] = useState(false);
  const toggle = (
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="rounded-sm text-xs text-muted-foreground transition-colors duration-300 outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
      >
        {open ? hide : show}
      </button>
  );
  return (
    <div className={className}>
      {aside ? <div className="flex items-center justify-between gap-3">{toggle}{aside}</div> : toggle}
      {open && <div className="mt-2">{children}</div>}
    </div>
  );
}

export function decisionTotals(d: Decision) {
  const before = d.lines.reduce((s, l) => s + l.before, 0);
  const after = d.lines.reduce((s, l) => s + l.after, 0);
  return { before, after };
}
