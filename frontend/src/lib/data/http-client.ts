import type { DataClient, SpendingFilter } from "./client";
import type {
  AllocationProposal, AssistantMessage, Budget, Company, CompanyDocument, ContextItem, Decision, Forecast,
  Person, SpendingRecord, Team, ForecastBundle, ForecastRefresh, ForecastEvidence, ForecastDriver, ForecastQuestionContext, ForecastScenarioResponse,
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
      try { const j = await res.json(); if (j?.error) message = j.error; else if (j?.detail) message = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail); } catch { /* ignore */ }
      throw new Error(message);
    }
    return res.json();
  }

  getForecastViews(filter: { scope_type?: string; scope_id?: string; run_id?: string } = {}) {
    const q = new URLSearchParams(Object.entries(filter).filter((entry): entry is [string, string] => typeof entry[1] === "string"));
    return this.get<ForecastBundle>(`/api/forecast-views${q.size ? `?${q}` : ""}`);
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
  sendMessage(threadId: string, content: string, forecastContext?: ForecastQuestionContext) {
    return this.post<AssistantMessage[]>(`/api/threads/${encodeURIComponent(threadId)}/messages`, { content, ...(forecastContext ? { forecast_context: forecastContext } : {}) });
  }
  applyProposal(proposalId: string, note?: string) {
    return this.post<Decision>(`/api/proposals/${encodeURIComponent(proposalId)}/apply`, { note });
  }
  rejectProposal(proposalId: string) {
    return this.post<AllocationProposal>(`/api/proposals/${encodeURIComponent(proposalId)}/reject`, {});
  }
}
