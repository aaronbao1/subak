import type { AllocationProposal, AllocationState, AllocationTargetsInput, Budget, Period, Team, Unit } from "./contracts";

export interface AllocationTargetsPreview {
  input: AllocationTargetsInput;
  period: Period;
  unit: Unit;
  kind: "transfer" | "addition";
  companyBefore: number;
  companyAfter: number;
  changes: Array<{teamId: string; before: number; after: number}>;
}
const cents = (amount: number) => Math.round(amount * 100);
function moneyInput(text: string): number {
  if (!/^(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d{1,2})?$/.test(text.trim())) throw new Error("Use nonnegative amounts with at most two decimal places.");
  const [whole, fraction = ""] = text.trim().replaceAll(",", "").split(".");
  const result = BigInt(whole) * BigInt(100) + BigInt(fraction.padEnd(2, "0"));
  if (result > BigInt(Number.MAX_SAFE_INTEGER)) throw new Error("An allocation is too large to represent exactly.");
  return Number(result);
}
const decimal = (minor: number) => `${Math.floor(minor / 100)}.${String(minor % 100).padStart(2, "0")}`;

export function currentAllocationBase(budgets: Budget[], period: Period, unit: Unit) {
  const rows = budgets.filter(row => row.unit === unit && row.period.start === period.start && row.period.end === period.end);
  if (!rows.length || new Set(rows.map(row => row.teamId)).size !== rows.length) throw new Error("Unique current-period team allocations are required.");
  const versions = new Set(rows.map(row => row.version));
  if (versions.size !== 1 || !/^v?\d+$/.test(rows[0].version ?? "")) throw new Error("A consistent budget version is required. Refresh the allocations.");
  if (rows.some(row => !Number.isFinite(row.allocated) || row.allocated < 0 || !Number.isSafeInteger(cents(row.allocated)))) throw new Error("Current team allocations are unavailable.");
  return { rows, baseVersion: Number(rows[0].version!.replace(/^v/, "")) };
}

/** Validates the requested preview; the backend repeats all financial checks before saving a draft. */
export function prepareAllocationTargets(targets: Record<string,string>, {budgets, teams, period, unit}: {budgets:Budget[];teams:Pick<Team,"id"|"name">[];period:Period;unit:Unit}): AllocationTargetsPreview {
  if (unit !== "usd") throw new Error("This allocation form currently supports USD budgets.");
  const {rows,baseVersion}=currentAllocationBase(budgets,period,unit);
  if (Object.keys(targets).length !== rows.length || rows.some(row => !(row.teamId in targets) || !teams.some(team => team.id === row.teamId))) throw new Error("Set a budget for every team in this period.");
  const allocations:Record<string,string>={};
  const changes=rows.map(row=>{ const minor=moneyInput(targets[row.teamId]);allocations[row.teamId]=decimal(minor);return {teamId:row.teamId,before:row.allocated,after:minor/100}; });
  const before=rows.reduce((sum,row)=>sum+cents(row.allocated),0);
  const after=changes.reduce((sum,row)=>sum+cents(row.after),0);
  if (!Number.isSafeInteger(before)||!Number.isSafeInteger(after)) throw new Error("The company allocation is too large to represent exactly.");
  if (!changes.some(row=>cents(row.before)!==cents(row.after))) throw new Error("Change at least one team budget before preparing a draft.");
  if (after < before) throw new Error("Redistribute the remaining budget to teams so the company total stays the same.");
  if (after > before && changes.some(row=>row.after<row.before)) throw new Error("Review redistribution and added funding separately. Keep the total unchanged here, or raise allocations without cutting another team.");
  const end=new Date(`${period.end}T00:00:00Z`);end.setUTCDate(end.getUTCDate()+1);
  return {input:{baseVersion,periodStart:period.start,periodEndExclusive:end.toISOString().slice(0,10),unit:"USD",allocations,rationale:"Finance adjusted team allocations for the selected planning period."},period,unit,kind:after===before?"transfer":"addition",companyBefore:before/100,companyAfter:after/100,changes};
}

export function checkAllocationTargets(request:AllocationTargetsPreview,proposal:AllocationProposal):{matches:boolean;reason?:string} {
  const same=proposal.period.start===request.period.start&&proposal.period.end===request.period.end&&proposal.unit===request.unit&&cents(proposal.totalBefore)===cents(request.companyBefore)&&cents(proposal.totalAfter)===cents(request.companyAfter)&&proposal.lines.length===request.changes.length&&request.changes.every(expected=>proposal.lines.some(line=>line.teamId===expected.teamId&&cents(line.before)===cents(expected.before)&&cents(line.after)===cents(expected.after)));
  return same?{matches:true}:{matches:false,reason:"The prepared allocation differs from these requested team budgets. Inspect the saved amounts before continuing."};
}

/** Native approved allocations take precedence only for the exact displayed period and unit. */
export function allocationStateRows(state:AllocationState|undefined,period:Period|undefined,unit:Unit):Budget[]|undefined {
  if(!state||!period||unit!=="usd"||state.unit!=="USD"||state.period.startDate!==period.start)return undefined;
  const end=new Date(`${period.end}T00:00:00Z`);end.setUTCDate(end.getUTCDate()+1);
  if(state.period.endDateExclusive!==end.toISOString().slice(0,10))return undefined;
  return state.allocations.map(row=>({teamId:row.teamId,allocated:Number(row.amount),period,unit,version:String(state.stateVersion)}));
}
