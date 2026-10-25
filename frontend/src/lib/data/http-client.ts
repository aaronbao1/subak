import { adaptBudgetRequest, adaptAllocationState, budgetRequestBody, allocationTargetsBody, type BudgetRequestWire, type AllocationStateWire } from "./budget-requests";
import { adaptWeeklyHistory, validateWeeklyHistoryQuery, type WeeklyHistoryWireResponse } from "./weekly-history";
import { hydrateForecastDashboard } from "./forecast-dashboard";
import type { DataClient, SpendingFilter } from "./client";
import type {
  AllocationTargetsInput, AllocationDraftReceipt, BudgetRequestInput, BudgetRequestDraftInput, WeeklyHistoryQuery, MessageOptions, MessageReconciliation, AllocationProposal, AssistantMessage, Budget, Company, CompanyDocument, ContextItem, Decision, Forecast,
  Person, SpendingRecord, Team, ForecastRefresh, ForecastEvidence, ForecastDriver, ForecastQuestionContext, ForecastScenarioResponse,
} from "@/lib/contracts";

/**
 * HTTP implementation of DataClient. Activated when NEXT_PUBLIC_API_URL is set.
 * Endpoint contract: see ../../../docs/frontend-integration.md. All payloads are the types in src/lib/contracts.
 */
export class HttpDataClient implements DataClient {
  constructor(private baseUrl: string) {}

