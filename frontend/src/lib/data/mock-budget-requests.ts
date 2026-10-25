import type { Dataset } from '@/fixtures';
import { DEMO_NOW, nextDemoTimestamp } from '@/fixtures/generate';
import type { AllocationProposal, Budget, Decision, Forecast, ForecastBundle } from '@/lib/contracts';
import type { AllocationDraftReceipt, AllocationState, AllocationTargetsInput, BudgetRequest, BudgetRequestAssessment, BudgetRequestDraftInput, BudgetRequestInput } from '@/lib/contracts/budget-requests';
import { billableAmount } from '@/lib/finance-summary';

export interface MockBudgetRequestDependencies {
  getBudgets: () => Budget[];
  getProposals: () => AllocationProposal[];
  getDecisions: () => Decision[];
  getBudgetVersion: () => number;
  getBudgetVersionToken: () => string;
  getForecastBundle: () => ForecastBundle;
  createProposal: (proposal: AllocationProposal) => void;
  actorId?: string;
  /** Optional explicitly supplied company envelope; otherwise the fixture allocates its full envelope. */
  getEnvelopeTotal?: () => string;
}
type StoredRequest = { input: BudgetRequestInput; id: string; createdAt: string; fingerprint: string };
type DraftRecord = { fingerprint: string; proposalId: string; requestId?: string };
const ZERO = BigInt(0);
const fail = (message: string): never => { throw Object.assign(new Error(message), { definiteFailure: true }); };
const clone = <T,>(value: T): T => structuredClone(value);
const max = (a: bigint, b: bigint) => a > b ? a : b;
const after = (date: string) => new Date(Date.parse(`${date}T00:00:00Z`) + 86_400_000).toISOString().slice(0, 10);
const money = (value: bigint) => { const digits = (value < ZERO ? -value : value).toString().padStart(3, '0'); return `${value < ZERO ? '-' : ''}${digits.slice(0, -2)}.${digits.slice(-2)}`; };
function cents(value: string): bigint {
  if (typeof value !== 'string' || !/^-?\d+(?:\.\d{1,2})?$/.test(value.trim())) return fail('Money must be an explicit decimal string with at most two decimal places.');
  const raw = value.trim(), negative = raw.startsWith('-');
  const [whole, fraction = ''] = raw.replace(/^-/, '').split('.');
  const amount = BigInt(whole + fraction.padEnd(2, '0')) * (negative ? -BigInt(1) : BigInt(1));
  if (amount <= -BigInt('100000000000000000') || amount >= BigInt('100000000000000000')) return fail('Amount is too large.');
  return amount;
}
function numericCents(value: number): bigint {
  if (!Number.isFinite(value) || !Number.isSafeInteger(Math.round(value * 100))) return fail('Amount exceeds the exact precision supported by this mock.');
  return BigInt(Math.round(value * 100));
}
function compatibleNumber(value: bigint): number {
  if (value > BigInt(Number.MAX_SAFE_INTEGER) || value < -BigInt(Number.MAX_SAFE_INTEGER)) return fail('Amount exceeds the exact precision supported by this mock proposal.');
  const result = Number(value) / 100;
  if (numericCents(result) !== value || cents(String(result)) !== value) return fail('Amount cannot safely round-trip through the mock proposal format.');
  return result;
}
function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  if (value && typeof value === 'object') return `{${Object.entries(value).filter(([, v]) => v !== undefined).sort(([a], [b]) => a.localeCompare(b)).map(([k, v]) => `${JSON.stringify(k)}:${canonical(v)}`).join(',')}}`;
  return JSON.stringify(value);
}
function text(value: string, limit: number, label: string): string {
  if (typeof value !== 'string' || !value.trim() || value.trim().length > limit) return fail(`${label} must contain text within ${limit} characters.`);
  return value.trim();
}

/** In-memory demo intake and draft receipts. This class never changes budgets or issued forecasts. */
export class MockBudgetRequests {
  private readonly requests = new Map<string, StoredRequest>();
  private readonly requestKeys = new Map<string, string>();
  private readonly drafts = new Map<string, DraftRecord>();
  private readonly proposalRequests = new Map<string, string[]>();
  private sequence = 0;
  private readonly actor: string;
  private readonly fx: Dataset;
  private readonly deps: MockBudgetRequestDependencies;
  constructor(fx: Dataset, deps: MockBudgetRequestDependencies) {
    this.fx = fx;
    this.deps = deps;
    this.actor = deps.actorId ?? 'finance-demo';
  }

