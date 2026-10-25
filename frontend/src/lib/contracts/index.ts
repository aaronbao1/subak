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

/** Where a signal about a person's work came from. Document = an uploaded file or export, not a live connector. */
export type Integration =
  | "slack" | "asana" | "monday" | "email" | "document"
  /** Added for richer evidence rendering; optional everywhere it appears. */
  | "gmail" | "notion" | "google_docs" | "linear" | "pdf";

/**
 * Why an individual's usage is expected to move. project_deferred: a manager pushed work back (e.g. "stay on the
 * design doc longer"); model_change: the person said they are moving to a different model; macro changes carry
 * scope "company" on the ContextItem.
 */
export type SignalKind =
  | "project_deferred"
  | "project_accelerated"
  | "model_change"
  | "tool_change"
  | "out_of_office"
  | "onboarding"
  | "steady"
  /** A provider or vendor changed prices (e.g. a model's per-token rate). Company scope. */
  | "pricing_change"
  /** An internal policy changed who may use what (e.g. a new model enabled for all employees). Company scope. */
  | "policy_change"
  /** Work is paused for an external reason (office renovation, vendor outage); usage drops for the named people. */
  | "project_paused";

/** Where a piece of evidence comes from, for grouping on the Evidence page. */
export type EvidenceCategory = "project" | "staffing" | "policy" | "pricing" | "model" | "macro";

/** Expected size of an evidence item's effect, as finance would state it. Either field may be absent. */
export interface EffectMagnitude {
  /** Signed percent change to the affected spend (e.g. -18 for an 18% drop). */
  pct?: number;
  /** Signed absolute change over the period, in the budget unit. */
  amount?: number;
  /** Plain-language basis, e.g. "3 people at their last-week rate". */
  basis?: string;
}

/** How one evidence item moved a projection away from its trend baseline. */
export interface ForecastAdjustment {
  contextId: string;
  /** Signed amount applied to the projection, in the forecast's unit. */
  amount: number;
  /** One sentence the UI can show, e.g. "Three people paused until Oct 30: −$2,400". */
  note?: string;
}

/**
 * An individual whose usage rolls up into a team. Spending, forecasts and context can be attributed to a person
 * through optional `personId` fields; team totals are always the sum over the team's people plus anything
 * recorded at team level without a person.
 */
export interface Person {
  id: string;
  teamId: string;
  name: string;
  role?: string;
  email?: string;
  /** Integrations this person's signals arrive through (Slack, Asana, Monday). */
  integrations?: Integration[];
  /** Primary coding tool or API workspace, e.g. "Cursor", "Claude Code". */
  primaryTool?: string;
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
  /** The individual this usage is attributed to, when attribution is known. Absent for team-level rows. */
  personId?: string;
  /** ISO date (YYYY-MM-DD) */
  date: string;
  component: CostComponent;
  provider: string; // e.g. "anthropic", "openai", "cursor"
  /** Model the usage ran on, for API rows: "Claude Opus 5.5", "GPT-5.5", "Gemini 3 Pro". Optional. */
  model?: string;
  /** Tokens consumed by this row, when the usage export reports them. Optional; never summed into `amount`. */
  tokens?: number;
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

/**
 * Optional per-day projection for days that are not yet complete: the partial day (its full-day total) and every
 * later day in the period. For a full_period forecast, spend on complete days + the sum of these equals `projected`.
 */
export interface ForecastDailyPoint {
  /** ISO date (YYYY-MM-DD) */
  date: string;
  projected: number;
  low?: number;
  high?: number;
}

/** Handoff 4: Forecast (forecasting → agent, frontend). Period comes from forecasting, never hard-coded. */
export interface Forecast {
  id?: string;
  teamId: string;
  /** Set on a person-level projection. Team-level forecasts have no personId; the UI never mixes the two. */
  personId?: string;
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
  /** Optional day-by-day breakdown of the projection for the days not yet complete. Same unit. */
  daily?: ForecastDailyPoint[];
  /** Trend-only projection before evidence adjustments; `projected = baseline + sum(adjustments)` when both are set. */
  baseline?: number;
  /** Evidence items that moved this projection, with the signed amount each contributed. */
  adjustments?: ForecastAdjustment[];
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
  /** Connector the source arrived through, e.g. a Slack message, an Asana task, a Monday board item. */
  integration?: Integration;
  /** Who said or did it, e.g. the manager who asked for the change. */
  author?: string;
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
  /** Individuals this item is about. A team- or company-wide item leaves this empty. */
  personIds?: string[];
  /** person: one individual's work; team: the team's plan; company: a macro change such as a new model everyone moves to. */
  scope?: "person" | "team" | "company";
  /** Typed reason, so the UI and the assistant can say *why* usage moves without parsing the summary. */
  signal?: SignalKind;
  /** Grouping for the Evidence page. */
  category?: EvidenceCategory;
  /** Expected size of the effect. */
  magnitude?: EffectMagnitude;
  /** Who said it, as the reader would recognize it: "Anthropic pricing page", "Priya N. in #research". */
  attribution?: string;
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
  personIds?: string[];
  integration?: Integration;
}

export interface Company {
  id: string;
  name: string;
  /** Explicit label so demo data is never mistaken for real data */
  isDemo: boolean;
  budgetUnit: Unit;
  currentPeriod: Period;
}
