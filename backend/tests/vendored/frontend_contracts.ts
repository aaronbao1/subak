/**
 * SHARED CONTRACTS — the six handoffs from the master plan, as TypeScript.
 * These are the frontend's view of what backend / forecasting / agent produce.
 * Do NOT change shapes here without the integration owner. Add optional fields if you must.
 */

export type Unit = "credits" | "usd" | "tokens";

/** Fixed seat fees, usage bundled with seats, billable overage on coding tools, and direct API charges. */
export type CostComponent = "subscription" | "included_usage" | "extra_usage" | "api";

/** Where a number came from. Never present an estimate as a bill. */
export type Provenance = "reported_charge" | "estimate" | "usage_only";

export interface Team {
  id: string;
  name: string;
  description?: string;
  lead?: string;
  /** CSS color token or hex used consistently across charts. */
  color: string;
}

export interface Period {
  /** ISO date, inclusive */
  start: string;
  /** ISO date, inclusive */
  end: string;
  label?: string;
}

/** Handoff 1: Spending history (backend → everyone). One row per team/day/component/provider. */
export interface SpendingRecord {
  id: string;
  teamId: string;
  /** ISO date (YYYY-MM-DD) */
  date: string;
  component: CostComponent;
  provider: string; // e.g. "anthropic", "openai", "cursor"
  amount: number;
  unit: Unit;
  provenance: Provenance;
  /** Human-readable source, e.g. "Anthropic cost report export 2026-10-20" */
  source: string;
  /** false when the source is known to be partial for this day */
  complete: boolean;
}

/** Current internal allocation for a team in a period. Planning number, not a provider limit. */
export interface Budget {
  teamId: string;
  period: Period;
  allocated: number;
  unit: Unit;
  /** Backend state version; a proposal built on an older version is stale. */
  version?: string;
}

/** Handoff 4: Forecast (forecasting → agent, frontend). Period comes from forecasting, never hard-coded. */
export interface Forecast {
  id?: string;
  teamId: string;
  period: Period;
  status: "available" | "unavailable";
  /**
   * full_period: projected total for the whole period, INCLUDING spend already incurred.
   * remaining: expected spend from now to period end, EXCLUDING incurred spend.
   * The dashboard must never add incurred spend to a full_period number.
   */
  basis?: "full_period" | "remaining";
  /** A forecast is unconditional; a scenario is conditional on the stated assumptions. */
  kind?: "forecast" | "scenario";
  /** placeholder = shared fixture number, must stay labeled as such; forecasting_service = produced by the real component. */
  origin?: "placeholder" | "forecasting_service";
  projected?: number;
  low?: number;
  high?: number;
  unit: Unit;
  assumptions: string[];
  limitations: string[];
  generatedAt: string; // ISO datetime
  unavailableReason?: string;
}

export interface SourceRef {
  documentId: string;
  title: string;
  /** Short quoted passage supporting the claim */
  excerpt?: string;
  /** Page, section, message timestamp, etc. */
  locator?: string;
  date?: string;
  kind?: ContextKind;
}

export type ContextKind = "plan" | "project_doc" | "research_note" | "correspondence";

/** A stated plan, something that was observed to happen, or the assistant's own interpretation. */
export type ClaimType = "stated_plan" | "observed_event" | "interpretation";

/** Handoff 3: Relevant context (Droid → forecasting, frontend). What is planned or changing. */
export interface ContextItem {
  id: string;
  teamIds: string[];
  title: string;
  summary: string;
  kind: ContextKind;
  /** When the change starts/stops applying, if known */
  effectiveFrom?: string;
  effectiveTo?: string;
  expectedEffect: "increase" | "decrease" | "neutral" | "unknown";
  confidence: "high" | "medium" | "low";
  sources: SourceRef[];
  /** What is still unresolved about this item */
  uncertainty?: string;
  claimType?: ClaimType;
  /** Set when a newer item explicitly replaces this one (e.g. an old thread superseded by an approved plan). */
  supersededBy?: string;
  /** Ids of older items this one supersedes. */
  supersedes?: string[];
}

/** Adding to the overall budget and redistributing the existing budget are DIFFERENT actions. */
export type ProposalKind = "redistribute" | "add_budget";

export interface AllocationLine {
  teamId: string;
  before: number;
  after: number;
}

/** Handoff 5: Budgets and proposed changes (backend ↔ agent/frontend). */
export interface AllocationProposal {
  id: string;
  kind: ProposalKind;
  unit: Unit;
  period: Period;
  totalBefore: number;
  totalAfter: number;
  /** Only for add_budget */
  addedAmount?: number;
  lines: AllocationLine[];
  rationale: string;
  citations: SourceRef[];
  createdAt: string;
  /**
   * proposed → finance is reviewing. pending → apply requested, awaiting backend confirmation.
   * applied → backend confirmed. rejected → finance declined. revised → replaced by a newer proposal.
   * stale → budgets changed since this was built; needs renewed review. failed → backend refused; see failureReason.
   */
  status: "proposed" | "pending" | "applied" | "rejected" | "revised" | "stale" | "failed";
  /** If this proposal revises an earlier one */
  revisesProposalId?: string;
  /** Budget version this proposal was computed against (for staleness checks). */
  basedOnBudgetVersion?: string;
  failureReason?: string;
  /** Snapshot of the projections finance actually reviewed, so the saved explanation never substitutes a later result. */
  forecastsReviewed?: Forecast[];
}

/** Handoff 6: Saved results (backend → frontend/agent). The finance decision and what changed. */
export interface Decision {
  id: string;
  proposalId: string;
  /** What finance did. Rejections are recorded too so history explains them. */
  action: "applied" | "rejected";
  kind: ProposalKind;
  appliedAt: string;
  appliedBy: string;
  note?: string;
  lines: AllocationLine[];
  unit: Unit;
  /** Copied from the proposal at decision time. */
  forecastsReviewed?: Forecast[];
  rationale?: string;
}

export interface ToolCallSummary {
  name: string; // e.g. "get_spending", "run_forecast", "search_documents"
  summary: string; // one line, human readable
}

export interface AssistantMessage {
  id: string;
  threadId: string;
  role: "user" | "assistant";
  content: string; // markdown allowed
  createdAt: string;
  /** Set when the assistant produced a proposal in this message */
  proposalId?: string;
  citations?: SourceRef[];
  toolCalls?: ToolCallSummary[];
}

/** Handoff 2: Readable company material (backend → Droid; frontend for evidence inspection). */
export interface CompanyDocument {
  id: string;
  title: string;
  kind: ContextKind;
  date: string;
  teamIds?: string[];
  /** Where it came from: "Uploaded PDF", "Slack export #research", "Notion export" */
  origin: string;
  /** Markdown body, readable by finance */
  body: string;
  /** Id of the document that replaces this one, if any */
  supersededBy?: string;
}

export interface Company {
  id: string;
  name: string;
  /** Explicit label so demo data is never mistaken for real data */
  isDemo: boolean;
  budgetUnit: Unit;
  currentPeriod: Period;
}
