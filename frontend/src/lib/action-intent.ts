/** Pure interpretation boundary: only validated actions may create mock proposals. */
export interface ActionIntentContext {
  intent?: 'explain' | 'scenario' | 'allocation';
  selected_proposal_id?: string;
  selected_proposal_version?: number;
  effective_date_text?: string;
  pending_slot?: 'amount' | 'team' | 'change' | 'proposal' | 'effective_date';
  draft?: { mode: 'addition' | 'transfer'; amount?: string; prioritize?: string; source_team?: string };
  scope_type?: 'company' | 'team' | 'person';
  scope_id?: string;
  period?: string;
  forecast_run_id?: string;
}
interface IntentTeam { id: string; name: string }
interface IntentProposal {
  id: string; kind: 'add_budget' | 'redistribute'; status: string; version?: number;
  addedAmount?: number;
  lines: { teamId: string; before: number; after: number }[];
}
export interface ActionInterpretation {
  action: 'addition' | 'transfer' | 'explain' | 'clarify' | 'none';
  readOnly: boolean;
  amount?: string;
  targetTeamId?: string;
  sourceTeamId?: string;
  reviseProposalId?: string;
  ask?: string;
  context: ActionIntentContext;
}
const escape = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/** Decimal arithmetic keeps $50 as fifty dollars and never rounds a user's request. */
function exactAmount(text: string): { amount?: string; invalid?: boolean } {
  const matches = [...text.matchAll(/(?:[-−]\s*)?\$?\s*[-−]?\d[\d,.]*\s*(?:million|thousand|mm|m|k)?\b/gi)];
  if (!matches.length) return {};
  if (matches.length !== 1) return { invalid: true };
  const match = matches[0][0].trim();
  if (/[-−]/.test(match)) return { invalid: true };
  const parsed = match.match(/^\$?\s*(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?\s*(million|thousand|mm|m|k)?$/i);
  if (!parsed) return { invalid: true };
  const fraction = parsed[2] ?? '';
  const power = /^(m|mm|million)$/i.test(parsed[3] ?? '') ? 6 : parsed[3] ? 3 : 0;
  let digits = BigInt(parsed[1].replace(/,/g, '') + fraction);
  const decimalPlaces = fraction.length - power;
  if (decimalPlaces > 2) {
    const divisor = BigInt(10) ** BigInt(decimalPlaces - 2);
    if (digits % divisor !== BigInt(0)) return { invalid: true };
    digits /= divisor;
  } else {
    digits *= BigInt(10) ** BigInt(2 - decimalPlaces);
  }
  if (digits <= BigInt(0) || digits > BigInt(Number.MAX_SAFE_INTEGER)) return { invalid: true };
  const cents = (digits % BigInt(100)).toString().padStart(2, '0').replace(/0+$/, '');
  return { amount: (digits / BigInt(100)).toString() + (cents ? `.${cents}` : '') };
}

export function interpretActionIntent(
  content: string,
  teams: IntentTeam[],
  options: { context?: ActionIntentContext; proposals?: IntentProposal[]; planningPeriod?: { start: string; end: string } } = {},
): ActionInterpretation {
  let text = content.trim().replace(/’/g, "'");
  const context: ActionIntentContext = { ...options.context, draft: options.context?.draft ? { ...options.context.draft } : undefined };
  const result = (action: ActionInterpretation['action'], extra: Partial<ActionInterpretation> = {}): ActionInterpretation => ({ action, readOnly: action !== 'addition' && action !== 'transfer', context, ...extra });
  const ask = (slot: ActionIntentContext['pending_slot'], question: string) => {
    context.pending_slot = slot;
    return result('clarify', { ask: question });
  };
  if (/\?|^(?:why|how|what|when|where|which|who|can|could|would|should|did|does|is|are)\b|^explain\b/i.test(text)) {
    context.intent = 'explain'; delete context.pending_slot;
    return result('explain');
  }
  const requestedPeriod = text.match(/\bfor\s+(\d{4}-\d{2}-\d{2})\s+(?:through|to)\s+(\d{4}-\d{2}-\d{2})\b/i);
  if (requestedPeriod) {
    if (!options.planningPeriod || requestedPeriod[1] !== options.planningPeriod.start || requestedPeriod[2] !== options.planningPeriod.end) return ask('change', 'Choose the current allocation period before preparing this change.');
    text = text.replace(requestedPeriod[0], '');
  }
  if ((context.pending_slot === 'effective_date' && !requestedPeriod) || /\b(?:effective date|start date|end date|tomorrow|next week|january|february|march|april|may|june|july|august|september|october|november|december)\b|\b\d{4}-\d{2}-\d{2}\b|\b(?:\d+|one|two|three|four) (?:days?|weeks?) (?:later|earlier)\b/i.test(text)) {
    context.intent = 'scenario';
    context.effective_date_text = content.trim();
    return ask('effective_date', 'Review the proposed effective date in the scenario preview; a date does not change the budget amount.');
  }
  if (context.intent === 'scenario') return result('explain', { ask: 'Preview this assumption as a scenario before preparing any budget change.' });

  const clauses = text.split(/;|\bbut\b/i);
  const addition = clauses.some((clause) => /\b(?:add|allocate|authorize|increase)\b|\b(?:additional|new|more)\s+(?:funding|budget|credits)\b/i.test(clause) && !/\b(?:not|never|without|don't|no)\b/i.test(clause));
  const transfer = clauses.some((clause) => /\b(?:redistribut\w*|rebalanc\w*|move|shift|transfer|reallocat\w*)\b/i.test(clause) && !/\b(?:not|never|don't)\s+(?:\w+\s+){0,2}(?:redistribut\w*|rebalanc\w*|move|shift|transfer|reallocat\w*)\b/i.test(clause));
  if (!addition && !transfer && /\b(?:not|never|don't|without)\b.*\b(?:add|adding|funding)\b|\bno new funding\b/i.test(text)) {
    delete context.pending_slot; delete context.draft;
    return result('explain', { ask: 'No new funding will be proposed. Ask to redistribute the existing budget if you want a transfer.' });
  }
  if (!addition && !transfer && /\b(?:not|never|don't|without|no|ignore|cancel)\b/i.test(text)) {
    delete context.pending_slot; delete context.draft;
    return result('explain', { ask: 'No budget change has been proposed.' });
  }
  if (addition && transfer) return ask('change', 'Should this add new funding or move the existing budget?');
  if (/[€£¥₹%]|\b(?:credits?|tokens?|gpu[- ]?hours?|hours?|hrs?|seats?|requests?|calls?|eur|euros?|gbp|pounds?|jpy|yen|cad|aud)\b/i.test(text) && /\d/.test(text)) return ask('amount', 'Enter the amount in US dollars; other units are not interchangeable with dollars.');
  const amountText = teams.reduce((value, team) => value.replace(new RegExp(`\\b${escape(team.name)}\\b`, 'gi'), ''), text);
  const money = exactAmount(amountText);
  const revision = /\b(?:revis\w*|instead|change|make it|rather)\b/i.test(text);
  if (context.intent === 'explain' && !addition && !transfer && !revision) return result('explain');
  const amountAnswer = /^(?:use\s+)?\$?\s*[-−]?\d[\d,.]*\s*(?:million|thousand|mm|m|k)?\s*(?:dollars?|usd)?(?:\s+please)?[.!]?$/i.test(text);
  const teamAnswer = context.pending_slot === 'team' && teams.some((team) => new RegExp(`^(?:(?:to|from|for)\\s+)?(?:${escape(team.name)}|${escape(team.id)})[.!]?$`, 'i').test(text));
  const continuing = !addition && !transfer && (revision || amountAnswer || teamAnswer);
  let selected: IntentProposal | undefined;
  const open = (options.proposals ?? []).filter((proposal) => proposal.status === 'proposed');
  if (context.selected_proposal_id && (continuing || addition || transfer)) {
    selected = open.find((proposal) => proposal.id === context.selected_proposal_id);
    if (!selected) {
      if (revision || ['amount', 'team', 'change'].includes(context.pending_slot ?? '') || (!addition && !transfer)) return ask('proposal', 'Select an open proposal to revise.');
      // A fresh explicit action must not inherit the closed proposal's selection or slots.
      delete context.selected_proposal_id;
      delete context.selected_proposal_version;
      delete context.draft;
      delete context.pending_slot;
    }
    if (selected && context.selected_proposal_version !== undefined && selected.version !== undefined && context.selected_proposal_version !== selected.version) return ask('proposal', 'That proposal has changed. Select its current version before revising it.');
  } else if (continuing && !context.draft && open.length) {
    if (open.length > 1) return ask('proposal', 'Select the proposal you want to revise.');
    selected = open[0];
  }
  let draft = continuing ? context.draft : undefined;
  if (selected && !draft) {
    const recipients = selected.lines.filter((line) => line.after > line.before);
    const donors = selected.lines.filter((line) => line.after < line.before);
    draft = {
      mode: selected.kind === 'add_budget' ? 'addition' : 'transfer',
      amount: selected.addedAmount === undefined ? undefined : String(selected.addedAmount),
      prioritize: recipients.length === 1 ? recipients[0].teamId : undefined,
      source_team: donors.length === 1 ? donors[0].teamId : undefined,
    };
  }
  const mode = transfer ? 'transfer' : addition ? 'addition' : draft?.mode;
  const named = (value?: string) => teams.find((team) => [team.id.toLowerCase(), team.name.toLowerCase()].includes(value?.toLowerCase() ?? ''));
  const mentioned = teams.filter((team) => new RegExp(`\\b(?:${escape(team.name)}|${escape(team.id)})\\b`, 'i').test(text));
  const explicitSource = teams.find((team) => new RegExp(`\\b(?:from|out of)\\s+(?:the\\s+)?(?:${escape(team.name)}|${escape(team.id)})\\b`, 'i').test(text));
  const source = explicitSource ?? named(draft?.source_team);
  const explicitTarget = teams.find((team) => new RegExp(`\\b(?:to|into|for|prioritiz(?:e|ing))\\s+(?:the\\s+)?(?:${escape(team.name)}|${escape(team.id)})\\b`, 'i').test(text));
  const target = explicitTarget ?? (context.pending_slot === 'team' && mentioned.length === 1 && mentioned[0].id !== source?.id ? mentioned[0] : named(draft?.prioritize));
  if (!mode) {
    if (money.amount || money.invalid || revision) return ask('change', 'Should this add new funding or transfer the existing budget?');
    return result('none');
  }
  context.intent = 'allocation';
  context.draft = { mode, amount: money.amount ?? draft?.amount, prioritize: target?.id, source_team: source?.id };
  if (money.invalid) return ask('amount', 'Enter one positive dollar amount, with at most two decimal places.');
  const amount = context.draft.amount;
  if (amount && exactAmount(amount).amount !== amount) return ask('amount', 'Enter one positive dollar amount, with at most two decimal places.');
  if (mentioned.filter((team) => team.id !== source?.id).length > 1) return ask('team', 'Choose one destination team for this change.');
  if (/\b(?:from|out of)\s+/i.test(text) && !explicitSource || /\b(?:to|into|for)\s+[a-z]/i.test(text) && !explicitTarget && /\b(?:to|into|for)\s+(?!the\s+(?:existing|current|entire|whole)\b)/i.test(text)) return ask('team', 'Choose a known team for this change.');
  if (source && target && source.id === target.id) return ask('team', 'Choose different source and destination teams.');
  if (mode === 'addition' && !amount || mode === 'transfer' && (source || target) && !amount) return ask('amount', 'What dollar amount should this change use?');
  if (mode === 'transfer' && amount && (!source || !target)) return ask('team', source ? 'Which team should receive the transfer?' : 'Which team should fund the transfer?');
  delete context.pending_slot;
  if (selected) {
    context.selected_proposal_id = selected.id;
    context.selected_proposal_version = selected.version;
  }
  return result(mode, { amount, targetTeamId: target?.id, sourceTeamId: source?.id, reviseProposalId: selected?.id });
}