  private period(start: string, end: string) {
    const periods = [this.fx.company.currentPeriod, ...this.deps.getBudgets().map(b => b.period)];
    const found = periods.find(p => p.start === start && after(p.end) === end);
    if (!found || start >= end) return fail('Request dates must match an existing planning period.');
    return { id: `synthetic-period:${start}:${end}`, startDate: start, endDateExclusive: end, label: found.label ?? `${start}–${found.end}` };
  }
  private budgets(start: string, end: string) {
    const values = this.deps.getBudgets().filter(b => b.unit === 'usd' && b.period.start === start && after(b.period.end) === end);
    if (new Set(values.map(b => b.teamId)).size !== values.length) return fail('Duplicate team allocation in this fixture.');
    return values;
  }
  private spending(teamId: string | undefined, start: string, end: string) {
    return this.fx.spending.filter(r => r.unit === 'usd' && (teamId === undefined || r.teamId === teamId) && r.date >= start && r.date < end && r.date <= DEMO_NOW.slice(0, 10));
  }
  private spent(teamId: string | undefined, start: string, end: string): bigint {
    return this.spending(teamId, start, end).reduce((sum, row) => sum + numericCents(billableAmount(row)), ZERO);
  }
  private forecast(teamId: string, start: string, end: string) {
    const view = this.deps.getForecastBundle().views.find(v => v.scope.type === 'team' && v.scope.id === teamId && v.dataset_id === this.fx.company.id && v.target.unit.toLowerCase() === 'usd' && v.target.basis === 'planning' && (v.target.timezone ?? v.timezone) === 'UTC' && v.target.quantity === 'spend');
    if (!view) return null;
    const points = [view.planning_period_outlook, view.quarter_outlook, ...(view.weekly ?? [])] as Array<Record<string, unknown> | undefined>;
    const point = points.find(p => p?.start === start && p.end === end && p.partial !== true && p.complete !== false && typeof p.base === 'number' && Number.isFinite(p.base));
    return point ? { amount: numericCents(point.base as number), runId: view.run_id } : null;
  }
  private assessment(input: BudgetRequestInput): BudgetRequestAssessment {
    const budgets = this.budgets(input.periodStart, input.periodEndExclusive);
    const budget = budgets.find(b => b.teamId === input.teamId);
    const allocation = budget ? numericCents(budget.allocated) : null;
    const recorded = this.spent(input.teamId, input.periodStart, input.periodEndExclusive);
    const projection = this.forecast(input.teamId, input.periodStart, input.periodEndExclusive);
    const allocated = budgets.reduce((sum, b) => sum + numericCents(b.allocated), ZERO);
    const donors = budgets.filter(b => b.teamId !== input.teamId).flatMap(b => {
      const forecast = this.forecast(b.teamId, input.periodStart, input.periodEndExclusive);
      if (!forecast) return [];
      const headroom = numericCents(b.allocated) - max(forecast.amount, this.spent(b.teamId, input.periodStart, input.periodEndExclusive));
      return headroom > ZERO ? [{ teamId: b.teamId, headroom: money(headroom) }] : [];
    }).sort((a, b) => a.teamId.localeCompare(b.teamId));
    return { assessedAt: nextDemoTimestamp(), budgetVersion: budgets.length ? this.deps.getBudgetVersion() : null,
      envelopeTotal: budgets.length ? money(this.deps.getEnvelopeTotal ? cents(this.deps.getEnvelopeTotal()) : allocated) : null,
      teamAllocation: allocation === null ? null : money(allocation), recordedSpend: money(recorded), forecastAmount: projection ? money(projection.amount) : null, forecastRunId: projection?.runId ?? null,
      forecastStatus: projection ? 'available' : 'unavailable', forecastUnit: 'USD', forecastBasis: 'full_period_total', projectedHeadroom: allocation !== null && projection ? money(allocation - max(projection.amount, recorded)) : null,
      requestedAllocation: allocation !== null && input.requestedAmount !== null ? money(allocation + cents(input.requestedAmount)) : null,
      availableDonors: donors, amountIncludedInForecast: false,
      qualification: `Synthetic fixture assessment against matching team allocation and issued full-period forecast. Recorded spend is a subtotal with incomplete source coverage. The requested amount is additional allocation intent and is not included in the forecast.${input.requestKind !== 'team' ? ' Project context uses its funding team; no separate project forecast is available.' : ''}${!projection ? ' No matching complete team forecast is available.' : ''}${!budgets.length ? ' No budget envelope is available for this period.' : ''}` };
  }

