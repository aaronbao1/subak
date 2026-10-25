import { MockBudgetRequests } from "./mock-budget-requests";
import { budgetRequestConsideration, nextDemoTimestamp } from "@/fixtures/generate";
import { syntheticWeeklyHistory } from "./mock-weekly-history";
import { syntheticForecastBundle } from "./mock-forecast";
import { previewSnapshotScenario, selectSnapshotWeeklyHistory, snapshotForecastBundle } from "./snapshot-read";
import type { DataClient, SpendingFilter } from "./client";
import type { CompanyDocument, AllocationTargetsInput, AllocationState, BudgetRequest, BudgetRequestInput, BudgetRequestDraftInput, WeeklyHistoryQuery, WeeklyHistoryResponse, MessageOptions, MessageReconciliation, AllocationProposal, AssistantMessage, Budget, Decision, ForecastBundle, ForecastDriver, ForecastEvidence, ForecastRefresh, ForecastQuestionContext } from "@/lib/contracts";
import { northstar, generateCompany, MAX_TEAMS, type Dataset } from "@/fixtures";

const wait = (ms = 120) => new Promise((r) => setTimeout(r, ms));
const newId = (p: string) => `${p}_${Math.random().toString(36).slice(2, 8)}`;
const TEAMS_KEY = "aisp.teams";

export interface SnapshotMockOptions {
  bundle: ForecastBundle;
  weeklyHistory: WeeklyHistoryResponse[];
  evidence: { items: ForecastEvidence[] };
  requests: BudgetRequest[];
  allocationState: AllocationState;
}

/**
 * Pick the dataset. The demo is the generated company with DEFAULT_TEAM_COUNT teams. `?teams=N` (0..16)
 * overrides the team count and is remembered in localStorage; `?teams=default` forgets the override;
 * `?teams=northstar` loads the plan's 3-team example.
 */
function selectDataset(): Dataset {
  const fallback = () => northstar;
  if (typeof window === "undefined") return fallback();
  try {
    const q = new URLSearchParams(window.location.search).get("teams");
    if (q === "northstar") { window.localStorage.removeItem(TEAMS_KEY); return northstar; }
    if (q === "default") { window.localStorage.removeItem(TEAMS_KEY); return fallback(); }
    const raw = q ?? window.localStorage.getItem(TEAMS_KEY);
    if (raw == null || raw === "") return fallback();
    const n = Number(raw);
    if (!Number.isInteger(n) || n < 0 || n > MAX_TEAMS) return fallback();
    window.localStorage.setItem(TEAMS_KEY, String(n));
    return generateCompany(n);
  } catch {
    return fallback();
  }
}

/** In-memory mock. State resets on reload. Fixture owner may extend scripted replies in src/fixtures. */
export class MockDataClient implements DataClient {
  private fx: Dataset;
  private budgets: Budget[];
  private proposals: AllocationProposal[];
  private decisions: Decision[];
  private threads: Map<string, AssistantMessage[]>;
  private requestService: MockBudgetRequests;
  private snapshot?: SnapshotMockOptions;
  private budgetVersion: string;
  private budgetStateVersion: number;

