import type { BudgetRequest, BudgetRequestInput, BudgetRequestKind } from "@/lib/contracts/budget-requests";
/** Form values remain distinct from ingested narrative. Only the explicit amount field states additional funding. */
export interface TeamUpdateFormValues {
  teamId: string;
  title: string;
  projectName: string;
  summary: string;
  amount: string;
  start: string;
  end: string;
}
export function requestedAmount(value: string): string | null {
  if (!value.trim()) return null;
  if (!/^(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d{1,2})?$/.test(value.trim())) throw new Error("Enter an exact positive amount, such as 5,000 or 50.25.");
  const [whole, fraction = ""] = value.trim().replaceAll(",", "").split(".");
  const cents = BigInt(whole) * BigInt(100) + BigInt(fraction.padEnd(2, "0"));
  if (cents <= BigInt(0) || cents > BigInt(Number.MAX_SAFE_INTEGER)) throw new Error("Enter a positive requested increase, or leave it blank.");
  return `${cents / BigInt(100)}.${String(cents % BigInt(100)).padStart(2, "0")}`;
}
function isoDate(value: string): number {
  const parsed = Date.parse(`${value}T00:00:00Z`);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || !Number.isFinite(parsed) || new Date(parsed).toISOString().slice(0, 10) !== value) throw new Error("Choose valid start and end dates.");
  return parsed;
}
export function prepareTeamUpdateForm(value: TeamUpdateFormValues, teamIds: string[]) {
  if (!teamIds.includes(value.teamId)) throw new Error("Choose the team making this request.");
  const title = value.title.trim(), summary = value.summary.trim();
  if (!title) throw new Error("Give the update a short title.");
  if (!summary) throw new Error("Describe the team’s plan or request.");
  const start = isoDate(value.start), end = isoDate(value.end);
  if (end < start) throw new Error("The end date must be on or after the start date.");
  return { teamId: value.teamId, title, projectName: value.projectName.trim() || null, summary, requestedAmount: requestedAmount(value.amount), periodStart: value.start, periodEndExclusive: new Date(end + 86_400_000).toISOString().slice(0, 10) };
}

/** A clarification creates a new request linked to its original update; it never edits source evidence. */
export function teamUpdateInput(value: TeamUpdateFormValues, teamIds: string[], kind: BudgetRequestKind, clientRequestId: string, sourceUpdate?: BudgetRequest): BudgetRequestInput {
  const prepared = prepareTeamUpdateForm(value, teamIds);
  if (sourceUpdate && prepared.requestedAmount === null) throw new Error("Enter the explicit additional amount for this budget request.");
  return { clientRequestId, teamId: prepared.teamId, title: prepared.title, requestKind: kind,
    ...(kind !== "team" && prepared.projectName ? { projectName: prepared.projectName } : {}),
    narrative: prepared.summary, requestedAmount: prepared.requestedAmount, unit: "USD",
    periodStart: prepared.periodStart, periodEndExclusive: prepared.periodEndExclusive,
    ...(sourceUpdate ? { sourceRef: `budget-request:${sourceUpdate.id}`, evidenceRefs: [{ kind: "budget_request" as const, id: sourceUpdate.id }] } : {}) };
}
