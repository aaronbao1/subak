"use client";
import { create } from "zustand";
import type {
  AllocationProposal, AssistantMessage, Budget, Company, ContextItem, Decision, Forecast, ForecastBundle, ForecastRefresh, ForecastEvidence, ForecastQuestionContext, Person, SpendingRecord, Team,
} from "@/lib/contracts";
import { quarterForecasts } from "@/components/dashboard/forecast-derive";
import { mergeThreadMessages } from "@/lib/data/thread-merge";
import { getDataClient } from "@/lib/data";

/**
 * App-wide state loaded from the DataClient. Any screen that applies a proposal
 * calls `applyProposal` here so the dashboard, team pages and decision log all refresh.
 */
interface AppState {
  loaded: boolean;
  forecastBundle?: ForecastBundle;
  forecastEvidence: ForecastEvidence[];
  forecastError?: string;
  forecastRefresh?: ForecastRefresh;
  refreshForecast: () => Promise<void>;
  loadForecastViews: () => Promise<void>;
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
  forecastQuestionContext?: ForecastQuestionContext;
  askForecastAssistant: (draft: string, context: ForecastQuestionContext) => void;

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

let forecastLoadRequest = 0;
let inflightLoad: Promise<void> | null = null;

export const useAppStore = create<AppState>((set, get) => ({
  loaded: false, forecastEvidence: [],
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
      await get().loadForecastViews();
      const { start, end } = company.currentPeriod;
      const spending = spendingHistory.filter((r) => r.date >= start && r.date <= end);
      const canonical = get().forecastBundle?.views.length ? quarterForecasts(get().forecastBundle!) : allForecasts;
      const forecasts = canonical.filter((f) => !f.personId);
      const personForecasts = canonical.filter((f) => !!f.personId);
      set(state => ({ loaded: true, company, teams, people, spending, spendingHistory, budgets, forecasts, personForecasts, context, proposals, decisions, threads: { ...state.threads, main: mergeThreadMessages(main, state.threads.main ?? []) } }));
    })().finally(() => { inflightLoad = null; });
    return inflightLoad;
  },

  async loadForecastViews() {
    const request = ++forecastLoadRequest;
    try {
      const c = getDataClient();
      const [forecastBundle, evidence] = await Promise.all([c.getForecastViews(), c.getForecastEvidence()]);
      if (request !== forecastLoadRequest) return;
      const adapted = quarterForecasts(forecastBundle);
      set({ forecastBundle, forecastEvidence: evidence.items, forecastError: undefined, ...(forecastBundle.views.length ? { forecasts: adapted.filter(f=>!f.personId), personForecasts:adapted.filter(f=>!!f.personId) } : {}) });
    } catch (e) {
      if (request === forecastLoadRequest) set({ forecastError: e instanceof Error ? e.message : "Forecast publication could not be loaded." });
    }
  },

  async refreshForecast() {
    if (["queued", "running", "pending"].includes(get().forecastRefresh?.status ?? "")) return;
    const c = getDataClient();
    set({ forecastError: undefined, forecastRefresh: { id: "requesting", status: "pending" } });
    try {
      let job = await c.refreshForecast(crypto.randomUUID());
      set({ forecastRefresh: job });
      for (let attempt = 0; attempt < 120 && ["queued", "running", "pending"].includes(job.status); attempt++) {
        await new Promise(resolve => setTimeout(resolve, 500));
        job = await c.getForecastRefresh(job.id);
        set({ forecastRefresh: job });
      }
      if (["completed", "succeeded", "published"].includes(job.status)) await get().loadForecastViews();
      else if (job.status === "failed") set({ forecastError: job.error ?? "Forecast refresh failed. The issued publication remains visible." });
      else set({ forecastError: "Refresh is still running. Reload to check its publication; the current issued run remains visible." });
    } catch (e) {
      set({ forecastRefresh: { id: get().forecastRefresh?.id ?? "requesting", status: "failed" }, forecastError: e instanceof Error ? e.message : "Refresh failed." });
    }
  },

  async refreshBudgets() {
    const c = getDataClient();
    const [budgets, proposals, decisions] = await Promise.all([c.getBudgets(), c.getProposals(), c.getDecisions()]);
    set({ budgets, proposals, decisions });
  },

  setAssistantOpen: (assistantOpen) => set({ assistantOpen }),
  askAssistant: (composer) => set({ composer, assistantOpen: true, forecastQuestionContext: undefined }),
  askForecastAssistant: (composer, forecastQuestionContext) => set({ composer, assistantOpen: true, forecastQuestionContext }),
  setComposer: (composer) => set({ composer }),

  async sendMessage(threadId, content) {
    const msgs = await getDataClient().sendMessage(threadId, content, get().forecastQuestionContext);
    set((s) => ({ threads: { ...s.threads, [threadId]: mergeThreadMessages(msgs, s.threads[threadId] ?? []) } }));
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