  constructor(dataset?: Dataset, snapshot?: SnapshotMockOptions) {
    const source = dataset ?? selectDataset();
    const { scriptedReply, ...values } = source;
    this.fx = { ...structuredClone(values), scriptedReply };
    this.snapshot = snapshot;
    this.budgets = structuredClone(this.fx.budgets);
    this.proposals = structuredClone(this.fx.proposals);
    this.decisions = structuredClone(this.fx.decisions);
    this.threads = new Map(Object.entries(this.fx.threads));
    this.budgetVersion = this.fx.budgets[0]?.version ?? "v1";
    this.budgetStateVersion = snapshot?.allocationState.stateVersion ?? (Number(this.budgetVersion.replace(/^v/, "")) || 1);
    this.forecastRun = snapshot?.bundle.publication?.run_id ?? snapshot?.bundle.views[0]?.run_id ?? this.forecastRun;
    const initialAllocated = this.budgets.reduce((sum, budget) => sum + budget.allocated, 0);
    const reserve = snapshot ? Number(snapshot.allocationState.envelopeTotal) - initialAllocated : 0;
    this.requestService = new MockBudgetRequests(this.fx, {
      getBudgets: () => this.budgets, getProposals: () => this.proposals, getDecisions: () => this.decisions,
      getBudgetVersion: () => this.budgetStateVersion, getBudgetVersionToken: () => this.budgetVersion,
      getForecastBundle: () => this.snapshot?.bundle ?? syntheticForecastBundle(this.fx, this.forecastRun),
      ...(snapshot ? {
        forecastDatasetId: String(snapshot.bundle.views.find(view => view.scope.type === "company")?.dataset_id ?? this.fx.company.id),
        getEnvelopeTotal: () => (this.budgets.reduce((sum, budget) => sum + budget.allocated, 0) + reserve).toFixed(2),
      } : {}),
      createProposal: proposal => { this.proposals.unshift(proposal); },
    }, { initialRequests: snapshot?.requests });
  }

  async getAllocationState() {
    await wait();
    if (this.snapshot && this.budgetStateVersion === this.snapshot.allocationState.stateVersion) return structuredClone(this.snapshot.allocationState);
    const state = this.requestService.getAllocationState();
    if (!this.snapshot) return state;
    return { ...state, spendCoverage: structuredClone(this.snapshot.allocationState.spendCoverage), allocations: state.allocations.map(allocation => {
      const saved = this.snapshot!.allocationState.allocations.find(item => item.teamId === allocation.teamId);
      return saved ? { ...allocation, recordedSpend: saved.recordedSpend, remaining: (Number(allocation.amount) - Number(saved.recordedSpend)).toFixed(2), coverageStatus: saved.coverageStatus } : allocation;
    }) };
  }
  async getBudgetRequests() { await wait(); return this.requestService.listRequests(); }
  async getBudgetRequest(id: string) { await wait(); return this.requestService.listRequests().find(request => request.id === id); }
  async ingestTeamUpdate(input: BudgetRequestInput) { await wait(); return this.requestService.createRequest(input); }
  async prepareBudgetRequestDraft(id: string, input: BudgetRequestDraftInput, operationId: string) { await wait(); return this.requestService.draftRequest(id, input, operationId); }
  async prepareAllocationProposal(input: AllocationTargetsInput, operationId: string) { await wait(); return this.requestService.draftAllocationTargets(input, operationId); }
  async reconcileAllocationProposal(operationId: string) { await wait(); return this.requestService.reconcileDraft(operationId); }

