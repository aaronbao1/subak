import type { Dataset, ScriptedReplyFn } from '@/fixtures/generate';
import { makeGenericReply, withBudgetRequestConsideration } from '@/fixtures/generate';
import type { ForecastBundle, ForecastView } from '@/lib/contracts';
import { interpretActionIntent } from '@/lib/action-intent';
import { selectScopeSummary, sumMoney } from '@/lib/finance-summary';

type Snapshot = Omit<Dataset, 'scriptedReply'>;
type SnapshotReplyOptions = { envelopeTotal?: number };
const money = (value: number) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 }).format(value).replace(/\.00$/, '');
const escape = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/** A shorthand is usable only when its whole word identifies exactly one saved team. */
function resolveTeamAliases(content: string, teams: Snapshot['teams']): string {
  const aliases = new Map<string, Set<string>>();
  for (const team of teams) for (const word of `${team.name} ${team.id}`.toLowerCase().split(/[^a-z0-9]+/).filter(word => word.length >= 4)) {
    const ids = aliases.get(word) ?? new Set<string>(); ids.add(team.id); aliases.set(word, ids);
  }
  return content.replace(/\b[a-z][a-z0-9]{3,}\b/gi, word => {
    const ids = aliases.get(word.toLowerCase());
    if (ids?.size !== 1) return word;
    const team = teams.find(team => ids.has(team.id))!;
    if (new RegExp(`\\b${escape(team.name)}\\b`, 'i').test(content)) return word;
    return team.name;
  });
}

