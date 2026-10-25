import type { Dataset } from '@/fixtures';
import { DEMO_NOW } from '@/fixtures/generate';
import type { ForecastBundle, ForecastScope, ForecastView, SpendingRecord } from '@/lib/contracts';
import type { WeeklyActual, WeeklyHistoryQuery, WeeklyHistoryResponse, WeeklyHistoryWeek, WeeklyIssuedForecast, WeeklyOutlook } from '@/lib/contracts/weekly-history';
import { billableAmount } from '@/lib/finance-summary';
import { sumUsageMoney } from '@/lib/usage-derive';
import { validateWeeklyHistoryQuery } from './weekly-history';

const DAY = 86_400_000;
const offset = (date: string, days: number) => new Date(Date.parse(`${date}T00:00:00Z`) + days * DAY).toISOString().slice(0, 10);
const datesBetween = (start: string, end: string) => Array.from({ length: Math.round((Date.parse(end) - Date.parse(start)) / DAY) }, (_, index) => offset(start, index));
const midnight = (date: string) => `${date}T00:00:00Z`;
const scopeKey = (scope: ForecastScope) => `${scope.type}:${scope.id ?? ''}`;
const partitionKey = (row: SpendingRecord) => JSON.stringify([row.teamId ?? null, row.personId ?? null]);
const streamKey = (row: SpendingRecord) => JSON.stringify([partitionKey(row), row.component, row.provider, row.model ?? null]);

/** Expand the number contract's decimal representation before exact addition. */
function decimal(value: number): string {
  if (!Number.isFinite(value)) throw new Error('Synthetic weekly amounts must be finite.');
  const [coefficient, power] = String(value).toLowerCase().split('e');
  if (power === undefined) return coefficient;
  const negative = coefficient.startsWith('-');
  const unsigned = coefficient.replace(/^-/, '');
  const [whole, fraction = ''] = unsigned.split('.');
  const digits = whole + fraction;
  const point = whole.length + Number(power);
  const expanded = point <= 0 ? `0.${'0'.repeat(-point)}${digits}` : point >= digits.length ? digits + '0'.repeat(point - digits.length) : `${digits.slice(0, point)}.${digits.slice(point)}`;
  return `${negative ? '-' : ''}${expanded}`;
}
const amountOf = (rows: SpendingRecord[]) => sumUsageMoney(rows.map(row => decimal(billableAmount(row))));
const negate = (amount: string) => amount.startsWith('-') ? amount.slice(1) : `-${amount}`;

/** Four-week mean, rounded once per additive population partition to the nearest cent. */
function quarterToCents(amount: string): string {
  const negative = amount.startsWith('-');
  const [whole, fraction = ''] = amount.replace(/^-/, '').split('.');
  const numerator = BigInt(whole + fraction) * BigInt(100);
  const denominator = BigInt(4) * BigInt(10) ** BigInt(fraction.length);
  const cents = (numerator + denominator / BigInt(2)) / denominator;
  const digits = cents.toString().padStart(3, '0');
  return `${negative && cents !== BigInt(0) ? '-' : ''}${digits.slice(0, -2)}.${digits.slice(-2)}`;
}

function fingerprint(rows: SpendingRecord[]): string {
  const serialized = JSON.stringify([...rows].sort((a, b) => a.id.localeCompare(b.id)).map(row => [row.id, row.date, row.teamId, row.personId, row.unit, row.component, row.provider, row.model, row.provenance, row.amount, row.complete]));
  let hash = 2166136261;
  for (const char of serialized) hash = Math.imul(hash ^ char.charCodeAt(0), 16777619);
  return (hash >>> 0).toString(16);
}

function matches(row: SpendingRecord, scope: ForecastScope): boolean {
  if (scope.type === 'company') return true;
  if (scope.type === 'team') return row.teamId === scope.id;
  if (scope.type === 'person') return row.personId === scope.id;
  if (scope.id === 'people_unallocated') return !!row.teamId && !row.personId;
  if (scope.id === 'teams_unallocated') return !row.teamId && !!row.personId;
  return !row.teamId && !row.personId;
}