  private forecastRun = "synthetic-ui-run-1";
  private refreshes = new Map<string, ForecastRefresh>();
  async getWeeklyForecastHistory(query: WeeklyHistoryQuery) {
    await wait();
    if (this.snapshot) return selectSnapshotWeeklyHistory(this.snapshot.weeklyHistory, query);
    return syntheticWeeklyHistory(this.fx, query, syntheticForecastBundle(this.fx, this.forecastRun));
  }
  async getForecastViews(filter: { scope_type?: string; scope_id?: string; run_id?: string } = {}) {
    await wait();
    const bundle = this.snapshot ? snapshotForecastBundle(this.snapshot.bundle, filter.run_id) : syntheticForecastBundle(this.fx, filter.run_id ?? this.forecastRun);
    return { ...bundle, views: bundle.views.filter(v => (!filter.scope_type || v.scope.type === filter.scope_type) && (!filter.scope_id || v.scope.id === filter.scope_id)) };
  }
  async refreshForecast(key: string) {
    await wait();
    const prior = this.refreshes.get(key);
    if (prior) return prior;
    const job = { id: `synthetic-refresh-${this.refreshes.size+1}`, status: "completed", run_id: this.snapshot ? this.forecastRun : `synthetic-ui-run-${this.refreshes.size+2}` };
    this.forecastRun = job.run_id;
    this.refreshes.set(key, job);
    return job;
  }
  async getForecastRefresh(id: string) { return [...this.refreshes.values()].find(j => j.id === id) ?? { id, status: "failed", error: "Unknown synthetic job" }; }
  async getForecastExplanation(runId: string) {
    if (this.snapshot) {
      if (!this.snapshot.bundle.views.some(view => view.run_id === runId)) throw new Error("This issued forecast is unavailable in the saved snapshot.");
      return { run_id: runId, qualification: "Saved issued forecast. Detailed calculation traces are not included in this interactive demo.", publication: structuredClone(this.snapshot.bundle.publication), calculations: [] };
    }
    return { run_id: runId, qualification: "Synthetic UI fixture. No production calculation or calibration.", calculations: [] };
  }
  async previewForecastScenario(runId: string, drivers: ForecastDriver[]) { await wait(); return this.snapshot ? previewSnapshotScenario(this.snapshot.bundle, runId, drivers) : syntheticForecastBundle(this.fx, `${runId}:preview`, drivers); }
  async getForecastScenario(id: string) { await wait(); if (this.snapshot) throw new Error("This scenario is not saved in the demo. Open a new preview from an issued forecast."); return syntheticForecastBundle(this.fx,id); }
  async getForecastEvidence() {
    if (this.snapshot) return structuredClone(this.snapshot.evidence);
    return { items: this.fx.context.map(c => ({ id: c.id, source_id: c.sources[0]?.documentId, revision: "synthetic-1", text: c.summary,
      drivers: [{ id: c.id, title: c.title, status: "context_only", reason: "Synthetic source context has no measured financial effect.",
        ...(c.scope === "company" ? { scope: { type: "company", id: this.fx.company.id } } : c.scope === "person" && c.personIds?.length === 1 ? { scope: { type: "person", id: c.personIds[0] } } : c.teamIds.length === 1 ? { scope: { type: "team", id: c.teamIds[0] } } : {}),
        team_ids: c.teamIds, person_ids: c.personIds, effective_from: c.effectiveFrom, effective_to: c.effectiveTo,
        citations: c.sources.map(source => ({ source_id: source.documentId, excerpt: source.excerpt, title: source.title })) }] })) };
  }
  async getCompany() { await wait(); return this.fx.company; }
  async getTeams() { await wait(); return this.fx.teams; }
  async getPeople() { await wait(); return this.fx.people; }
  async getSpending(filter?: SpendingFilter) {
    await wait();
    return this.fx.spending.filter(
      (r) =>
        (!filter?.teamId || r.teamId === filter.teamId) &&
        (!filter?.from || r.date >= filter.from) &&
        (!filter?.to || r.date <= filter.to),
    );
  }
  async getBudgets() { await wait(); return this.budgets.map((b) => ({ ...b })); }
  async getForecasts() { await wait(); return this.fx.forecasts; }
  async getContext(teamId?: string) {
    await wait();
    return teamId ? this.fx.context.filter((c) => c.teamIds.includes(teamId)) : this.fx.context;
  }
  async getDocuments() { await wait(); return this.fx.documents; }
  async getDocument(id: string): Promise<CompanyDocument | undefined> {
    await wait();
    const document = this.fx.documents.find(d => d.id === id);
    if (document) return document;
    const request = this.requestService.listRequests().find(item => item.id === id);
    if (!request) return undefined;
    return {id:request.id,title:request.title,kind:"correspondence",date:request.source.submittedAt.slice(0,10),teamIds:[request.teamId],
      origin:"Submitted budget request",integration:"document",
      body:`${request.narrative}\n\nSource: ${request.sourceRef ?? "Submitted team update"}\n\nRequested additional allocation: ${request.requestedAmount === null ? "Not specified" : `USD ${request.requestedAmount}`}\n\nPeriod: ${request.periodStart} to ${request.periodEndExclusive} (end exclusive).\n\nThis submitted request does not change the issued forecast or approved allocation. Finance reviews any budget proposal separately.`};
  }
  async getProposals() { await wait(); return this.proposals.map((p) => ({ ...p })); }
  async getProposal(id: string) { await wait(); const p = this.proposals.find((x) => x.id === id); return p ? { ...p } : undefined; }
  async getDecisions() { await wait(); return this.decisions.map((d) => ({ ...d })); }
  async getThread(threadId: string) { await wait(); return [...(this.threads.get(threadId) ?? [])]; }