  createRequest(raw: BudgetRequestInput): BudgetRequest {
    const requestedAmount = raw.requestedAmount === null ? null : money(cents(raw.requestedAmount));
    if (requestedAmount !== null && cents(requestedAmount) <= ZERO) return fail('Requested amount must be positive additional allocation or null.');
    const input: BudgetRequestInput = { ...clone(raw), clientRequestId: text(raw.clientRequestId, 200, 'Request identity'), title: text(raw.title, 300, 'Title'), narrative: text(raw.narrative, 20000, 'Narrative'), requestedAmount };
    if (input.unit !== 'USD' || !['team', 'project', 'initiative'].includes(input.requestKind)) return fail('Choose a supported USD request kind.');
    if ((input.projectName?.length ?? 0) > 300 || (input.sourceRef?.length ?? 0) > 1000 || (input.evidenceRefs?.length ?? 0) > 100) return fail('Request source or evidence is too long.');
    const key = `${this.actor}:${input.clientRequestId}`, fingerprint = canonical(input);
    const existingId = this.requestKeys.get(key);
    if (existingId) {
      if (this.requests.get(existingId)!.fingerprint !== fingerprint) return fail('This request identity was already used for different content.');
      return this.getRequest(existingId);
    }
    if (!this.fx.teams.some(t => t.id === input.teamId)) return fail('The request must name a known active team.');
    this.period(input.periodStart, input.periodEndExclusive);
    for (const ref of input.evidenceRefs ?? []) {
      const known = ref.kind === 'budget_request' ? this.requests.has(ref.id) : ref.kind === 'document' ? this.fx.documents.some(d => d.id === ref.id) : ref.kind === 'signal' ? this.fx.context.some(c => c.id === ref.id) : ref.kind === 'forecast_snapshot' ? this.deps.getForecastBundle().views.some(v => v.run_id === ref.id || v.id === ref.id) : ref.kind === 'spend_summary' && this.fx.spending.some(r => r.id === ref.id);
      if (!known) return fail('A request evidence reference is not available in this fixture.');
    }
    const id = `mock-request:${this.actor}:${++this.sequence}`;
    this.requests.set(id, { input, id, createdAt: nextDemoTimestamp(), fingerprint });
    this.requestKeys.set(key, id);
    return this.getRequest(id);
  }