  private async get<T>(path: string): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, { cache: "no-store" });
    if (!res.ok) throw new Error(`${path} → ${res.status} ${await res.text().catch(() => "")}`);
    return res.json();
  }
  private async post<T>(path: string, body: unknown, headers?: Record<string, string>): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      method: "POST", headers: { "content-type": "application/json", ...headers }, body: JSON.stringify(body),
    });
    if (!res.ok) {
      let message = `${path} → ${res.status}`;
      try { const j = await res.json(); if (typeof j?.error === "string") message = j.error; else if (typeof j?.error?.message === "string") message = j.error.message; else if (j?.detail) message = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail); } catch { /* ignore */ }
      throw Object.assign(new Error(message), { status: res.status, definiteFailure: res.status >= 400 && res.status < 500 && res.status !== 408 });
    }
    return res.json();
  }

  async getAllocationState() { return adaptAllocationState(await this.get<AllocationStateWire>("/api/allocation-state")); }
  async getBudgetRequests() { return (await this.get<{ items: BudgetRequestWire[] }>("/api/budget-requests")).items.map(adaptBudgetRequest); }
  async getBudgetRequest(id: string) {
    const response = await fetch(`${this.baseUrl}/api/budget-requests/${encodeURIComponent(id)}`, { cache: "no-store" });
    if (response.status === 404) return undefined;
    if (!response.ok) throw new Error("Request could not be loaded.");
    return adaptBudgetRequest(await response.json());
  }
  async ingestTeamUpdate(input: BudgetRequestInput) { return adaptBudgetRequest(await this.post<BudgetRequestWire>("/api/budget-requests", budgetRequestBody(input))); }
  async prepareBudgetRequestDraft(id: string, input: BudgetRequestDraftInput, operationId: string): Promise<AllocationDraftReceipt> {
    const receipt = await this.post<{request: BudgetRequestWire; proposal: {id: string}}>(`/api/budget-requests/${encodeURIComponent(id)}/draft`,
      {base_version:input.baseVersion,action_type:input.actionType,source_team_id:input.sourceTeamId ?? null}, {"Idempotency-Key":operationId});
    return {proposalId:receipt.proposal.id,request:adaptBudgetRequest(receipt.request)};
  }
  async prepareAllocationProposal(input: AllocationTargetsInput, operationId: string): Promise<AllocationDraftReceipt> {
    const receipt = await this.post<{id: string}>("/api/allocation-drafts", allocationTargetsBody(input), {"Idempotency-Key":operationId});
    return {proposalId:receipt.id};
  }
  async reconcileAllocationProposal(operationId: string): Promise<AllocationDraftReceipt | undefined> {
    const response = await fetch(`${this.baseUrl}/api/allocation-drafts/${encodeURIComponent(operationId)}`, {cache:"no-store"});
    if (response.status === 404) return undefined;
    if (!response.ok) throw new Error("Draft status could not be checked.");
    const receipt: {id:string} = await response.json();
    return {proposalId:receipt.id};
  }
  async getWeeklyForecastHistory(query: WeeklyHistoryQuery) {
    validateWeeklyHistoryQuery(query);
    const params = new URLSearchParams({ scope_type: query.scopeType, start_date: query.startDate, end_date_exclusive: query.endDateExclusive });
    if (query.scopeId) params.set("scope_id", query.scopeId);
    const response = await this.get<WeeklyHistoryWireResponse>(`/api/forecast-weekly-history?${params}`);
    return adaptWeeklyHistory(response, query);
  }
  async getForecastViews(filter: { scope_type?: string; scope_id?: string; run_id?: string } = {}) {
    const q = new URLSearchParams(Object.entries(filter).filter((entry): entry is [string, string] => typeof entry[1] === "string"));
    q.set("compact", "true");
    return hydrateForecastDashboard(await this.get<unknown>(`/api/forecast-views?${q}`));
  }
  refreshForecast(idempotencyKey: string) { return this.post<ForecastRefresh>("/api/forecast-refreshes", {}, { "Idempotency-Key": idempotencyKey }); }
  getForecastRefresh(id: string) { return this.get<ForecastRefresh>(`/api/forecast-refreshes/${encodeURIComponent(id)}`); }
  getForecastExplanation(runId: string) { return this.get<Record<string, unknown>>(`/api/forecast-runs/${encodeURIComponent(runId)}/explanation`); }
  previewForecastScenario(runId: string, drivers: ForecastDriver[]) { return this.post<ForecastScenarioResponse>(`/api/forecast-runs/${encodeURIComponent(runId)}/scenarios`, { drivers }); }
  getForecastScenario(id: string) { return this.get<ForecastScenarioResponse>(`/api/forecast-scenarios/${encodeURIComponent(id)}`); }
  getForecastEvidence() { return this.get<{ items: ForecastEvidence[] }>("/api/forecast-evidence"); }
  getCompany() { return this.get<Company>("/api/company"); }
  getTeams() { return this.get<Team[]>("/api/teams"); }
  getPeople() { return this.get<Person[]>("/api/people"); }
  getSpending(filter?: SpendingFilter) {
    const q = new URLSearchParams();
    if (filter?.teamId) q.set("teamId", filter.teamId);
    if (filter?.from) q.set("from", filter.from);
    if (filter?.to) q.set("to", filter.to);
    const qs = q.toString();
    return this.get<SpendingRecord[]>(`/api/spending${qs ? `?${qs}` : ""}`);
  }
  getBudgets() { return this.get<Budget[]>("/api/budgets"); }
  getForecasts() { return this.get<Forecast[]>("/api/forecasts"); }
  getContext(teamId?: string) { return this.get<ContextItem[]>(`/api/context${teamId ? `?teamId=${encodeURIComponent(teamId)}` : ""}`); }
  getDocuments() { return this.get<CompanyDocument[]>("/api/documents"); }
  getDocument(id: string) { return this.get<CompanyDocument | undefined>(`/api/documents/${encodeURIComponent(id)}`); }
  getProposals() { return this.get<AllocationProposal[]>("/api/proposals"); }
  getProposal(id: string) { return this.get<AllocationProposal | undefined>(`/api/proposals/${encodeURIComponent(id)}`); }
  getDecisions() { return this.get<Decision[]>("/api/decisions"); }
  getThread(threadId: string) { return this.get<AssistantMessage[]>(`/api/threads/${encodeURIComponent(threadId)}`); }
  sendMessage(threadId: string, content: string, forecastContext?: ForecastQuestionContext, options?: MessageOptions) {
    return this.post<AssistantMessage[]>(`/api/threads/${encodeURIComponent(threadId)}/messages`, { content, ...(forecastContext ? { forecast_context: forecastContext } : {}), ...(options?.clientMessageId ? { client_message_id: options.clientMessageId } : {}), ...(options?.conversationContext ? { conversation_context: options.conversationContext } : {}) });
  }
  async reconcileMessage(threadId: string, clientMessageId: string): Promise<MessageReconciliation> {
    const path = `/api/threads/${encodeURIComponent(threadId)}/messages/${encodeURIComponent(clientMessageId)}`;
    const response = await fetch(`${this.baseUrl}${path}`, { cache: "no-store" });
    if (response.status === 404) return { status: "not_found" };
    if (!response.ok) throw new Error("Message status could not be checked.");
    return response.json();
  }
  applyProposal(proposalId: string, note?: string, operationId?: string) {
    return this.post<Decision>(`/api/proposals/${encodeURIComponent(proposalId)}/apply`, { note }, operationId ? { "Idempotency-Key": operationId } : undefined);
  }
  rejectProposal(proposalId: string) {
    return this.post<AllocationProposal>(`/api/proposals/${encodeURIComponent(proposalId)}/reject`, {});
  }
}