/** Explain immutable saved receipts; allocation drafts use the existing session-local workflow. */
export function makeSnapshotReply(dataset: Snapshot, bundle: ForecastBundle, options: SnapshotReplyOptions = {}): ScriptedReplyFn {
  const period = dataset.company.currentPeriod;
  const periodName = period.label || `${period.start} to ${period.end}`;
  const forecasts = dataset.forecasts.filter(f => f.period.start === period.start && f.period.end === period.end);
  const actions = makeGenericReply(dataset.teams, forecasts, dataset.context, dataset.people, period);
  const initialAllocated = sumMoney(dataset.budgets.filter(b => b.period.start === period.start && b.period.end === period.end && b.unit === 'usd').map(b => b.allocated));
  const viewFor = (type: 'company' | 'team', id: string): ForecastView | undefined => bundle.views.find(v => v.scope.type === type && v.scope.id === id);
  return withBudgetRequestConsideration((content, state, conversationContext, forecastContext) => {
    if (forecastContext && !bundle.views.some(view => view.run_id === forecastContext.run_id
      && view.scope.type === forecastContext.scope_type && view.scope.id === forecastContext.scope_id)) return { message: {
      content: 'The selected forecast is not available in this saved snapshot. Open a current forecast to review its figures and assumptions.',
      conversationContext: { intent: 'explain' },
    } };
    const resolvedContent = resolveTeamAliases(content, dataset.teams);
    if (/\b(?:refresh|recalculate|recompute|rerun|publish)\b.*\bforecasts?\b|\bforecasts?\b.*\b(?:refresh|recalculation|rerun)\b/i.test(content)) return { message: {
      content: 'This session uses the saved forecast. It cannot recalculate or publish a new forecast; you can review the saved figures and prepare allocation changes separately.',
      conversationContext: { intent: 'explain' },
    } };
    if (forecastContext && /\bcompare\b/i.test(content) && dataset.teams.some(team => team.id !== forecastContext.scope_id
      && new RegExp(`\\b${escape(team.name)}\\b`, 'i').test(resolvedContent))) return { message: {
      content: 'This conversation is pinned to one selected forecast. Clear that selection to compare other teams using the saved figures.',
      conversationContext: { intent: 'explain' },
    } };
    const intent = interpretActionIntent(resolvedContent, dataset.teams, { context: conversationContext, proposals: state.proposals, planningPeriod: period });
    if (forecastContext && (intent.action === 'addition' || intent.action === 'transfer' || intent.context.intent === 'allocation')) return { message: {
      content: 'This conversation is pinned to the selected forecast. Clear that context or choose Adjust budgets before preparing an allocation change.',
      conversationContext: { intent: 'explain' },
    } };
    if (intent.context.intent === 'scenario') return { message: {
      content: 'Select a forecast assumption and adjust its date in the scenario preview. You can review the proposed timing in this session; the saved forecast and allocations stay unchanged.',
      conversationContext: intent.context,
      toolCalls: [{ name: 'review_scenario_assumptions', summary: 'Reviewed the saved forecast assumptions; no forecast was recalculated.' }],
    } };
    if (intent.action === 'addition' || intent.action === 'transfer' || intent.action === 'clarify' || intent.ask) {
      if (intent.action === 'transfer' && intent.sourceTeamId && intent.amount) {
        const source = dataset.teams.find(team => team.id === intent.sourceTeamId)!;
        const sourceSummary = selectScopeSummary({ scope: { type: 'team', id: source.id }, period,
          unit: dataset.company.budgetUnit, datasetId: dataset.company.id, spending: dataset.spending,
          budgets: state.budgets, forecastView: viewFor('team', source.id) });
        const headroom = sourceSummary.issued.amount === null || sourceSummary.allocation === null ? null
          : Math.max(0, sumMoney([sourceSummary.allocation, -Math.max(sourceSummary.issued.amount, sourceSummary.observed.amount ?? 0)]));
        if (headroom === null || Number(intent.amount) > headroom) return { message: {
          content: headroom === null ? `${source.name} has no matching saved forecast and allocation to establish available headroom. No transfer was drafted.`
            : `${source.name} has ${money(headroom)} available above its saved forecast and recorded spend. Choose a transfer within that headroom.`,
          conversationContext: { ...intent.context, pending_slot: 'amount' },
        } };
      }
      const result = actions(resolvedContent, state, conversationContext);
      if (result.proposal) result.message.content += '\n\nReview this draft before applying it in this session. It has not been applied.';
      return result;
    }

    const named = forecastContext
      ? forecastContext.scope_type === 'team' ? dataset.teams.find(team => team.id === forecastContext.scope_id) : undefined
      : dataset.teams.find(team => new RegExp(`\\b${escape(team.name)}\\b`, 'i').test(resolvedContent));
    const scope = named ? { type: 'team' as const, id: named.id } : forecastContext ? { type: forecastContext.scope_type, id: forecastContext.scope_id }
      : { type: 'company' as const, id: dataset.company.id };
    const view = bundle.views.find(v => v.scope.type === scope.type && v.scope.id === scope.id && (!forecastContext || v.run_id === forecastContext.run_id));
    const summary = selectScopeSummary({ scope, period, unit: dataset.company.budgetUnit, datasetId: dataset.company.id,
      spending: dataset.spending, budgets: state.budgets, forecastView: view });
    const subject = `**${named?.name ?? (scope.type === 'person' ? dataset.people.find(person => person.id === scope.id)?.name : undefined)
      ?? (scope.type === 'company' ? dataset.company.name : view?.scope.name ?? 'Selected scope')}**`;
    const recorded = summary.observed.amount === null ? 'has no recorded spending available' : `has **${money(summary.observed.amount)}** recorded spend`;
    const outlook = summary.issued.amount === null ? `No matching ${scope.type} forecast is available.` : `The saved full-period forecast is **${money(summary.issued.amount)}**.`;
    const coverage = summary.observed.complete ? 'Based on available spending records.' : 'Recorded spend includes incomplete coverage.';
    const first = `${subject} ${recorded} for **${periodName}**. ${outlook} ${coverage}`;
    const lines = [first];
    if (summary.allocation !== null) {
      const envelope = options.envelopeTotal === undefined ? null : sumMoney([options.envelopeTotal, summary.allocation, -initialAllocated]);
      lines.push(named ? `Current allocation: **${money(summary.allocation)}**.${summary.variance === null ? '' : ` The forecast is ${money(Math.abs(summary.variance))} ${summary.variance > 0 ? 'above' : 'below'} allocation.`}`
        : `Current team allocations total **${money(summary.allocation)}**.${envelope === null ? '' : ` Company envelope: **${money(envelope)}**.`}`);
    }
    if (scope.type === 'company') {
      const teams = dataset.teams.map(team => ({ team, summary: selectScopeSummary({ scope: { type: 'team', id: team.id }, period,
        unit: dataset.company.budgetUnit, datasetId: dataset.company.id, spending: dataset.spending, budgets: state.budgets, forecastView: viewFor('team', team.id) }) }))
        .sort((a, b) => (b.summary.issued.amount ?? -1) - (a.summary.issued.amount ?? -1)).slice(0, 5);
      lines.push(teams.map(({ team, summary: s }) => `- **${team.name}:** recorded ${s.observed.amount === null ? 'unavailable' : money(s.observed.amount)}; forecast ${s.issued.amount === null ? 'unavailable' : money(s.issued.amount)}; allocation ${s.allocation === null ? 'unavailable' : money(s.allocation)}.`).join('\n'));
    }
    const context = dataset.context.filter(item => !item.supersededBy && (scope.type === 'company' || item.scope === 'company'
      || scope.type === 'team' && item.teamIds.includes(scope.id ?? '')
      || scope.type === 'person' && item.personIds?.includes(scope.id ?? ''))).slice(0, 3);
    if (context.length) lines.push(`Saved source context:\n${context.map(item => `- ${item.summary}`).join('\n')}`);
    if (/\bchang(?:e|ed|es)|previous|prior|last (?:week|month)|outlook/i.test(content)) lines.push('A prior comparable forecast is not included in this conversation, so I cannot quantify a change from the previous outlook. Source context is not a measured forecast effect.');
    if (/request|funding/i.test(content)) lines.push('Review the current requests below. To prepare a change, name the amount and team, or the source and destination for a transfer. A request is not an approval.');
    lines.push('Allocation changes are kept in this browser session and do not alter the saved forecast.');
    return { message: {
      content: lines.filter(Boolean).join('\n\n'), conversationContext: intent.context,
      citations: context.flatMap(item => item.sources),
      toolCalls: [
        { name: 'get_spend_summary', summary: 'Read the saved spending records for the selected period.' },
        { name: 'get_forecast', summary: 'Read the saved issued forecast for the same scope and period.' },
        { name: 'get_budgets', summary: 'Read the current browser-session allocations.' },
        ...(context.length ? [{ name: 'read_saved_sources', summary: `Reviewed ${context.length} saved source summaries.` }] : []),
      ],
    } };
  }, dataset.teams, period);
}
