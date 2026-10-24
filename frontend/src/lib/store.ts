"use client";
import { create } from "zustand";
import type {
  AllocationProposal, AssistantMessage, Budget, Company, ContextItem, Decision, Forecast, SpendingRecord, Team,
} from "@/lib/contracts";
import { getDataClient } from "@/lib/data";

/**
 * App-wide state loaded from the DataClient. Any screen that applies a proposal
 * calls `applyProposal` here so the dashboard, team pages and decision log all refresh.
 */
interface AppState {
  loaded: boolean;
  company?: Company;
  teams: Team[];
  spending: SpendingRecord[];
  budgets: Budget[];
  forecasts: Forecast[];
  context: ContextItem[];
  proposals: AllocationProposal[];
  decisions: Decision[];
  threads: Record<string, AssistantMessage[]>;
  assistantOpen: boolean;
  /** Prefilled text for the assistant composer (e.g. from a team page). Consumed by the drawer. */
  assistantDraft?: string;

  load: () => Promise<void>;
  refreshBudgets: () => Promise<void>;
  setAssistantOpen: (open: boolean) => void;
  /** Opens the drawer with a prefilled prompt. */
  askAssistant: (draft: string) => void;
  clearAssistantDraft: () => void;
  sendMessage: (threadId: string, content: string) => Promise<AssistantMessage[]>;
  applyProposal: (proposalId: string, note?: string) => Promise<Decision>;
  rejectProposal: (proposalId: string) => Promise<void>;
}

export const useAppStore = create<AppState>((set, get) => ({
  loaded: false,
  teams: [], spending: [], budgets: [], forecasts: [], context: [], proposals: [], decisions: [], threads: {},
  assistantOpen: false,

  async load() {
    const c = getDataClient();
    const [company, teams, spending, budgets, forecasts, context, proposals, decisions, main] = await Promise.all([
      c.getCompany(), c.getTeams(), c.getSpending(), c.getBudgets(), c.getForecasts(), c.getContext(),
      c.getProposals(), c.getDecisions(), c.getThread("main"),
    ]);
    set({ loaded: true, company, teams, spending, budgets, forecasts, context, proposals, decisions, threads: { main } });
  },

  async refreshBudgets() {
    const c = getDataClient();
    const [budgets, proposals, decisions] = await Promise.all([c.getBudgets(), c.getProposals(), c.getDecisions()]);
    set({ budgets, proposals, decisions });
  },

  setAssistantOpen: (assistantOpen) => set({ assistantOpen }),
  askAssistant: (assistantDraft) => set({ assistantDraft, assistantOpen: true }),
  clearAssistantDraft: () => set({ assistantDraft: undefined }),

  async sendMessage(threadId, content) {
    const msgs = await getDataClient().sendMessage(threadId, content);
    set((s) => ({ threads: { ...s.threads, [threadId]: [...(s.threads[threadId] ?? []), ...msgs] } }));
    await get().refreshBudgets();
    return msgs;
  },

  async applyProposal(proposalId, note) {
    const d = await getDataClient().applyProposal(proposalId, note);
    await get().refreshBudgets();
    return d;
  },

  async rejectProposal(proposalId) {
    await getDataClient().rejectProposal(proposalId);
    await get().refreshBudgets();
  },
}));
