import type { DataClient, SpendingFilter } from "./client";
import type {
  AllocationProposal, AssistantMessage, Budget, Company, CompanyDocument, ContextItem, Decision, Forecast,
  SpendingRecord, Team,
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
  private async post<T>(path: string, body: unknown): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body),
    });
    if (!res.ok) {
      let message = `${path} → ${res.status}`;
      try { const j = await res.json(); if (j?.error) message = j.error; } catch { /* ignore */ }
      throw new Error(message);
    }
    return res.json();
  }

  getCompany() { return this.get<Company>("/api/company"); }
  getTeams() { return this.get<Team[]>("/api/teams"); }
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
  sendMessage(threadId: string, content: string) {
    return this.post<AssistantMessage[]>(`/api/threads/${encodeURIComponent(threadId)}/messages`, { content });
  }
  applyProposal(proposalId: string, note?: string) {
    return this.post<Decision>(`/api/proposals/${encodeURIComponent(proposalId)}/apply`, { note });
  }
  rejectProposal(proposalId: string) {
    return this.post<AllocationProposal>(`/api/proposals/${encodeURIComponent(proposalId)}/reject`, {});
  }
}
