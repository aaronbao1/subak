import type { AllocationProposal, AssistantMessage, ConversationContext, Decision, ProposalActionState, Team, Unit } from '@/lib/contracts';

export interface AssistantAllocationSummary {
  unit: Unit;
  period: { start: string; end: string; label: string };
  before: string;
  after: string;
  delta: string;
  lines: Array<{ teamId: string; teamName: string; before: string; after: string; delta: string }>;
}
export interface AssistantAnswerModel {
  kind: 'clarification' | 'proposal' | 'allocation_draft' | 'scenario' | 'answer';
  headline: string;
  status: string;
  statusTone: 'neutral' | 'success' | 'warning' | 'danger';
  summary: string | null;
  /** Intact opening paragraph/section for a visually bounded general-answer preview. */
  preview?: string;
  /** Complete presentation text, never a first-sentence or numeric extraction. */
  body: string;
  bodyMode: 'inline' | 'details';
  detailsLabel: string;
  proposalId?: string;
  clarification?: { slot: NonNullable<ConversationContext['pending_slot']>; label: string };
  allocation?: AssistantAllocationSummary;
  notice?: string;
}

const SIMULATED_FOOTER = '_Simulated: this reply comes from the deterministic fake Droid runner (a scripted playbook, not a model). Proposals still need a finance approver._';
function cleanKnownCopy(value: string): string {
  return value
    .replaceAll(SIMULATED_FOOTER, '_Proposals still need a finance approver._')
    .replaceAll('Projections are simulated (', 'Projections are estimates (')
    .replace(/the scripted assistant(?= has not inferred a numerical effect from them\.)/g, 'the assistant')
    .replace(/the deterministic fake runner(?= does not interpret free-text questions; this is the standard per-team comparison\.)/g, 'the assistant')
    .replace(/This is a synthetic UI fixture for issued run \*\*[^*\n]+\*\*, (?:company|team|person|shared) \*\*[^*\n]+\*\*(?:, driver \*\*[^*\n]+\*\*)?\./g, 'This explanation uses the selected forecast.')
    .replace(/This is a synthetic UI fixture for issued run/gi, 'For issued run')
    .replace(/Synthetic fixture only;\s*no production/gi, 'No production')
    .replace(/Synthetic UI fixture\.[ \t]*/gi, '')
    .replace(/Synthetic demonstration\.[ \t]*/gi, '')
    .replace(/ in this mock(?=[.!?]|$)/gi, '')
    .replace(/backend fixture pipeline/gi, 'backend pipeline')
    .replace(/(^|\n)[ \t]*(?:Synthetic demo|Demo mode|Scripted assistant)[ \t]*[:·][ \t]*/gi, '$1');
}

