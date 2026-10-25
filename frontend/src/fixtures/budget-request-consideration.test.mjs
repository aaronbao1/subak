import test from 'node:test';
import assert from 'node:assert/strict';
import { tsModuleUrl } from '../../tests/load-ts-module.mjs';
const generated = await import(tsModuleUrl(new URL('./generate.ts', import.meta.url)));
const fixture = await import(tsModuleUrl(new URL('./index.ts', import.meta.url)));
const endExclusive = generated.addDays(fixture.period.end, 1);
const request = (id, patch = {}) => ({
  id, clientRequestId: id, teamId: 'research', title: `Capacity ${id}`, requestKind: 'project', projectName: 'Atlas',
  narrative: `Original source narrative ${id}`, requestedAmount: '9000.00', unit: 'USD',
  periodStart: fixture.period.start, periodEndExclusive: endExclusive, sourceRef: `email:${id}`,
  evidenceRefs: [], period: { id: 'weekly', startDate: fixture.period.start, endDateExclusive: endExclusive, label: fixture.period.label },
  source: { reference: `email:${id}`, submittedBy: 'Team lead', submittedAt: `${fixture.period.start}T10:00:00Z` },
  status: 'submitted', linkedProposalIds: [], decisionIds: [], approvedAmount: '0.00', remainingRequestedAmount: '9000.00',
  assessment: { assessedAt: `${fixture.period.start}T10:00:00Z`, budgetVersion: 1, envelopeTotal: '200000.00', teamAllocation: '60000.00', recordedSpend: '45000.00', forecastAmount: '85000.00', forecastRunId: 'issued-original', forecastStatus: 'available', forecastUnit: 'USD', forecastBasis: 'full_period_total', projectedHeadroom: '-25000.00', requestedAllocation: '69000.00', availableDonors: [], qualification: 'Request excluded from forecast.', amountIncludedInForecast: false },
  ...patch,
});
const state = {proposals: [], budgets: fixture.budgets, budgetVersion: 'v1'};
const replies = [['Northstar', fixture.scriptedReply], ['generated', generated.makeGenericReply(fixture.teams, fixture.forecasts, fixture.context, fixture.people)]];
for (const [name, reply] of replies) {
  test(`${name}: two same-team requests remain separate considerations without changing a $50 proposal`, () => {
    const requests = [request('one'), request('two', {status:'partially_funded', requestedAmount:'10000.00', remainingRequestedAmount:'3000.00', approvedAmount:'7000.00'})];
    const before = JSON.stringify({state, requests, forecasts: fixture.forecasts});
    const output = reply('Add $50 for Research', {...state, budgetRequests: requests});
    assert.equal(output.proposal.addedAmount, 50);
    assert.equal(output.proposal.totalAfter - output.proposal.totalBefore, 50);
    assert.equal(output.proposal.lines.find(line => line.teamId === 'research').after - output.proposal.lines.find(line => line.teamId === 'research').before, 50);
    for (const id of ['one','two']) {
      assert.ok(output.message.content.includes(`/requests?request=${id}`));
      assert.ok(output.message.content.includes(`email:${id}`));
      assert.ok(output.proposal.rationale.includes(`Capacity ${id}`));
    }
    assert.match(output.message.content, /3,000(?:\.00)? remaining/);
    assert.ok(output.message.content.includes(fixture.period.start));
    assert.ok(output.message.content.includes(endExclusive));
    assert.ok(output.message.content.includes('submitted'));
    assert.ok(output.message.content.includes('partially funded'));
    assert.equal(output.message.toolCalls.filter(call => call.name === 'list_budget_requests').length, 1);
    assert.match(output.message.toolCalls.find(call => call.name === 'list_budget_requests').summary, /2 current/);
    assert.equal(output.proposal.requestIds, undefined);
    assert.equal(JSON.stringify({state, requests, forecasts: fixture.forecasts}), before);
  });
  test(`${name}: closed wrong-period and repeated request records are excluded while factual replies consider current updates`, () => {
    const active = request('active', {status:'needs_revision',requestedAmount:null,remainingRequestedAmount:null});
    const requests = [active, active, request('closed',{status:'rejected'}), request('funded',{status:'approved_applied'}), request('past',{periodStart:'2020-01-01'}), request('wrong-end',{periodEndExclusive:'2030-01-01'})];
    const output = reply('Why is Research over budget?', {...state,budgetRequests:requests});
    assert.equal(output.proposal,undefined);
    assert.equal(output.message.content.split('/requests?request=active').length-1,1);
    for (const id of ['closed','funded','past','wrong-end']) assert.ok(!output.message.content.includes(`/requests?request=${id}`));
    assert.match(output.message.content,/amount needs clarification/i);
    assert.match(output.message.toolCalls.find(call=>call.name==='list_budget_requests')?.summary ?? '',/1 current/);
  });
  test(`${name}: request context is read afresh for each reply and canonical actions avoid duplicate consideration`,()=>{
    const requests=[request('dynamic',{status:'pending_review'})];
    const first=reply('Add $50k',{...state,budgetRequests:requests});
    assert.equal(first.proposal.addedAmount,50000);
    assert.equal(first.message.content.split('/requests?request=dynamic').length-1,1);
    requests[0].status='approved_applied';
    const next=reply('Compare teams',{...state,budgetRequests:requests});
    assert.ok(!next.message.content.includes('/requests?request=dynamic'));
    assert.match(next.message.toolCalls.find(call=>call.name==='list_budget_requests')?.summary ?? '',/0 current/);
  });
}
