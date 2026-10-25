"use client";
import { create } from "zustand";
import type {
  AllocationProposal, AssistantMessage, Budget, Company, ContextItem, Decision, Forecast, Person, SpendingRecord, Team,
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
  /** Everyone whose usage rolls up into a team. */
  people: Person[];
  /** Spending inside the current period. Totals, components and team pages use this. */
  spending: SpendingRecord[];
  /** Every spending record the backend holds, earlier periods included. Only the history chart uses this. */
  spendingHistory: SpendingRecord[];
  budgets: Budget[];
  /** Team-level projections only. */
  forecasts: Forecast[];
  /** Person-level projections (each carries `personId`). Sum per team reconciles with the team forecast. */
  personForecasts: Forecast[];
  context: ContextItem[];
  proposals: AllocationProposal[];
  decisions: Decision[];
  threads: Record<string, AssistantMessage[]>;
  assistantOpen: boolean;
  /** Text in the assistant composer. Pages prefill it through askAssistant. */
  composer: string;

  load: () => Promise<void>;
  refreshBudgets: () => Promise<void>;
  setAssistantOpen: (open: boolean) => void;
  /** Opens the drawer with a prefilled prompt. */
  askAssistant: (draft: string) => void;
  setComposer: (text: string) => void;
  sendMessage: (threadId: string, content: string) => Promise<AssistantMessage[]>;
  applyProposal: (proposalId: string, note?: string) => Promise<Decision>;
  rejectProposal: (proposalId: string) => Promise<void>;
}

let inflightLoad: Promise<void> | null = null;

export const useAppStore = create<AppState>((set, get) => ({
  loaded: false,
  teams: [], people: [], spending: [], spendingHistory: [], budgets: [], forecasts: [], personForecasts: [], context: [], proposals: [], decisions: [], threads: {},
  assistantOpen: false,
  composer: "",

  async load() {
    // One load at a time: the live refresh interval can fire faster than a large backend answers,
    // and overlapping full reloads would pile up requests. A tick that lands mid-load joins the running one.
    if (inflightLoad) return inflightLoad;
    inflightLoad = (async () => {
    const c = getDataClient();
    const [company, teams, people, spendingHistory, budgets, allForecasts, context, proposals, decisions, main] = await Promise.all([
      c.getCompany(), c.getTeams(), c.getPeople(), c.getSpending(), c.getBudgets(), c.getForecasts(), c.getContext(),
      c.getProposals(), c.getDecisions(), c.getThread("main"),
    ]);
    const { start, end } = company.currentPeriod;
    const spending = spendingHistory.filter((r) => r.date >= start && r.date <= end);
    const forecasts = allForecasts.filter((f) => !f.personId);
    const personForecasts = allForecasts.filter((f) => !!f.personId);
    set({ loaded: true, company, teams, people, spending, spendingHistory, budgets, forecasts, personForecasts, context, proposals, decisions, threads: { main } });
    })().finally(() => { inflightLoad = null; });
    return inflightLoad;
  },

  async refreshBudgets() {
    const c = getDataClient();
    const [budgets, proposals, decisions] = await Promise.all([c.getBudgets(), c.getProposals(), c.getDecisions()]);
    set({ budgets, proposals, decisions });
  },

  setAssistantOpen: (assistantOpen) => set({ assistantOpen }),
  askAssistant: (composer) => set({ composer, assistantOpen: true }),
  setComposer: (composer) => set({ composer }),

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
