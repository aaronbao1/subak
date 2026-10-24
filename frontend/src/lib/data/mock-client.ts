import type { DataClient, SpendingFilter } from "./client";
import type { AllocationProposal, AssistantMessage, Budget, Decision } from "@/lib/contracts";
import * as fx from "@/fixtures";

const wait = (ms = 120) => new Promise((r) => setTimeout(r, ms));
const newId = (p: string) => `${p}_${Math.random().toString(36).slice(2, 8)}`;

/** In-memory mock. State resets on reload. Fixture owner may extend scripted replies in src/fixtures. */
export class MockDataClient implements DataClient {
  private budgets: Budget[] = structuredClone(fx.budgets);
  private proposals: AllocationProposal[] = structuredClone(fx.proposals);
  private decisions: Decision[] = structuredClone(fx.decisions);
  private threads = new Map<string, AssistantMessage[]>(
    Object.entries(fx.threads).map(([k, v]) => [k, structuredClone(v)]),
  );

  async getCompany() { await wait(); return fx.company; }
  async getTeams() { await wait(); return fx.teams; }
  async getSpending(filter?: SpendingFilter) {
    await wait();
    return fx.spending.filter(
      (r) =>
        (!filter?.teamId || r.teamId === filter.teamId) &&
        (!filter?.from || r.date >= filter.from) &&
        (!filter?.to || r.date <= filter.to),
    );
  }
  async getBudgets() { await wait(); return this.budgets; }
  async getForecasts() { await wait(); return fx.forecasts; }
  async getContext(teamId?: string) {
    await wait();
    return teamId ? fx.context.filter((c) => c.teamIds.includes(teamId)) : fx.context;
  }
  async getProposals() { await wait(); return this.proposals; }
  async getProposal(id: string) { await wait(); return this.proposals.find((p) => p.id === id); }
  async getDecisions() { await wait(); return this.decisions; }
  async getThread(threadId: string) { await wait(); return this.threads.get(threadId) ?? []; }

  async sendMessage(threadId: string, content: string) {
    await wait(600);
    const thread = this.threads.get(threadId) ?? [];
    const now = new Date().toISOString();
    const user: AssistantMessage = { id: newId("msg"), threadId, role: "user", content, createdAt: now };
    const scripted = fx.scriptedReply(content, { proposals: this.proposals, budgets: this.budgets });
    if (scripted.proposal) this.proposals.unshift(scripted.proposal);
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

  async applyProposal(proposalId: string, note?: string) {
    await wait(300);
    const p = this.proposals.find((x) => x.id === proposalId);
    if (!p) throw new Error(`Proposal ${proposalId} not found`);
    if (p.status !== "proposed") throw new Error(`Proposal ${proposalId} is ${p.status}`);
    for (const line of p.lines) {
      const b = this.budgets.find((x) => x.teamId === line.teamId);
      if (b) b.allocated = line.after;
    }
    p.status = "applied";
    const d: Decision = {
      id: newId("dec"),
      proposalId,
      kind: p.kind,
      appliedAt: new Date().toISOString(),
      appliedBy: "finance@demo",
      note,
      lines: p.lines,
      unit: p.unit,
    };
    this.decisions.unshift(d);
    return d;
  }

  async rejectProposal(proposalId: string) {
    await wait(200);
    const p = this.proposals.find((x) => x.id === proposalId);
    if (!p) throw new Error(`Proposal ${proposalId} not found`);
    p.status = "rejected";
    return p;
  }
}
