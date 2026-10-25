"use client";
import { create } from "zustand";
import type {
  AllocationState, BudgetRequest, BudgetRequestInput, WeeklyHistoryQuery, WeeklyHistoryResponse, ConversationContext, ProposalActionState, AllocationProposal, AssistantMessage, Budget, Company, ContextItem, Decision, Forecast, ForecastBundle, ForecastRefresh, ForecastEvidence, ForecastQuestionContext, Person, SpendingRecord, Team,
} from "@/lib/contracts";
import { targetForecasts } from "@/components/dashboard/forecast-derive";
import { mergeThreadMessages } from "@/lib/data/thread-merge";
import { scenarioDraftFromConversation, type ActionDraft } from "@/lib/planning-drafts";
import { getDataClient } from "@/lib/data";

/**
 * App-wide state loaded from the DataClient. Any screen that applies a proposal
 * calls `applyProposal` here so the dashboard, team pages and decision log all refresh.
 */
interface AppState {
  allocationState?: AllocationState;
  allocationStateStatus: "idle" | "loading" | "ready" | "stale" | "error";
  allocationStateError?: string;
  loadAllocationState: () => Promise<void>;
  requests: BudgetRequest[];
  requestState: "idle" | "loading" | "ready" | "stale" | "error";
  requestError?: string;
  loadRequests: () => Promise<void>;
  ingestTeamUpdate: (input: BudgetRequestInput) => Promise<BudgetRequest>;
  loaded: boolean;
  loadState: "idle" | "loading" | "ready" | "stale" | "error";
  loadError?: string;
  optionalErrors: Record<string, string>;
  retryOptional: () => Promise<void>;
  budgetSync: "idle" | "loading" | "ready" | "stale";
  budgetSyncError?: string;
  proposalActions: Record<string, ProposalActionState>;
  reconcileProposal: (proposalId: string) => Promise<Decision | undefined>;
  conversationContext?: ConversationContext;
  composerFocus: number;
  updateActionDraft: (threadId: string, messageId: string, draft: ActionDraft) => void;
  reviseProposal: (proposalId: string) => void;
  clearAssistantContext: () => void;
  setAssistantIntent: (intent: ConversationContext["intent"]) => void;
  reconcileMessage: (threadId: string, clientMessageId: string) => Promise<void>;
  weeklyHistory?: WeeklyHistoryResponse;
  weeklyHistoryQuery?: WeeklyHistoryQuery;
  weeklyHistoryState: "idle" | "loading" | "ready" | "stale" | "error";
  weeklyHistoryError?: string;
  loadWeeklyHistory: (query: WeeklyHistoryQuery) => Promise<void>;
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
  /** Compatibility rows for the selected planning period. Longer history uses the bounded daily usage API. */
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
  refreshBudgets: () => Promise<boolean>;
  setAssistantOpen: (open: boolean) => void;
  /** Opens the drawer with a prefilled prompt. */
  askAssistant: (draft: string, context?: ConversationContext) => void;
  setComposer: (text: string) => void;
  sendMessage: (threadId: string, content: string, request?: { conversationContext: ConversationContext; forecastContext?: ForecastQuestionContext }) => Promise<AssistantMessage[]>;
  applyProposal: (proposalId: string, note?: string) => Promise<Decision>;
  rejectProposal: (proposalId: string) => Promise<void>;
}

let requestLoadSequence = 0;
let allocationLoadSequence = 0;
let forecastLoadRequest = 0;
let weeklyLoadRequest = 0;
let budgetMutationRevision = 0;
let inflightLoad: Promise<void> | null = null;
type MessageSnapshot = { isolated?: boolean; context?: ConversationContext; forecastContext?: ForecastQuestionContext; bundle?: ForecastBundle; previousDraft?: ActionDraft };
const messageSnapshots = new Map<string, MessageSnapshot>();

