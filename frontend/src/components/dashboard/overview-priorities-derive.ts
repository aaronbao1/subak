import type { AllocationProposal, ContextItem, Period, Team, Unit } from "@/lib/contracts";
import type { ScopeSummary } from "@/lib/contracts/finance-view";
import type { DriverInsight } from "@/lib/driver-insights";

export type OverviewPriority = {
  id: string;
  kind: "budget" | "proposal" | "context" | "driver";
  driverInsight?: DriverInsight;
  title: string;
  description: string;
  amount?: number;
  unit: Unit;
  period: Period;
  team?: Team;
  summary?: ScopeSummary;
  sources: ContextItem[];
  proposals: AllocationProposal[];
};

/** Priorities use the matching financial target or explicit, dated source context. Source mentions never acquire an inferred dollar effect. */
export function buildOverviewPriorities({ summaries, proposals, context, teams, period, unit, asOf, scheduledDrivers = [] }: {
  summaries: Array<{ team: Team; summary: ScopeSummary }>;
  proposals: AllocationProposal[];
  context: ContextItem[];
  teams: Team[];
  period: Period;
  unit: Unit;
  asOf: string;
  scheduledDrivers?: Array<{ insight: DriverInsight; start?: string }>;
}): OverviewPriority[] {
  const result: OverviewPriority[] = [];
  const over = summaries.filter(({ summary }) => summary.variance !== null && summary.variance > 0)
    .sort((a, b) => b.summary.variance! - a.summary.variance! || a.team.name.localeCompare(b.team.name));
  for (const { team, summary } of over.slice(0, 2)) result.push({ id: `budget:${team.id}`, kind: "budget", title: `${team.name} is expected over budget`, description: "Matching forecast and budget for the selected period", amount: summary.variance!, unit, period, team, summary, sources: [], proposals: [] });

  const actionable = proposals.filter(proposal => ["proposed", "pending", "stale", "failed"].includes(proposal.status) && proposal.unit === unit && proposal.period.start === period.start && proposal.period.end === period.end);
  if (actionable.length) {
    const waiting = actionable.filter(proposal => proposal.status === "proposed").length;
    result.push({ id: "proposals", kind: "proposal", title: waiting ? `${waiting} budget ${waiting === 1 ? "proposal needs" : "proposals need"} review` : `${actionable.length} budget ${actionable.length === 1 ? "change needs" : "changes need"} attention`, description: waiting ? "Review the draft before changing allocations" : "Check the latest save or draft status", unit, period, sources: [], proposals: actionable });
  }

  const knownTeams = new Set(teams.map(team => team.id));
  const windowEnd = new Date(Date.parse(`${asOf}T00:00:00Z`) + 14 * 86_400_000).toISOString().slice(0, 10);
  const sources = context.filter(item => !item.supersededBy && item.claimType !== "interpretation" && item.sources.length > 0 && item.effectiveFrom && item.effectiveFrom > asOf && item.effectiveFrom <= windowEnd && (!item.effectiveTo || item.effectiveTo >= item.effectiveFrom) && (item.scope === "company" || item.teamIds.some(id => knownTeams.has(id))))
    .sort((a, b) => a.effectiveFrom!.localeCompare(b.effectiveFrom!) || (a.category === "pricing" ? -1 : b.category === "pricing" ? 1 : 0) || a.title.localeCompare(b.title));
  const groups = new Map<string, ContextItem[]>();
  for (const item of sources) {
    const key = `${item.category ?? item.kind}:${item.scope === "company" ? "company" : [...item.teamIds].sort().join(",")}:${item.effectiveFrom}`;
    groups.set(key, [...(groups.get(key) ?? []), item]);
  }
  for (const group of groups.values()) {
    if (result.length >= 5) break;
    const first = group[0];
    const scope = first.scope === "company" ? "Company" : first.teamIds.map(id => teams.find(team => team.id === id)?.name).filter(Boolean).join(", ");
    result.push({ id: `context:${first.id}`, kind: "context", title: group.length === 1 ? first.title : `${group.length} upcoming ${first.category ?? "plan"} changes`, description: `${scope} · starts ${first.effectiveFrom} · source context`, unit, period, sources: group, proposals: [] });
  }
  const shownSources = new Set(result.flatMap(priority => priority.sources.map(item => item.id)));
  const upcomingDrivers = scheduledDrivers.filter(({ insight, start }) => start && start.slice(0, 10) > asOf && start.slice(0, 10) <= windowEnd && insight.inSnapshot && ["modeled", "included", "queued"].includes(insight.status) && !shownSources.has(insight.driver.id))
    .sort((a, b) => a.start!.localeCompare(b.start!) || a.insight.title.localeCompare(b.insight.title));
  for (const { insight, start } of upcomingDrivers) {
    if (result.length >= 5) break;
    result.push({ id: `driver:${insight.driver.id}`, kind: "driver", title: insight.title, description: `Starts ${start!.slice(0, 10)} · ${insight.status === "queued" ? "awaiting forecast update" : "included in published outlook"}`, unit, period, sources: [], proposals: [], driverInsight: insight });
  }
  return result.slice(0, 5);
}
