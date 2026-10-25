import type {
  AllocationProposal,
  AssistantMessage,
  Budget,
  Company,
  CompanyDocument,
  ContextItem,
  Decision,
  Forecast,
  Person,
  SpendingRecord,
  Team,
} from "@/lib/contracts";

export interface SpendingFilter {
  teamId?: string;
  from?: string;
  to?: string;
}

/**
 * The ONLY way UI code talks to data. Mock today, HTTP to the backend later.
 * Keep it async everywhere so swapping implementations is a no-op for the UI.
 */
export interface DataClient {
  getCompany(): Promise<Company>;
  getTeams(): Promise<Team[]>;
  /** Everyone whose usage rolls up into a team. */
  getPeople(): Promise<Person[]>;
  getSpending(filter?: SpendingFilter): Promise<SpendingRecord[]>;
  getBudgets(): Promise<Budget[]>;
  /** Team-level and person-level projections together; person-level ones carry `personId`. */
  getForecasts(): Promise<Forecast[]>;
  getContext(teamId?: string): Promise<ContextItem[]>;
  getDocuments(): Promise<CompanyDocument[]>;
  getDocument(id: string): Promise<CompanyDocument | undefined>;
  getProposals(): Promise<AllocationProposal[]>;
  getProposal(id: string): Promise<AllocationProposal | undefined>;
  getDecisions(): Promise<Decision[]>;
  getThread(threadId: string): Promise<AssistantMessage[]>;
  /** Sends a finance message; resolves with the new messages (user echo + assistant reply). */
  sendMessage(threadId: string, content: string): Promise<AssistantMessage[]>;
  applyProposal(proposalId: string, note?: string): Promise<Decision>;
  rejectProposal(proposalId: string): Promise<AllocationProposal>;
}