export const useAppStore = create<AppState>((set, get) => ({
  requests: [], requestState: "idle", allocationStateStatus: "idle",
  weeklyHistoryState: "idle", loaded: false, loadState: "idle", optionalErrors: {}, budgetSync: "idle", proposalActions: {}, composerFocus: 0, forecastEvidence: [],
  teams: [], people: [], spending: [], spendingHistory: [], budgets: [], forecasts: [], personForecasts: [], context: [], proposals: [], decisions: [], threads: {},
  assistantOpen: false,
  composer: "",

  async load() {
    if (inflightLoad) return inflightLoad;
    set({ loadState: get().loaded ? "ready" : "loading", loadError: undefined });
    inflightLoad = (async () => {
      const c = getDataClient();
      const optional = get().retryOptional();
      const budgetRevision = budgetMutationRevision;
      try {
        const companyRequest = c.getCompany();
        const spendingRequest = companyRequest.then(company => c.getSpending({ from: company.currentPeriod.start, to: company.currentPeriod.end }));
        const [company, teams, people, spendingHistory, budgets, allForecasts] = await Promise.all([
          companyRequest, c.getTeams(), c.getPeople(), spendingRequest, c.getBudgets(), c.getForecasts(),
        ]);
        const { start, end } = company.currentPeriod;
        const canonical = get().forecastBundle?.views.length ? targetForecasts(get().forecastBundle!, company.currentPeriod) : allForecasts;
        set({ loaded: true, loadState: "ready", loadError: undefined, company, teams, people,
          spending: spendingHistory.filter(r => r.date >= start && r.date <= end), spendingHistory,
          ...(budgetRevision === budgetMutationRevision ? { budgets } : {}),
          forecasts: canonical.filter(f => !f.personId), personForecasts: canonical.filter(f => !!f.personId) });
        await get().loadForecastViews();
      } catch (error) {
        set({ loadState: get().loaded ? "stale" : "error", loadError: errorText(error, "Spending could not be loaded.") });
      }
      await optional;
    })().finally(() => { inflightLoad = null; });
    return inflightLoad;
  },

  async retryOptional() {
    const requestData = Promise.all([get().loadRequests(), get().loadAllocationState()]);
    const c = getDataClient();
    const restoreContext = !get().loaded && !get().conversationContext;
    const results = await Promise.allSettled([c.getContext(), c.getProposals(), c.getDecisions(), c.getThread("main")]);
    const errors: Record<string, string> = {};
    ["evidence", "proposals", "decisions", "assistant"].forEach((name, i) => {
      const result = results[i];
      if (result.status === "rejected") errors[name] = errorText(result.reason, `${name} could not be loaded.`);
    });
    const [context, proposals, decisions, main] = results;
    set(state => ({ optionalErrors: errors,
      ...(context.status === "fulfilled" ? { context: context.value } : {}),
      ...(proposals.status === "fulfilled" ? { proposals: preserveConfirmedProposals(proposals.value, state.proposals, state.proposalActions) } : {}),
      ...(decisions.status === "fulfilled" ? { decisions: mergeDecisions(decisions.value, state.decisions) } : {}),
      ...(main.status === "fulfilled" && restoreContext ? { conversationContext: [...main.value].reverse().find(m => m.role === "assistant")?.conversationContext } : {}),
      ...(main.status === "fulfilled" ? { threads: { ...state.threads, main: mergeThreadMessages(main.value, state.threads.main ?? []) } } : {}),
    }));
    await requestData;
  },

  async loadRequests() {
    const sequence = ++requestLoadSequence;
    set({requestState:"loading",requestError:undefined});
    try {
      const requests = await getDataClient().getBudgetRequests();
      if (sequence === requestLoadSequence) set({requests,requestState:"ready",requestError:undefined});
    } catch (error) {
      if (sequence === requestLoadSequence) set({requestState:get().requests.length ? "stale" : "error",requestError:errorText(error,"Team requests could not be loaded.")});
    }
  },
  async loadAllocationState() {
    const sequence = ++allocationLoadSequence;
    set({allocationStateStatus:"loading",allocationStateError:undefined});
    try {
      const allocationState = await getDataClient().getAllocationState();
      if (sequence === allocationLoadSequence) set({allocationState,allocationStateStatus:"ready",allocationStateError:undefined});
    } catch (error) {
      if (sequence === allocationLoadSequence) set({allocationStateStatus:get().allocationState ? "stale" : "error",allocationStateError:errorText(error,"Approved allocation state could not be loaded.")});
    }
  },
  async ingestTeamUpdate(input) {
    const receipt = await getDataClient().ingestTeamUpdate(input);
    ++requestLoadSequence;
    set(state=>({requests:[receipt,...state.requests.filter(request=>request.id !== receipt.id)],requestState:"ready",requestError:undefined}));
    return receipt;
  },
  async loadWeeklyHistory(query) {
    const previous = get().weeklyHistoryQuery;
    const sameQuery = previous && weeklyQueryKey(previous) === weeklyQueryKey(query);
    if (sameQuery && get().weeklyHistoryState === "loading") return;
    const request = ++weeklyLoadRequest;
    set({ weeklyHistoryQuery: { ...query }, weeklyHistoryState: "loading", weeklyHistoryError: undefined,
      ...(sameQuery ? {} : { weeklyHistory: undefined }) });
    try {
      const weeklyHistory = await getDataClient().getWeeklyForecastHistory(query);
      if (request !== weeklyLoadRequest) return;
      set({ weeklyHistory, weeklyHistoryState: "ready", weeklyHistoryError: undefined });
    } catch (error) {
      if (request !== weeklyLoadRequest) return;
      set({ weeklyHistoryState: get().weeklyHistory ? "stale" : "error", weeklyHistoryError: errorText(error, "Weekly spending history could not be loaded.") });
    }
  },

  async loadForecastViews() {
    const request = ++forecastLoadRequest;
    try {
      const c = getDataClient();
      const [forecastBundle, evidence] = await Promise.all([c.getForecastViews(), c.getForecastEvidence()]);
      if (request !== forecastLoadRequest) return;
      const period = get().company?.currentPeriod;
      const adapted = period ? targetForecasts(forecastBundle, period) : [];
      set({ forecastBundle, forecastEvidence: evidence.items, forecastError: undefined, ...(forecastBundle.views.length ? { forecasts: adapted.filter(f=>!f.personId), personForecasts:adapted.filter(f=>!!f.personId) } : {}) });
      const query = get().weeklyHistoryQuery;
      await Promise.all([get().loadRequests(), ...(query ? [get().loadWeeklyHistory(query)] : [])]);
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
    const requestData = Promise.all([get().loadRequests(), get().loadAllocationState()]);
    const c = getDataClient();
    const budgetRevision = budgetMutationRevision;
    set(state => ({ budgetSync: "loading", budgetSyncError: undefined,
      proposalActions: mapConfirmedActions(state.proposalActions, "pending") }));
    try {
      const [budgets, proposals, decisions] = await Promise.all([c.getBudgets(), c.getProposals(), c.getDecisions()]);
      if (budgetRevision !== budgetMutationRevision) { await requestData; return false; }
      set(state => ({ budgets, budgetSync: "ready", budgetSyncError: undefined,
        proposals: preserveConfirmedProposals(proposals, state.proposals, state.proposalActions),
        decisions: mergeDecisions(decisions, state.decisions),
        proposalActions: mapConfirmedActions(state.proposalActions, "synced") }));
      await requestData;
      return true;
    } catch (error) {
      const message = errorText(error, "The latest totals could not be loaded.");
      set(state => ({ budgetSync: "stale", budgetSyncError: message,
        proposalActions: mapConfirmedActions(state.proposalActions, "failed", message) }));
      await requestData;
      return false;
    }
  },

  setAssistantOpen: (assistantOpen) => set({ assistantOpen }),
  askAssistant: (composer, conversationContext) => set(state => ({ composer, conversationContext: conversationContext ?? {}, assistantOpen: true, forecastQuestionContext: undefined, composerFocus: state.composerFocus + 1 })),
  askForecastAssistant: (composer, forecastQuestionContext) => set(state => ({ composer, assistantOpen: true, forecastQuestionContext,
    conversationContext: { intent: "explain", forecast_run_id: forecastQuestionContext.run_id }, composerFocus: state.composerFocus + 1 })),
  clearAssistantContext: () => set({ conversationContext: {}, forecastQuestionContext: undefined }),
  setAssistantIntent: intent => set(state => ({ forecastQuestionContext: intent === "explain" || (intent === "scenario" && state.forecastQuestionContext?.driver_id) ? state.forecastQuestionContext : undefined,
    conversationContext: { ...(intent === state.conversationContext?.intent ? state.conversationContext : {}), intent } })),
  reviseProposal: proposalId => {
    const proposal = get().proposals.find(p => p.id === proposalId);
    if (!proposal) return;
    set(state => ({ assistantOpen: true, composer: "Revise this proposal: ", forecastQuestionContext: undefined,
      composerFocus: state.composerFocus + 1,
      conversationContext: { intent: "allocation", selected_proposal_id: proposal.id,
        selected_proposal_version: proposal.version, pending_slot: "change", period: proposal.period.label ?? `${proposal.period.start} – ${proposal.period.end}` } }));
  },
  setComposer: (composer) => set({ composer }),
  updateActionDraft: (threadId, messageId, draft) => set(state => ({ threads: { ...state.threads, [threadId]: (state.threads[threadId] ?? []).map(message => message.id === messageId ? { ...message, actionDraft: draft } : message) } })),

  async sendMessage(threadId, content, request) {
    const clientMessageId = crypto.randomUUID();
    const isolated = request !== undefined;
    const context = isolated ? request.conversationContext : get().conversationContext;
    const forecastContext = isolated ? request.forecastContext : get().forecastQuestionContext;
    const forecastBundle = get().forecastBundle;
    const previousDraft = [...(get().threads[threadId] ?? [])].reverse().find(message => message.actionDraft?.kind === "scenario")?.actionDraft;
    const snapshot = { isolated, context, forecastContext, bundle: forecastBundle, previousDraft };
    messageSnapshots.set(clientMessageId, snapshot);
    const pending: AssistantMessage = { id: `pending:${clientMessageId}`, clientMessageId, threadId, role: "user", content,
      createdAt: new Date().toISOString(), delivery: "sending" };
    set(state => ({ composer: !isolated && state.composer.trim() === content.trim() ? "" : state.composer,
      threads: { ...state.threads, [threadId]: [...(state.threads[threadId] ?? []), pending] } }));
    try {
      const response = await getDataClient().sendMessage(threadId, content, forecastContext, { clientMessageId, conversationContext: context ?? {} });
      const messages = withScenarioDrafts(response, snapshot);
      set(state => ({ threads: { ...state.threads, [threadId]: mergeThreadMessages(messages,
        (state.threads[threadId] ?? []).filter(m => m.id !== pending.id || messages.some(accepted => accepted.role === "user" && accepted.clientMessageId === clientMessageId)), "append") },
        ...(!isolated && state.conversationContext === context ? { conversationContext: [...messages].reverse().find(m => m.role === "assistant")?.conversationContext ?? context } : {}) }));
      messageSnapshots.delete(clientMessageId);
      await get().refreshBudgets();
      return messages;
    } catch (error) {
      const delivery = definiteFailure(error) ? "failed" : "unknown";
      set(state => ({ threads: { ...state.threads, [threadId]: (state.threads[threadId] ?? []).map(m => m.role === "user" && m.clientMessageId === clientMessageId ? { ...m, delivery } : m) } }));
      throw error;
    }
  },

  async reconcileMessage(threadId, clientMessageId) {
    try {
      const result = await getDataClient().reconcileMessage(threadId, clientMessageId);
      if (result.status === "completed" && result.messages) {
        const snapshot = messageSnapshots.get(clientMessageId);
        const messages = snapshot ? withScenarioDrafts(result.messages, snapshot) : result.messages;
        set(state => ({ threads: { ...state.threads, [threadId]: mergeThreadMessages(messages,
          (state.threads[threadId] ?? []).filter(m => !(m.clientMessageId === clientMessageId && m.id.startsWith("pending:")) || messages.some(accepted => accepted.role === "user" && accepted.clientMessageId === clientMessageId)), "append") },
          ...((snapshot ? !snapshot.isolated && state.conversationContext === snapshot.context : !state.conversationContext) ? {
            conversationContext: [...messages].reverse().find(m => m.role === "assistant")?.conversationContext ?? state.conversationContext,
          } : {}) }));
        messageSnapshots.delete(clientMessageId);
        await get().refreshBudgets();
      }
    } catch { /* Keep unknown delivery visible; a read failure is not proof the message was rejected. */ }
  },

  async applyProposal(proposalId, note) {
    const previous = get().proposalActions[proposalId];
    if (previous?.mutation === "confirmed" && previous.receipt?.action === "applied") return previous.receipt;
    if (previous && ["pending", "unknown"].includes(previous.mutation)) throw new Error("Check the original request's status before trying again.");
    const operationId = crypto.randomUUID();
    budgetMutationRevision++;
    set(state => ({ proposalActions: { ...state.proposalActions, [proposalId]: { operationId, action: "apply", mutation: "pending", sync: "idle" } } }));
    try {
      const receipt = await getDataClient().applyProposal(proposalId, note, operationId);
      set(state => confirmedReceipt(state, receipt));
      await get().refreshBudgets();
      return receipt;
    } catch (error) {
      set(state => ({ proposalActions: { ...state.proposalActions, [proposalId]: { ...state.proposalActions[proposalId],
        mutation: definiteFailure(error) ? "failed" : "unknown", error: errorText(error, "The outcome could not be confirmed.") } } }));
      const receipt = await get().reconcileProposal(proposalId);
      if (receipt?.action === "applied") return receipt;
      if (definiteFailure(error)) await get().refreshBudgets();
      throw error;
    }
  },

  async reconcileProposal(proposalId) {
    try {
      const receipt = (await getDataClient().getDecisions()).find(d => d.proposalId === proposalId);
      if (!receipt) return undefined;
      set(state => confirmedReceipt(state, receipt));
      await get().refreshBudgets();
      return receipt;
    } catch { return undefined; }
  },

  async rejectProposal(proposalId) {
    const previous = get().proposalActions[proposalId];
    if (previous?.mutation === "confirmed" && previous.action === "reject") return;
    if (previous && ["pending", "unknown"].includes(previous.mutation)) throw new Error("Check the original request's status before trying again.");
    const operationId = crypto.randomUUID();
    budgetMutationRevision++;
    set(state => ({ proposalActions: { ...state.proposalActions, [proposalId]: { operationId, action: "reject", mutation: "pending", sync: "idle" } } }));
    try {
      const proposal = await getDataClient().rejectProposal(proposalId);
      set(state => ({ ...clearSettledProposalContext(state, proposalId), proposals: state.proposals.map(p => p.id === proposalId ? proposal : p),
        proposalActions: { ...state.proposalActions, [proposalId]: { operationId, action: "reject", mutation: "confirmed", sync: "pending" } } }));
      await get().refreshBudgets();
    } catch (error) {
      set(state => ({ proposalActions: { ...state.proposalActions, [proposalId]: { ...state.proposalActions[proposalId],
        mutation: definiteFailure(error) ? "failed" : "unknown", error: errorText(error, "The outcome could not be confirmed.") } } }));
      const receipt = await get().reconcileProposal(proposalId);
      if (receipt?.action === "rejected") return;
      throw error;
    }
  },
}));

function errorText(error: unknown, fallback: string) { return error instanceof Error ? error.message : fallback; }
function definiteFailure(error: unknown) { return typeof error === "object" && error !== null && "definiteFailure" in error && error.definiteFailure === true; }
function mergeDecisions(fetched: Decision[], current: Decision[]) {
  const values = new Map(fetched.map(d => [d.id, d]));
  current.forEach(d => { if (!values.has(d.id)) values.set(d.id, d); });
  return [...values.values()].sort((a, b) => Date.parse(b.appliedAt) - Date.parse(a.appliedAt));
}
function preserveConfirmedProposals(fetched: AllocationProposal[], current: AllocationProposal[], actions: Record<string, ProposalActionState>) {
  const values = new Map(fetched.map(p => [p.id, p]));
  current.forEach(p => {
    const action = actions[p.id];
    if (action?.mutation === "confirmed") values.set(p.id, { ...(values.get(p.id) ?? p), status: action.action === "apply" ? "applied" : "rejected" });
  });
  return [...values.values()];
}
function mapConfirmedActions(actions: Record<string, ProposalActionState>, sync: ProposalActionState["sync"], syncError?: string) {
  return Object.fromEntries(Object.entries(actions).map(([id, action]) => [id, action.mutation === "confirmed" ? { ...action, sync, syncError } : action]));
}
function confirmedReceipt(state: AppState, receipt: Decision): Partial<AppState> {
  const existing = state.proposalActions[receipt.proposalId];
  return { ...clearSettledProposalContext(state, receipt.proposalId), decisions: mergeDecisions([receipt], state.decisions),
    proposals: state.proposals.map(p => p.id === receipt.proposalId ? { ...p, status: receipt.action === "applied" ? "applied" : "rejected" } : p),
    proposalActions: { ...state.proposalActions, [receipt.proposalId]: { operationId: existing?.operationId ?? receipt.id,
      action: receipt.action === "applied" ? "apply" : "reject", mutation: "confirmed", sync: "pending", receipt } } };
}

function withScenarioDrafts(messages: AssistantMessage[], snapshot: MessageSnapshot) {
  return messages.map(message => {
    if (message.role !== "assistant" || message.actionDraft) return message;
    const actionDraft = scenarioDraftFromConversation({ bundle: snapshot.bundle, forecastContext: snapshot.forecastContext, context: message.conversationContext,
      previousDraft: snapshot.previousDraft?.kind === "scenario" ? snapshot.previousDraft : undefined });
    return actionDraft ? { ...message, actionDraft } : message;
  });
}

/** A settled draft is no longer the next action's revision target. Preserve a newer selection. */
function clearSettledProposalContext(state: AppState, proposalId: string): Partial<AppState> {
  return state.conversationContext?.selected_proposal_id === proposalId ? { conversationContext: {} } : {};
}

function weeklyQueryKey(query: WeeklyHistoryQuery) { return JSON.stringify([query.scopeType, query.scopeId ?? null, query.startDate, query.endDateExclusive]); }
