import type {
  AllocationProposal,
  AssistantMessage,
  Budget,
  Company,
  CompanyDocument,
  ContextItem,
  Decision,
  Forecast, ForecastBundle, ForecastRefresh, ForecastEvidence, ForecastDriver, ForecastQuestionContext, ForecastScenarioResponse,
  Person,
  SpendingRecord,
  Team,
} from "@/lib/contracts";

export interface SpendingFilter {
  teamId?: string;
  from?: string;
  to?: string;
}

/**
 * The ONLY way UI code talks to data. Mock today, HTTP to the backend later.
 * Keep it async everywhere so swapping implementations is a no-op for the UI.
 */
export interface DataClient {
  getForecastViews(filter?: { scope_type?: string; scope_id?: string; run_id?: string }): Promise<ForecastBundle>;
  refreshForecast(idempotencyKey: string): Promise<ForecastRefresh>;
  getForecastRefresh(id: string): Promise<ForecastRefresh>;
  getForecastExplanation(runId: string): Promise<Record<string, unknown>>;
  previewForecastScenario(runId: string, drivers: ForecastDriver[]): Promise<ForecastScenarioResponse>;
  getForecastScenario(scenarioId: string): Promise<ForecastScenarioResponse>;
  getForecastEvidence(): Promise<{ items: ForecastEvidence[] }>;
  getCompany(): Promise<Company>;
  getTeams(): Promise<Team[]>;
  /** Everyone whose usage rolls up into a team. */
  getPeople(): Promise<Person[]>;
  getSpending(filter?: SpendingFilter): Promise<SpendingRecord[]>;
  getBudgets(): Promise<Budget[]>;
  /** Team-level and person-level projections together; person-level ones carry `personId`. */
  getForecasts(): Promise<Forecast[]>;
  getContext(teamId?: string): Promise<ContextItem[]>;
  getDocuments(): Promise<CompanyDocument[]>;
  getDocument(id: string): Promise<CompanyDocument | undefined>;
  getProposals(): Promise<AllocationProposal[]>;
  getProposal(id: string): Promise<AllocationProposal | undefined>;
  getDecisions(): Promise<Decision[]>;
  getThread(threadId: string): Promise<AssistantMessage[]>;
  /** Sends a finance message; resolves with the new messages (user echo + assistant reply). */
  sendMessage(threadId: string, content: string, forecastContext?: ForecastQuestionContext): Promise<AssistantMessage[]>;
  applyProposal(proposalId: string, note?: string): Promise<Decision>;
  rejectProposal(proposalId: string): Promise<AllocationProposal>;
}
