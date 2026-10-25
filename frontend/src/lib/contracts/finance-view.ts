import type { Period, Provenance, Unit } from './index';

export interface ScopeRef { type: 'company' | 'team' | 'person' | 'shared'; id?: string | null }
/** Half-open UTC target. Dataset identity and financial basis are part of comparability. */
export interface ComparisonTarget {
  scope: ScopeRef;
  startDate: string;
  endDateExclusive: string;
  timezone: 'UTC';
  unit: Unit;
  basis: string;
  datasetId: string;
  issuedRunId?: string;
}
export interface ScopeSummary {
  target: ComparisonTarget;
  observed: { amount: number | null; byProvenance: Record<Provenance, number>; includedNotional: number; recordCount: number; /** Completeness of received records only; not a source-coverage manifest. */ complete: boolean; revision?: string };
  issued: { amount: number | null; runId?: string; synthetic: boolean };
  allocation: number | null;
  variance: number | null;
  quality: string[];
}
export interface TargetInput { scope: ScopeRef; period: Period; unit: Unit; datasetId: string; basis?: string; issuedRunId?: string }
/** Per-driver model sensitivity; effects are not additive or proven causal savings. */
export interface DriverInsight {
  driverId: string;
  runId: string;
  scope: ScopeRef;
  target: ComparisonTarget;
  title: string;
  effectiveFrom?: string;
  effectiveTo?: string;
  effect: number | null;
  inclusion: 'included' | 'queued' | 'context_only';
  sourceRefs: Array<Record<string, unknown>>;
}