  private linkedIds(id: string): Set<string> {
    const linked = new Set([...this.proposalRequests].filter(([, refs]) => refs.includes(id)).map(([pid]) => pid));
    let changed = true;
    while (changed) { changed = false; for (const p of this.deps.getProposals()) if (!linked.has(p.id) && p.revisesProposalId && linked.has(p.revisesProposalId)) { linked.add(p.id); changed = true; } }
    return linked;
  }
  private inheritedRequests(proposalId: string): string[] {
    const result = new Set<string>(), seen = new Set<string>();
    let id: string | undefined = proposalId;
    while (id && !seen.has(id)) { seen.add(id); for (const ref of this.proposalRequests.get(id) ?? []) result.add(ref); id = this.deps.getProposals().find(p => p.id === id)?.revisesProposalId; }
    return [...result];
  }
  getRequest(id: string): BudgetRequest {
    const stored = this.requests.get(id);
    if (!stored) return fail('Budget request not found.');
    const linked = this.linkedIds(id), proposals = this.deps.getProposals().filter(p => linked.has(p.id));
    const decisions = [...new Map(this.deps.getDecisions().filter(d => linked.has(d.proposalId)).map(d => [d.id, d])).values()];
    const applied = new Set<string>();
    let approved = ZERO;
    for (const decision of decisions) {
      if (stored.input.requestedAmount === null || decision.action !== 'applied' || applied.has(decision.proposalId) || decision.unit !== 'usd') continue;
      applied.add(decision.proposalId);
      const sameTeam = this.inheritedRequests(decision.proposalId).filter(ref => { const request = this.requests.get(ref)?.input; return request?.teamId === stored.input.teamId && request.requestedAmount !== null; });
      if (sameTeam.length > 1) continue; // A team increase does not earmark funds between same-team requests.
      const line = decision.lines.find(l => l.teamId === stored.input.teamId);
      if (line) approved += max(ZERO, numericCents(line.after) - numericCents(line.before));
    }
    const replaced = new Set(proposals.map(p => p.revisesProposalId).filter(Boolean));
    const leaves = proposals.filter(p => !replaced.has(p.id));
    const requested = stored.input.requestedAmount === null ? null : cents(stored.input.requestedAmount);
    const status = requested !== null && approved >= requested ? 'approved_applied' : approved > ZERO ? 'partially_funded' : leaves.some(p => p.status === 'proposed' && (!p.basedOnBudgetVersion || p.basedOnBudgetVersion === this.deps.getBudgetVersionToken())) ? 'pending_review' : leaves.some(p => ['stale', 'failed', 'revised', 'proposed'].includes(p.status)) ? 'needs_revision' : leaves.length && leaves.every(p => decisions.some(d => d.proposalId === p.id && d.action === 'rejected')) ? 'rejected' : 'submitted';
    return clone({ ...stored.input, id, period: this.period(stored.input.periodStart, stored.input.periodEndExclusive), source: { reference: stored.input.sourceRef ?? null, submittedBy: this.actor, submittedAt: stored.createdAt }, status,
      linkedProposalIds: proposals.map(p => p.id), decisionIds: decisions.map(d => d.id), approvedAmount: money(approved), remainingRequestedAmount: requested === null ? null : money(max(ZERO, requested - approved)), assessment: this.assessment({ ...stored.input, requestedAmount: requested === null ? null : money(max(ZERO, requested - approved)) }) });
  }
  listRequests(teamId?: string): BudgetRequest[] { return [...this.requests.values()].reverse().filter(r => !teamId || r.input.teamId === teamId).map(r => this.getRequest(r.id)); }
  assessRequest(id: string): BudgetRequest { return this.getRequest(id); }

  private operation(key: string, fingerprint?: string): DraftRecord | undefined {
    const safe = text(key, 200, 'Operation identity');
    const existing = this.drafts.get(`${this.actor}:${safe}`);
    if (existing && fingerprint !== undefined && existing.fingerprint !== fingerprint) return fail('This operation identity was already used for a different allocation draft.');
    return existing;
  }
  private receipt(record: DraftRecord): AllocationDraftReceipt { return { proposalId: record.proposalId, ...(record.requestId ? { request: this.getRequest(record.requestId) } : {}) }; }
  reconcileDraft(operationId: string): AllocationDraftReceipt | undefined { const record = this.operation(operationId); return record ? this.receipt(record) : undefined; }