/** Require each stream known by this cutoff on every date; today's roster never affects past eligibility. */
function completeWindow(rows: SpendingRecord[], start: string, end: string, knownRows: SpendingRecord[] = rows): boolean {
  if (!rows.length || rows.some(row => !row.complete)) return false;
  const streams = new Set(knownRows.map(streamKey));
  return datesBetween(start, end).every(date => {
    const present = new Set(rows.filter(row => row.date === date).map(streamKey));
    return present.size > 0 && [...streams].every(key => present.has(key));
  });
}

function priorIssue(fx: Dataset, scope: ForecastScope, allRows: SpendingRecord[], start: string, end: string): WeeklyIssuedForecast | null {
  const trainingStart = offset(start, -28);
  // Filter before deduplication: a future row can never replace a pre-issue fixture observation.
  const rows = [...new Map(allRows.filter(row => row.date >= trainingStart && row.date < start).map(row => [row.id, row])).values()];
  if (!completeWindow(rows, trainingStart, start, allRows.filter(row => row.date < start))) return null;
  const partitions = new Map<string, SpendingRecord[]>();
  for (const row of rows) {
    const key = partitionKey(row);
    const values = partitions.get(key) ?? [];
    values.push(row);
    partitions.set(key, values);
  }
  const amount = sumUsageMoney([...partitions.values()].map(part => quarterToCents(amountOf(part)!)))!;
  const runId = `synthetic-weekly-v1:${fx.company.id}:${scopeKey(scope)}:${start}:${fingerprint(rows)}`;
  return { amount, runId, targetId: `${runId}:${start}:${end}`, datasetId: fx.company.id, issuedAt: midnight(start), informationCutoff: midnight(start), start, endExclusive: end };
}

function latestOutlook(view: ForecastView | undefined, datasetId: string, start: string, end: string, state: WeeklyHistoryWeek['state']): WeeklyOutlook | null {
  if (!view || state === 'closed' || view.dataset_id !== datasetId || view.target.unit.toLowerCase() !== 'usd' || view.target.basis !== 'planning' || view.target.quantity !== 'spend' || (view.target.timezone ?? view.timezone) !== 'UTC') return null;
  const issuedAt = view.publication?.generated_at;
  const informationCutoff = view.publication?.information_cutoff ?? view.information_cutoff;
  if (typeof issuedAt !== 'string' || typeof informationCutoff !== 'string' || !Number.isFinite(Date.parse(issuedAt)) || !Number.isFinite(Date.parse(informationCutoff)) || Date.parse(informationCutoff) > Date.parse(issuedAt) || Date.parse(issuedAt) > Date.parse(DEMO_NOW)) return null;
  const planning = view.planning_period_outlook as Record<string, unknown> | undefined;
  const full = state === 'current' && planning?.start === start && planning?.end === end && typeof planning.base === 'number' && planning.complete !== false ? planning : view.weekly?.find(point => point.start === start && point.end === end && !point.partial && point.complete !== false);
  const remainder = state === 'current' ? view.weekly?.find(point => point.partial && point.calendar_start === start && typeof point.start === 'string' && point.start >= start && point.end === end && point.complete !== false) : undefined;
  const point = full ?? remainder;
  if (!point || typeof point.base !== 'number' || !Number.isFinite(point.base) || typeof point.start !== 'string' || typeof point.end !== 'string') return null;
  return { amount: sumUsageMoney([decimal(point.base)])!, runId: view.run_id, datasetId, issuedAt, informationCutoff, start: point.start, endExclusive: point.end, partial: point.start !== start || point.end !== end || point.partial === true };
}

/**
 * Deterministic synthetic walk-forward illustration, independent of held-out weekly actuals.
 * This authors synthetic issue/outcome fixtures; it does not claim archived production forecasts.
 */