  private messageRequests = new Map<string, { fingerprint: string; promise: Promise<AssistantMessage[]>; messages?: AssistantMessage[] }>();
  async reconcileMessage(threadId: string, clientMessageId: string): Promise<MessageReconciliation> {
    const request = this.messageRequests.get(`${threadId}:${clientMessageId}`);
    return request ? request.messages ? { status: "completed", messages: request.messages } : { status: "pending" } : { status: "not_found" };
  }
  async sendMessage(threadId: string, content: string, forecastContext?: ForecastQuestionContext, options?: MessageOptions) {
    const key = `${threadId}:${options?.clientMessageId ?? newId("request")}`;
    const fingerprint = JSON.stringify({ content, forecastContext, conversationContext: options?.conversationContext });
    const previous = this.messageRequests.get(key);
    if (previous) {
      if (previous.fingerprint !== fingerprint) throw Object.assign(new Error("This message identity was already used for different content."), { definiteFailure: true });
      return previous.promise;
    }
    const promise = this.generateReply(threadId, content, forecastContext, options);
    const request = { fingerprint, promise } as { fingerprint: string; promise: Promise<AssistantMessage[]>; messages?: AssistantMessage[] };
    this.messageRequests.set(key, request);
    promise.then(messages => { request.messages = messages; }, () => { /* Preserve the request identity on failure. */ });
    return promise;
  }
  private async generateReply(threadId: string, content: string, forecastContext?: ForecastQuestionContext, options?: MessageOptions) {
    await wait(600);
    const thread = this.threads.get(threadId) ?? [];
    const now = nextDemoTimestamp();
    const user: AssistantMessage = { id: newId("msg"), threadId, role: "user", content, createdAt: now, clientMessageId: options?.clientMessageId };
    const budgetRequests = this.requestService.listRequests();
    const scripted = this.fx.scriptedReply(content, { proposals: this.proposals, budgets: this.budgets, budgetVersion: this.budgetVersion, budgetRequests }, options?.conversationContext, forecastContext);
    if (!this.snapshot && forecastContext && !scripted.proposal && !scripted.message.conversationContext?.pending_slot && scripted.message.conversationContext?.intent !== "allocation") {
      scripted.message = { citations: scripted.message.citations, conversationContext: scripted.message.conversationContext, content: `This is a synthetic UI fixture for issued run **${forecastContext.run_id}**, ${forecastContext.scope_type} **${forecastContext.scope_id ?? "shared"}**${forecastContext.driver_id ? `, driver **${forecastContext.driver_id}**` : ""}. The interface uses a constant observed-rate illustration. Historical error intervals and source-derived numerical effects are unavailable in this mock. Connect the backend fixture pipeline for cited calculations and paired reruns.`, toolCalls: [{ name: "synthetic_forecast_explanation", summary: "Synthetic fixture only; no production forecast or calibration was executed." }] };
      const requestContext = budgetRequestConsideration(budgetRequests, this.fx.company.currentPeriod, this.fx.teams);
      if (requestContext.content) scripted.message.content += `\n\n${requestContext.content}`;
      scripted.message.toolCalls = [...(scripted.message.toolCalls ?? []), ...requestContext.toolCalls];
      delete scripted.proposal;
    }
    if (scripted.proposal) {
      // A revision replaces the proposal it revises; the older one is kept in history as "revised".
      if (scripted.proposal.revisesProposalId) {
        const old = this.proposals.find((x) => x.id === scripted.proposal!.revisesProposalId);
        if (old && old.status === "proposed") old.status = "revised";
      }
      this.proposals.unshift(scripted.proposal);
    }
    const assistant: AssistantMessage = {
      id: newId("msg"),
      threadId,
      clientMessageId: options?.clientMessageId,
      role: "assistant",
      createdAt: nextDemoTimestamp(),
      ...scripted.message,
    };
    thread.push(user, assistant);
    this.threads.set(threadId, thread);
    return [user, assistant];
  }