  private saveDraft(input: AllocationTargetsInput, operationId: string, fingerprint: string, requestId?: string): AllocationDraftReceipt {
    const existing = this.operation(operationId, fingerprint);
    if (existing) return this.receipt(existing);
    if (!Number.isInteger(input.baseVersion) || input.baseVersion !== this.deps.getBudgetVersion()) return fail('Budget version is stale or unsupported; review the current allocations.');
    const period = this.period(input.periodStart, input.periodEndExclusive);
    if (input.unit !== 'USD') return fail('Only USD allocation drafts are supported.');
    const budgets = this.budgets(input.periodStart, input.periodEndExclusive);
    const expected = budgets.map(b => b.teamId).sort(), supplied = Object.keys(input.allocations).sort();
    if (!budgets.length || canonical(expected) !== canonical(supplied)) return fail('Include every currently allocated team exactly once.');
    if (expected.some(id => !this.fx.teams.some(t => t.id === id))) return fail('Allocation draft includes an inactive or unknown team.');
    const targets = budgets.map(b => ({ teamId: b.teamId, before: numericCents(b.allocated), after: cents(input.allocations[b.teamId]) }));
    if (targets.some(t => t.after < ZERO)) return fail('Allocation targets cannot be negative.');
    const totalBefore = targets.reduce((sum, t) => sum + t.before, ZERO), totalAfter = targets.reduce((sum, t) => sum + t.after, ZERO), increase = totalAfter - totalBefore;
    if (!targets.some(t => t.before !== t.after)) return fail('The allocation plan has no change.');
    if (increase < ZERO) return fail('Reducing the envelope is unsupported; redistribute the full allocation.');
    if (increase > ZERO && targets.some(t => t.after < t.before)) return fail('Mixed additions and transfers need separate proposals.');
    const refs = [...new Set(input.requestIds ?? [])].sort();
    const fundingTeams = new Set<string>();
    for (const id of refs) {
      const row = this.getRequest(id);
      if (row.periodStart !== input.periodStart || row.periodEndExclusive !== input.periodEndExclusive || !expected.includes(row.teamId)) return fail('A linked request belongs to another period or team.');
      if (!requestId && row.requestedAmount === null) return fail('An amountless update is source context, not a funding request for an allocation target.');
      if (!requestId && fundingTeams.has(row.teamId)) return fail('Link at most one funding request per team; same-team attribution would be ambiguous.');
      if (row.requestedAmount !== null) fundingTeams.add(row.teamId);
    }
    const sourceRefs = [...new Set([...refs, ...refs.flatMap(id => (this.requests.get(id)!.input.evidenceRefs ?? []).filter(ref => ref.kind === 'budget_request').map(ref => ref.id))])];
    const sourceDocuments = new Map(sourceRefs.flatMap(id => (this.requests.get(id)!.input.evidenceRefs ?? []).filter(ref => ref.kind === 'document').flatMap(ref => {
      const document = this.fx.documents.find(d => d.id === ref.id);
      return document ? [[document.id, { documentId: document.id, title: document.title, date: document.date, ...(ref.note ? { locator: ref.note } : {}) }] as const] : [];
    })));
    const proposal: AllocationProposal = { id: `mock-proposal:${this.actor}:${++this.sequence}`, version: 1, kind: increase > ZERO ? 'add_budget' : 'redistribute', unit: 'usd',
      period: { start: period.startDate, end: new Date(Date.parse(`${period.endDateExclusive}T00:00:00Z`) - 86_400_000).toISOString().slice(0, 10), label: period.label },
      totalBefore: compatibleNumber(totalBefore), totalAfter: compatibleNumber(totalAfter), ...(increase > ZERO ? { addedAmount: compatibleNumber(increase) } : {}),
      lines: targets.map(t => ({ teamId: t.teamId, before: compatibleNumber(t.before), after: compatibleNumber(t.after) })), rationale: text(input.rationale, 10000, 'Rationale'),
      citations: [...sourceRefs.map(id => { const request = this.requests.get(id)!; return { documentId: id, title: request.input.title, excerpt: request.input.narrative, locator: 'Submitted team request', date: request.createdAt.slice(0, 10) }; }), ...sourceDocuments.values()],
      createdAt: nextDemoTimestamp(), status: 'proposed', basedOnBudgetVersion: this.deps.getBudgetVersionToken(), forecastsReviewed: targets.flatMap(t => {
        const projection = this.forecast(t.teamId, input.periodStart, input.periodEndExclusive);
        return projection ? [{ id: projection.runId, teamId: t.teamId, period: { start: input.periodStart, end: new Date(Date.parse(`${input.periodEndExclusive}T00:00:00Z`) - 86_400_000).toISOString().slice(0, 10) }, status: 'available', unit: 'usd', basis: 'full_period', kind: 'forecast', origin: 'placeholder', projected: compatibleNumber(projection.amount), assumptions: [], limitations: ['Synthetic issued forecast; request amount is excluded.'], generatedAt: DEMO_NOW } satisfies Forecast] : [];
      }) };
    this.deps.createProposal(clone(proposal));
    this.proposalRequests.set(proposal.id, refs);
    const record = { fingerprint, proposalId: proposal.id, ...(requestId ? { requestId } : {}) };
    this.drafts.set(`${this.actor}:${operationId.trim()}`, record);
    return this.receipt(record);
  }
  draftAllocationTargets(raw: AllocationTargetsInput, operationId: string): AllocationDraftReceipt {
    const input = { ...clone(raw), allocations: Object.fromEntries(Object.entries(raw.allocations).map(([id, value]) => [id, money(cents(value))])), rationale: text(raw.rationale, 10000, 'Rationale'), requestIds: [...new Set(raw.requestIds ?? [])].sort() };
    return this.saveDraft(input, operationId, canonical({ endpoint: 'allocation-drafts', actor: this.actor, input }));
  }
  draftRequest(id: string, input: BudgetRequestDraftInput, operationId: string): AllocationDraftReceipt {
    const fingerprint = canonical({ endpoint: 'budget-request-draft', actor: this.actor, id, input });
    const existing = this.operation(operationId, fingerprint);
    if (existing) return this.receipt(existing);
    const request = this.getRequest(id);
    if (request.remainingRequestedAmount === null) return fail('This update has no explicit funding amount.');
    const remaining = cents(request.remainingRequestedAmount);
    if (remaining <= ZERO) return fail('Confirmed decisions already cover this request.');
    const budgets = this.budgets(request.periodStart, request.periodEndExclusive);
    const allocations = Object.fromEntries(budgets.map(b => [b.teamId, numericCents(b.allocated)]));
    if (!(request.teamId in allocations)) return fail('The request team has no matching allocation.');
    if (input.actionType === 'addition') { if (input.sourceTeamId !== undefined) return fail('Additional funding has no source team.'); }
    else if (input.actionType === 'transfer') {
      if (!input.sourceTeamId || input.sourceTeamId === request.teamId) return fail('Select a different explicit source team.');
      const donor = request.assessment.availableDonors.find(d => d.teamId === input.sourceTeamId);
      if (!donor || cents(donor.headroom) < remaining) return fail('The source has insufficient supported forecast headroom for the entire remaining request.');
      allocations[input.sourceTeamId] -= remaining;
    } else return fail('Choose addition or transfer.');
    allocations[request.teamId] += remaining;
    return this.saveDraft({ baseVersion: input.baseVersion, periodStart: request.periodStart, periodEndExclusive: request.periodEndExclusive, unit: 'USD', allocations: Object.fromEntries(Object.entries(allocations).map(([teamId, amount]) => [teamId, money(amount)])), rationale: `Review request: ${request.title}. ${request.narrative}`.slice(0, 10000), requestIds: [id] }, operationId, fingerprint, id);
  }

