import type { AllocationProposal, Budget, Period, Team, Unit } from "./contracts";

export interface AllocationWorkbenchDraft {
  mode: "transfer" | "addition";
  sourceTeamId?: string;
  targetTeamId: string;
  amount: string;
  unit: Unit;
  period: Period;
}
export interface AllocationRequest {
  draft: AllocationWorkbenchDraft;
  amount: string;
  content: string;
  companyBefore: number;
  companyAfter: number;
  changes: Array<{ teamId: string; before: number; after: number }>;
}
const samePeriod = (a: Period, b: Period) => a.start === b.start && a.end === b.end;
const cents = (amount: number) => Math.round(amount * 100);

function exactCents(text: string): number {
  const clean = text.trim();
  if (!/^(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d{1,2})?$/.test(clean)) throw new Error("Enter a positive amount with at most two decimal places.");
  const [whole, fraction = ""] = clean.replaceAll(",", "").split(".");
  const minor = BigInt(whole) * BigInt(100) + BigInt(fraction.padEnd(2, "0"));
  if (minor <= BigInt(0) || minor > BigInt(Number.MAX_SAFE_INTEGER)) throw new Error("Enter a valid positive amount.");
  return Number(minor);
}

/** A form request is a draft instruction, never a mutation of an allocation. */
export function prepareAllocationRequest(draft: AllocationWorkbenchDraft, { budgets, teams }: { budgets: Budget[]; teams: Pick<Team, "id" | "name">[] }): AllocationRequest {
  if (draft.unit !== "usd") throw new Error("This allocation form currently supports USD budgets.");
  const minor = exactCents(draft.amount);
  const amount = `${Math.floor(minor / 100)}.${String(minor % 100).padStart(2, "0")}`;
  const target = teams.find(t => t.id === draft.targetTeamId);
  if (!target) throw new Error("Choose a destination team.");
  const eligible = budgets.filter(b => b.unit === draft.unit && samePeriod(b.period, draft.period));
  if (!eligible.length || new Set(eligible.map(b => b.teamId)).size !== eligible.length) throw new Error("A unique budget is required for the selected period.");
  if (eligible.some(b => !Number.isFinite(b.allocated) || b.allocated < 0 || !Number.isSafeInteger(cents(b.allocated)))) throw new Error("The current allocations are unavailable. Refresh before drafting.");
  const targetBudget = eligible.find(b => b.teamId === target.id);
  if (!targetBudget) throw new Error("The destination team has no allocation for this exact period.");
  const companyMinor = eligible.reduce((sum, b) => sum + cents(b.allocated), 0);
  if (!Number.isSafeInteger(companyMinor + (draft.mode === "addition" ? minor : 0))) throw new Error("The resulting company amount is too large to represent exactly.");
  const periodText = `for ${draft.period.start} through ${draft.period.end}`;
  if (draft.mode === "addition") return {
    draft: { ...draft }, amount, companyBefore: companyMinor / 100, companyAfter: (companyMinor + minor) / 100, changes: [],
    content: `Add $${amount} to the company budget, prioritizing ${target.name} ${periodText}. Prepare a proposal for review.`,
  };
  const source = teams.find(t => t.id === draft.sourceTeamId);
  if (!source || source.id === target.id) throw new Error("Choose different source and destination teams.");
  const sourceBudget = eligible.find(b => b.teamId === source.id);
  if (!sourceBudget) throw new Error("The source team has no allocation for this exact period.");
  if (minor > cents(sourceBudget.allocated)) throw new Error("The amount exceeds the source team's allocation.");
  return {
    draft: { ...draft }, amount, companyBefore: companyMinor / 100, companyAfter: companyMinor / 100,
    changes: [{ teamId: source.id, before: sourceBudget.allocated, after: (cents(sourceBudget.allocated) - minor) / 100 }, { teamId: target.id, before: targetBudget.allocated, after: (cents(targetBudget.allocated) + minor) / 100 }],
    content: `Move $${amount} from ${source.name} to ${target.name} ${periodText}. Keep the company budget unchanged. Prepare a proposal for review.`,
  };
}

/** The returned backend proposal is authoritative. Never label a capped transfer as the requested amount. */
export function checkPreparedAllocation(request: AllocationRequest, proposal: AllocationProposal): { matches: boolean; reason?: string } {
  const fail = (reason: string) => ({ matches: false, reason });
  if (!samePeriod(request.draft.period, proposal.period) || request.draft.unit !== proposal.unit) return fail("The prepared draft uses a different period or unit. Inspect it before continuing.");
  if (cents(proposal.totalBefore) !== cents(request.companyBefore) || cents(proposal.totalAfter) !== cents(request.companyAfter)) return fail("The prepared company total differs from the requested change. Review the actual draft amounts.");
  if (request.draft.mode === "addition") return proposal.kind === "add_budget" && cents(proposal.addedAmount ?? NaN) === exactCents(request.amount) ? { matches: true } : fail("The prepared funding addition differs from the requested amount.");
  if (proposal.kind !== "redistribute") return fail("The prepared draft adds funding instead of transferring it.");
  const changed = proposal.lines.filter(line => cents(line.after) !== cents(line.before));
  if (changed.length !== 2 || request.changes.some(expected => !changed.some(line => line.teamId === expected.teamId && cents(line.before) === cents(expected.before) && cents(line.after) === cents(expected.after)))) return fail("The prepared transfer differs from your request, possibly because the source has less supported headroom. Review the actual draft amounts.");
  return { matches: true };
}