export function syntheticWeeklyHistory(fx: Dataset, query: WeeklyHistoryQuery, bundle: ForecastBundle): WeeklyHistoryResponse {
  validateWeeklyHistoryQuery(query);
  if (fx.company.budgetUnit !== 'usd') throw new Error('Weekly spending history requires a USD fixture.');
  const scope: ForecastScope = { type: query.scopeType, id: query.scopeId ?? fx.company.id };
  const today = DEMO_NOW.slice(0, 10);
  const companyMatches = scope.type !== 'company' || scope.id === fx.company.id;
  const scoped = companyMatches ? fx.spending.filter(row => row.unit === 'usd' && row.date <= today && matches(row, scope)) : [];
  const currentRows = [...new Map(scoped.map(row => [row.id, row])).values()];
  const view = bundle.views.find(item => item.scope.type === scope.type && (item.scope.id ?? '') === (scope.id ?? ''));
  const weeks = datesBetween(query.startDate, query.endDateExclusive).filter((_, index) => index % 7 === 0).map((start): WeeklyHistoryWeek => {
    const endExclusive = offset(start, 7);
    const state = endExclusive <= today ? 'closed' : start > today ? 'future' : 'current';
    const rows = currentRows.filter(row => row.date >= start && row.date < endExclusive);
    const complete = state === 'closed' && completeWindow(rows, start, endExclusive, currentRows.filter(row => row.date < endExclusive));
    const revision = rows.length ? `synthetic-outcome-v1:${fingerprint(rows)}` : null;
    const actual: WeeklyActual = state === 'future' ? { amount: null, status: 'future', source: 'none', datasetId: null, revision: null, corrected: false, sourceRefs: [] } : {
      amount: amountOf(rows), status: complete ? 'mature' : rows.length ? 'partial' : 'missing', source: complete ? 'observed_outcome' : rows.length ? 'repository_ledger' : 'none',
      datasetId: rows.length ? fx.company.id : null, revision, corrected: false,
      sourceRefs: complete ? [`synthetic-observed-outcome:${scopeKey(scope)}:${start}`] : [...new Set(rows.map(row => row.source))],
    };
    const priorForecast = state === 'future' ? null : priorIssue(fx, scope, scoped, start, endExclusive);
    const variance = actual.status === 'mature' && actual.amount !== null && priorForecast ? {
      amount: sumUsageMoney([actual.amount, negate(priorForecast.amount)]), status: 'available' as const, reason: null,
    } : { amount: null, status: 'unavailable' as const, reason: state !== 'closed' ? 'This week is not complete.' : actual.status !== 'mature' ? 'Complete weekly observations are unavailable.' : 'No eligible forecast was issued before this week.' };
    return { start, endExclusive, state, actual, priorForecast, outlook: rows.length || state === 'future' ? latestOutlook(view, fx.company.id, start, endExclusive, state) : null, variance };
  });
  return { scope, startDate: query.startDate, endDateExclusive: query.endDateExclusive, timezone: 'UTC', unit: 'USD', basis: 'planning', quantity: 'spend', datasetId: fx.company.id,
    asOf: DEMO_NOW, synthetic: true, actualsRevision: `synthetic-ledger-v1:${fingerprint(currentRows)}`, selectionPolicy: 'latest_published_before_week_start', weeks,
    notes: [
      'Deterministic synthetic illustration. Historical issues use only the preceding four complete fixture weeks; no forecast engine or calibration has run.',
      'Synthetic availability assumption: a complete daily fixture observation becomes available at the next UTC midnight. Historical issue timestamps are authored demo fixtures, not archived live publications.',
      'Complete historical weeks have independent synthetic observed-outcome fixtures. Included usage and unpriced usage are excluded from billable spending; simulated charges retain their synthetic identity.',
      'The current day and week are partial. Only complete outcomes with a matching prior issue receive a final over/under amount. Current and future outlooks retain the supplied publication and its supported horizon.',
    ] };
}