  getAllocationState(): AllocationState {
    const start = this.fx.company.currentPeriod.start, end = after(this.fx.company.currentPeriod.end), budgets = this.budgets(start, end);
    const allocated = budgets.reduce((sum, b) => sum + numericCents(b.allocated), ZERO), envelope = this.deps.getEnvelopeTotal ? cents(this.deps.getEnvelopeTotal()) : allocated;
    const coverage = (rows: Dataset['spending']): 'complete' | 'partial' | 'missing' => !rows.length ? 'missing' : rows.some(r => !r.complete) || end > DEMO_NOW.slice(0, 10) || new Set(rows.map(r => r.date)).size !== (Date.parse(end) - Date.parse(start)) / 86_400_000 ? 'partial' : 'complete';
    const records = this.spending(undefined, start, end), known = new Set(this.fx.teams.map(t => t.id)), shared = records.filter(r => !known.has(r.teamId));
    const latest = this.deps.getDecisions().filter(d => d.action === 'applied' && this.deps.getProposals().some(p => p.id === d.proposalId && p.period.start === start && after(p.period.end) === end)).sort((a, b) => b.appliedAt.localeCompare(a.appliedAt))[0];
    return { period: this.period(start, end), unit: 'USD', stateVersion: this.deps.getBudgetVersion(), envelopeTotal: money(envelope), allocatedTotal: money(allocated), unallocatedAmount: money(envelope - allocated),
      allocations: budgets.map(b => { const spent = this.spent(b.teamId, start, end); return { teamId: b.teamId, amount: money(numericCents(b.allocated)), recordedSpend: money(spent), remaining: money(numericCents(b.allocated) - spent), coverageStatus: coverage(this.spending(b.teamId, start, end)) }; }),
      updatedAt: latest?.appliedAt ?? DEMO_NOW, lastDecisionId: latest?.id ?? null, spendCoverage: { status: coverage(records), unattributedSpend: money(shared.reduce((sum, r) => sum + numericCents(billableAmount(r)), ZERO)), unattributedRecords: shared.length, notes: ['Synthetic fixture spending; partial or missing source coverage remains explicit. Included usage is excluded.'] },
      note: 'Internal planning allocations; no provider credits are transferred or enforced.' };
  }
}