  async applyProposal(proposalId: string, note?: string) {
    await wait(300);
    const p = this.proposals.find((x) => x.id === proposalId);
    if (!p) throw Object.assign(new Error(`Proposal ${proposalId} not found`), { definiteFailure: true });
    if (p.status === "applied") throw Object.assign(new Error("This proposal was already applied."), { definiteFailure: true });
    if (p.status !== "proposed") throw Object.assign(new Error(`Proposal is ${p.status} and cannot be applied.`), { definiteFailure: true });
    if (p.basedOnBudgetVersion && p.basedOnBudgetVersion !== this.budgetVersion) {
      p.status = "stale";
      throw Object.assign(new Error("Budgets changed since this proposal was prepared. Ask for a refreshed proposal."), { definiteFailure: true });
    }
    // Validate arithmetic the way the backend will.
    const cents = (value: number) => {
      const minor = Math.round(value * 100);
      if (!Number.isFinite(value) || !Number.isSafeInteger(minor)) throw Object.assign(new Error("Amount exceeds the exact cents supported by this mock."), {definiteFailure:true});
      return BigInt(minor);
    };
    const sumAfter = p.lines.reduce((sum, line) => sum + cents(line.after), BigInt(0));
    const sumBefore = p.lines.reduce((sum, line) => sum + cents(line.before), BigInt(0));
    if (sumAfter !== cents(p.totalAfter) || sumBefore !== cents(p.totalBefore) || (p.kind === "redistribute" && sumAfter !== sumBefore)) {
      p.status = "failed";
      p.failureReason = "Team totals do not reconcile with the company envelope.";
      throw Object.assign(new Error(p.failureReason), { definiteFailure: true });
    }
    for (const line of p.lines) {
      const b = this.budgets.find((x) => x.teamId === line.teamId);
      if (b) b.allocated = line.after;
    }
    this.budgetVersion = `v${++this.budgetStateVersion}`;
    for (const b of this.budgets) b.version = this.budgetVersion;
    for (const other of this.proposals) if (other.status === "proposed" && other.id !== p.id) other.status = "stale";
    p.status = "applied";
    const d: Decision = {
      id: newId("dec"),
      proposalId,
      action: "applied",
      kind: p.kind,
      appliedAt: nextDemoTimestamp(),
      appliedBy: "Erin Walsh, FP&A",
      note,
      lines: p.lines,
      unit: p.unit,
      forecastsReviewed: p.forecastsReviewed,
      rationale: p.rationale,
    };
    this.decisions.unshift(d);
    return d;
  }

  async rejectProposal(proposalId: string) {
    await wait(200);
    const p = this.proposals.find((x) => x.id === proposalId);
    if (!p) throw Object.assign(new Error(`Proposal ${proposalId} not found`), { definiteFailure: true });
    p.status = "rejected";
    this.decisions.unshift({
      id: newId("dec"), proposalId, action: "rejected", kind: p.kind,
      appliedAt: nextDemoTimestamp(), appliedBy: "Erin Walsh, FP&A", lines: p.lines, unit: p.unit,
      forecastsReviewed: p.forecastsReviewed, rationale: p.rationale,
    });
    return p;
  }
}
