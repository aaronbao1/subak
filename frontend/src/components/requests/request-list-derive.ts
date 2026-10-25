import type { BudgetRequest } from "@/lib/contracts/budget-requests";
import type { Period } from "@/lib/contracts";

export const REQUEST_STATUS_LABEL: Record<BudgetRequest["status"], string> = {
  submitted: "Requested", pending_review: "Draft ready", needs_revision: "Needs revision", partially_funded: "Partially funded", approved_applied: "Approved and applied", rejected: "Rejected",
};
export const isOpenRequest = (request: BudgetRequest): boolean => !["approved_applied", "rejected"].includes(request.status);
export function requestMatchesPeriod(request: BudgetRequest, period: Period): boolean {
  return request.periodStart === period.start && request.periodEndExclusive === new Date(Date.parse(`${period.end}T00:00:00Z`) + 86_400_000).toISOString().slice(0, 10);
}
/** A pending subtotal uses explicit remaining amounts from matching targets, never narrative extraction or approved dollars. */
export function pendingRequestSummary(requests: BudgetRequest[], period?: Period) {
  const open = requests.filter(isOpenRequest);
  const matching = period ? open.filter(request => requestMatchesPeriod(request, period)) : [];
  let cents = BigInt(0), known = 0;
  for (const request of matching) {
    const value = request.remainingRequestedAmount;
    if (value === null || !/^\d+(?:\.\d{1,2})?$/.test(value)) continue;
    const [whole, fraction = ""] = value.split(".");
    cents += BigInt(whole) * BigInt(100) + BigInt(fraction.padEnd(2, "0"));
    known++;
  }
  return { open, matching, total: known ? `${cents / BigInt(100)}.${String(cents % BigInt(100)).padStart(2, "0")}` : null, unknownCount: matching.length - known };
}
export function requestMoney(value: string | null | undefined): string {
  if (value == null || !Number.isFinite(Number(value))) return "Not specified";
  const amount = Number(value);
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2, minimumFractionDigits: amount % 1 ? 2 : 0 }).format(amount);
}
export function requestDates(start: string, endExclusive: string): string {
  const label = (value: string) => new Date(`${value}T00:00:00Z`).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
  const end = new Date(Date.parse(`${endExclusive}T00:00:00Z`) - 86_400_000).toISOString().slice(0, 10);
  return `${label(start)}–${label(end)}`;
}