/** Known presentation labels only. Code, quoted source text, links and business terms stay verbatim. */
export function cleanAssistantPresentation(value: string): string {
  const protectedParts = /```[\s\S]*?(?:```|(?![\s\S]))|~~~[\s\S]*?(?:~~~|(?![\s\S]))|`+[^`\n]*`+|\[[^\]\n]*\]\([^\n)]*\)|^[ \t]*>.*$|^(?: {4}|\t).*$|"(?:[^"\\]|\\.)*"|“[^”]*”/gm;
  let result = '', cursor = 0;
  for (const match of value.matchAll(protectedParts)) {
    result += cleanKnownCopy(value.slice(cursor, match.index)) + match[0];
    cursor = match.index + match[0].length;
  }
  return result + cleanKnownCopy(value.slice(cursor));
}

const ZERO = BigInt(0);
function exactCents(value: number): bigint | null {
  if (!Number.isFinite(value)) return null;
  const parts = String(value).match(/^(-?)(\d+)(?:\.(\d{1,2}))?$/);
  if (!parts) return null;
  const amount = BigInt(parts[2] + (parts[3] ?? '').padEnd(2, '0')) * (parts[1] ? -BigInt(1) : BigInt(1));
  if (amount > BigInt(Number.MAX_SAFE_INTEGER) || amount < -BigInt(Number.MAX_SAFE_INTEGER)) return null;
  return amount;
}
function amountString(cents: bigint): string {
  const digits = (cents < ZERO ? -cents : cents).toString().padStart(3, '0');
  return `${cents < ZERO ? '-' : ''}${digits.slice(0, -2)}.${digits.slice(-2)}`;
}
/** Format a typed exact amount without a floating-point round trip or compact notation. */
export function formatAssistantAmount(amount: string, unit: Unit): string {
  const match = amount.match(/^(-?)(\d+)(?:\.(\d{1,2}))?$/);
  if (!match) return 'Unavailable';
  const whole = match[2].replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  const fraction = unit === 'tokens' ? (match[3] ?? '').replace(/0+$/, '') : (match[3] ?? '').padEnd(2, '0');
  const value = `${match[1] ? '−' : ''}${unit === 'usd' ? '$' : ''}${whole}${fraction ? `.${fraction}` : ''}`;
  return unit === 'usd' ? value : `${value} ${unit}`;
}
function periodLabel(period: AllocationProposal['period']): string | null {
  const values = [period.start, period.end].map(date => Date.parse(`${date}T00:00:00Z`));
  if (values.some((value, index) => !Number.isFinite(value) || new Date(value).toISOString().slice(0, 10) !== [period.start, period.end][index]) || values[0] > values[1]) return null;
  const fmt = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' });
  return `${fmt.format(values[0])} – ${fmt.format(values[1])} (UTC)`;
}
function allocationSummary(proposal: AllocationProposal, teams: Pick<Team, 'id' | 'name'>[], receipt?: Decision): AssistantAllocationSummary | undefined {
  const label = periodLabel(proposal.period);
  const source = receipt?.action === 'applied' ? receipt : proposal;
  if (!label || !['usd', 'credits', 'tokens'].includes(source.unit) || !source.lines.length || new Set(source.lines.map(l => l.teamId)).size !== source.lines.length) return undefined;
  const lines = source.lines.map(line => ({ ...line, beforeCents: exactCents(line.before), afterCents: exactCents(line.after) }));
  if (lines.some(line => line.beforeCents === null || line.afterCents === null || line.beforeCents < ZERO || line.afterCents < ZERO)) return undefined;
  const before = lines.reduce((sum, line) => sum + line.beforeCents!, ZERO), after = lines.reduce((sum, line) => sum + line.afterCents!, ZERO);
  if (source === proposal && (exactCents(proposal.totalBefore) !== before || exactCents(proposal.totalAfter) !== after)) return undefined;
  if (source.kind === 'redistribute' && before !== after || source.kind === 'add_budget' && (after < before || lines.some(line => line.afterCents! < line.beforeCents!))) return undefined;
  if (source === proposal && proposal.kind === 'add_budget' && proposal.addedAmount !== undefined && exactCents(proposal.addedAmount) !== after - before) return undefined;
  return { unit: source.unit, period: { start: proposal.period.start, end: proposal.period.end, label }, before: amountString(before), after: amountString(after), delta: amountString(after - before),
    lines: lines.map(line => ({ teamId: line.teamId, teamName: teams.find(team => team.id === line.teamId)?.name ?? line.teamId, before: amountString(line.beforeCents!), after: amountString(line.afterCents!), delta: amountString(line.afterCents! - line.beforeCents!) })) };
}

const CLARIFICATIONS: Record<NonNullable<ConversationContext['pending_slot']>, string> = {
  amount: 'Funding amount needed', team: 'Choose a team', change: 'Describe the change', proposal: 'Choose a proposal', effective_date: 'Choose an effective date',
};
const PROPOSAL_STATES: Record<AllocationProposal['status'], Pick<AssistantAnswerModel, 'headline' | 'status' | 'statusTone' | 'summary'>> = {
  proposed: { headline: 'Budget change ready for review', status: 'Review needed', statusTone: 'neutral', summary: 'Review the allocation details before applying the proposal.' },
  pending: { headline: 'Saving budget decision', status: 'Saving', statusTone: 'neutral', summary: 'Waiting for confirmation.' },
  applied: { headline: 'Budget change applied', status: 'Applied', statusTone: 'success', summary: 'The confirmed decision is saved.' },
  rejected: { headline: 'Proposal rejected', status: 'Rejected', statusTone: 'neutral', summary: 'The rejection is recorded.' },
  stale: { headline: 'Proposal needs updating', status: 'Outdated', statusTone: 'warning', summary: 'Review a refreshed proposal before applying a change.' },
  revised: { headline: 'Proposal replaced', status: 'Revised', statusTone: 'neutral', summary: 'This proposal has a newer revision.' },
  failed: { headline: 'Proposal needs attention', status: 'Unavailable', statusTone: 'danger', summary: null },
};

/** Financial facts come only from typed matching objects. Message prose remains a complete explanation. */
export function buildAssistantAnswer({ message, proposal: candidate, proposalAction, teams = [] }: {
  message: AssistantMessage;
  proposal?: AllocationProposal;
  proposalAction?: ProposalActionState;
  teams?: Pick<Team, 'id' | 'name'>[];
}): AssistantAnswerModel {
  const body = cleanAssistantPresentation(message.content);
  const intent = message.conversationContext?.intent;
  const base: AssistantAnswerModel = { kind: 'answer', headline: intent === 'explain' ? 'Spending analysis' : intent === 'scenario' ? 'Scenario analysis' : intent === 'allocation' ? 'Budget planning' : 'Answer', status: 'Response', statusTone: 'neutral', summary: null, body,
    bodyMode: body.length <= 320 && !/\n\s*\n/.test(body) ? 'inline' : 'details', detailsLabel: 'Explanation' };
  const reference = message.proposalId ?? (message.actionDraft?.kind === 'allocation' ? message.actionDraft.proposalId : undefined);
  const proposal = candidate?.id === reference ? candidate : undefined;
  const action = reference && (!proposalAction?.receipt || proposalAction.receipt.proposalId === reference) ? proposalAction : undefined;
  const receipt = action?.receipt;
  const allocation = proposal ? allocationSummary(proposal, teams, receipt) : undefined;
  const proposalBase: AssistantAnswerModel = { ...base, kind: 'proposal', bodyMode: 'details', proposalId: reference, ...(allocation ? { allocation } : {}) };
  const notice = proposal && !allocation ? 'Exact allocation amounts or dates need verification before review.' : undefined;

  if (action?.mutation === 'unknown' && !receipt) return { ...proposalBase, headline: 'Check the decision status', status: 'Confirmation needed', statusTone: 'warning', summary: 'This request may have been recorded.', notice: 'Check status before submitting another decision.' };
  if (action?.mutation === 'pending' && !receipt) return { ...proposalBase, headline: action.action === 'reject' ? 'Recording rejection' : 'Saving budget decision', status: 'Saving', statusTone: 'neutral', summary: 'Waiting for confirmation.', ...(notice ? { notice } : {}) };
  if (action && (receipt || action.mutation === 'confirmed')) {
    const state = receipt?.action ?? (action.action === 'apply' ? 'applied' : 'rejected');
    const syncNotice = action.sync === 'failed' ? `Decision saved. ${cleanAssistantPresentation(action.syncError ?? 'The latest totals could not be refreshed.')}` : action.sync === 'pending' ? 'Decision saved. Refreshing the latest totals…' : notice;
    return { ...proposalBase, ...PROPOSAL_STATES[state], ...(syncNotice ? { notice: syncNotice } : {}) };
  }
  if (action?.mutation === 'failed') return { ...proposalBase, headline: 'Decision needs attention', status: 'Request failed', statusTone: 'danger', summary: null, notice: cleanAssistantPresentation(action.error ?? 'The request could not be completed.') };

  // Terminal authoritative proposal status supersedes an older message's clarification context.
  if (proposal && !['proposed', 'pending'].includes(proposal.status)) return { ...proposalBase, ...PROPOSAL_STATES[proposal.status], ...(proposal.failureReason ? { notice: cleanAssistantPresentation(proposal.failureReason) } : notice ? { notice } : {}) };
  const slot = message.conversationContext?.pending_slot;
  if (slot && slot in CLARIFICATIONS) return { ...base, kind: 'clarification', headline: CLARIFICATIONS[slot], status: 'Input needed', statusTone: 'neutral', bodyMode: 'inline', clarification: { slot, label: CLARIFICATIONS[slot] } };
  if (proposal) {
    const model = { ...proposalBase, ...PROPOSAL_STATES[proposal.status], ...(notice ? { notice } : {}) };
    return notice && proposal.status === 'proposed' ? { ...model, headline: 'Budget change needs verification', status: 'Verification needed', statusTone: 'warning' } : model;
  }
  if (message.actionDraft?.kind === 'scenario') return { ...base, kind: 'scenario', headline: 'Scenario ready to preview', status: 'What-if draft', statusTone: 'neutral', summary: 'Preview the proposed assumptions before changing a plan.', bodyMode: 'details' };
  if (message.actionDraft?.kind === 'allocation') return { ...base, kind: 'allocation_draft', headline: 'Budget transfer draft', status: 'Draft', statusTone: 'neutral', summary: 'Review the transfer details before preparing a proposal.', bodyMode: 'details', ...(reference ? { proposalId: reference } : {}) };
  if (reference) return { ...proposalBase, headline: 'Proposal details unavailable', status: 'Details unavailable', statusTone: 'warning', summary: 'Retrieve the proposal to review its current details.' };
  if (base.bodyMode === 'details') {
    const blocks = body.split(/\n\s*\n/);
    // The transport's intent label is metadata; keep it in body, not the answer preview.
    if (blocks.length > 1 && /^\*\*Read as:\*\*[^\n]*$/.test(blocks[0].trim())) blocks.shift();
    const opening: string[] = [];
    for (const block of blocks) {
      opening.push(block);
      if (!/^#{1,6}[^\n]*$/.test(block.trim())) break;
    }
    return { ...base, preview: opening.join('\n\n') };
  }
  return base;
}
