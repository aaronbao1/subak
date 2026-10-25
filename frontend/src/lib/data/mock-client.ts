import { syntheticForecastBundle } from "./mock-forecast";
import type { DataClient, SpendingFilter } from "./client";
import type { AllocationProposal, AssistantMessage, Budget, Decision, ForecastDriver, ForecastRefresh, ForecastQuestionContext } from "@/lib/contracts";
import { northstar, generateCompany, DEFAULT_TEAM_COUNT, MAX_TEAMS, type Dataset } from "@/fixtures";

const wait = (ms = 120) => new Promise((r) => setTimeout(r, ms));
const newId = (p: string) => `${p}_${Math.random().toString(36).slice(2, 8)}`;
const TEAMS_KEY = "aisp.teams";

/**
 * Pick the dataset. The demo is the generated company with DEFAULT_TEAM_COUNT teams. `?teams=N` (0..16)
 * overrides the team count and is remembered in localStorage; `?teams=default` forgets the override;
 * `?teams=northstar` loads the plan's 3-team example.
 */
function selectDataset(): Dataset {
  const fallback = () => generateCompany(DEFAULT_TEAM_COUNT);
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
  private fx: Dataset = selectDataset();
  private budgets: Budget[] = structuredClone(this.fx.budgets);
  private proposals: AllocationProposal[] = structuredClone(this.fx.proposals);
  private decisions: Decision[] = structuredClone(this.fx.decisions);
  private threads = new Map<string, AssistantMessage[]>(
    Object.entries(this.fx.threads).map(([k, v]) => [k, structuredClone(v)]),
  );

  private forecastRun = "synthetic-ui-run-1";
  private refreshes = new Map<string, ForecastRefresh>();
  async getForecastViews(filter: { scope_type?: string; scope_id?: string; run_id?: string } = {}) {
    await wait();
    const bundle = syntheticForecastBundle(this.fx, filter.run_id ?? this.forecastRun);
    return { ...bundle, views: bundle.views.filter(v => (!filter.scope_type || v.scope.type === filter.scope_type) && (!filter.scope_id || v.scope.id === filter.scope_id)) };
  }
  async refreshForecast(key: string) {
    await wait();
    const prior = this.refreshes.get(key);
    if (prior) return prior;
    const job = { id: `synthetic-refresh-${this.refreshes.size+1}`, status: "completed", run_id: `synthetic-ui-run-${this.refreshes.size+2}` };
    this.forecastRun = job.run_id;
    this.refreshes.set(key, job);
    return job;
  }
  async getForecastRefresh(id: string) { return [...this.refreshes.values()].find(j => j.id === id) ?? { id, status: "failed", error: "Unknown synthetic job" }; }
  async getForecastExplanation(runId: string) { return { run_id: runId, qualification: "Synthetic UI fixture. No production calculation or calibration.", calculations: [] }; }
  async previewForecastScenario(runId: string, drivers: ForecastDriver[]) { await wait(); return syntheticForecastBundle(this.fx, `${runId}:preview`, drivers); }
  async getForecastScenario(id: string) { await wait(); return syntheticForecastBundle(this.fx,id); }
  async getForecastEvidence() { return { items: this.fx.context.map(c => ({ id:c.id, source_id:c.sources[0]?.documentId, text:c.summary, drivers:[{id:c.id,title:c.title,status:"context_only",reason:"Legacy synthetic context has no validated numerical parameters.",citations:c.sources.map(source=>({source_id:source.documentId,excerpt:source.excerpt,title:source.title}))}] })) }; }
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
  async getDocument(id: string) { await wait(); return this.fx.documents.find((d) => d.id === id); }
  async getProposals() { await wait(); return this.proposals.map((p) => ({ ...p })); }
  async getProposal(id: string) { await wait(); const p = this.proposals.find((x) => x.id === id); return p ? { ...p } : undefined; }
  async getDecisions() { await wait(); return this.decisions.map((d) => ({ ...d })); }
  async getThread(threadId: string) { await wait(); return [...(this.threads.get(threadId) ?? [])]; }

  async sendMessage(threadId: string, content: string, forecastContext?: ForecastQuestionContext) {
    await wait(600);
    const thread = this.threads.get(threadId) ?? [];
    const now = new Date().toISOString();
    const user: AssistantMessage = { id: newId("msg"), threadId, role: "user", content, createdAt: now };
    const scripted = this.fx.scriptedReply(content, { proposals: this.proposals, budgets: this.budgets, budgetVersion: this.budgetVersion });
    if (forecastContext) {
      scripted.message = { content: `This is a synthetic UI fixture for issued run **${forecastContext.run_id}**, ${forecastContext.scope_type} **${forecastContext.scope_id ?? "shared"}**${forecastContext.driver_id ? `, driver **${forecastContext.driver_id}**` : ""}. The interface uses a constant observed-rate illustration. Historical error intervals and source-derived numerical effects are unavailable in this mock. Connect the backend fixture pipeline for cited calculations and paired reruns.`, toolCalls: [{ name: "synthetic_forecast_explanation", summary: "Synthetic fixture only; no production forecast or calibration was executed." }] };
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
      role: "assistant",
      createdAt: new Date().toISOString(),
      ...scripted.message,
    };
    thread.push(user, assistant);
    this.threads.set(threadId, thread);
    return [user, assistant];
  }

  private budgetVersion = this.fx.budgets[0]?.version ?? "v1";

  async applyProposal(proposalId: string, note?: string) {
    await wait(300);
    const p = this.proposals.find((x) => x.id === proposalId);
    if (!p) throw new Error(`Proposal ${proposalId} not found`);
    if (p.status === "applied") throw new Error("This proposal was already applied.");
    if (p.status !== "proposed") throw new Error(`Proposal is ${p.status} and cannot be applied.`);
    if (p.basedOnBudgetVersion && p.basedOnBudgetVersion !== this.budgetVersion) {
      p.status = "stale";
      throw new Error("Budgets changed since this proposal was prepared. Ask for a refreshed proposal.");
    }
    // Validate arithmetic the way the backend will.
    const sumAfter = p.lines.reduce((s, l) => s + l.after, 0);
    const sumBefore = p.lines.reduce((s, l) => s + l.before, 0);
    if (sumAfter !== p.totalAfter || sumBefore !== p.totalBefore || (p.kind === "redistribute" && sumAfter !== sumBefore)) {
      p.status = "failed";
      p.failureReason = "Team totals do not reconcile with the company envelope.";
      throw new Error(p.failureReason);
    }
    for (const line of p.lines) {
      const b = this.budgets.find((x) => x.teamId === line.teamId);
      if (b) b.allocated = line.after;
    }
    this.budgetVersion = newId("v");
    for (const b of this.budgets) b.version = this.budgetVersion;
    for (const other of this.proposals) if (other.status === "proposed" && other.id !== p.id) other.status = "stale";
    p.status = "applied";
    const d: Decision = {
      id: newId("dec"),
      proposalId,
      action: "applied",
      kind: p.kind,
      appliedAt: new Date().toISOString(),
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
    if (!p) throw new Error(`Proposal ${proposalId} not found`);
    p.status = "rejected";
    this.decisions.unshift({
      id: newId("dec"), proposalId, action: "rejected", kind: p.kind,
      appliedAt: new Date().toISOString(), appliedBy: "Erin Walsh, FP&A", lines: p.lines, unit: p.unit,
      forecastsReviewed: p.forecastsReviewed, rationale: p.rationale,
    });
    return p;
  }
}
