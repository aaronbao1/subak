/**
 * SHARED COMPANY EXAMPLE (demo data, clearly fictional).
 * Company: Meridian Software. Budget unit: internal credits. Period: October 2026.
 * The fixtures owner expands this (90 days of daily spending, richer docs, more scripted replies)
 * WITHOUT changing the contracts in src/lib/contracts.
 */
import type {
  AllocationProposal, AssistantMessage, Budget, Company, ContextItem, Decision, Forecast, Period,
  SpendingRecord, Team,
} from "@/lib/contracts";

export const period: Period = { start: "2026-10-01", end: "2026-10-31", label: "October 2026" };

export const company: Company = {
  id: "meridian",
  name: "Meridian Software",
  isDemo: true,
  budgetUnit: "credits",
  currentPeriod: period,
};

export const teams: Team[] = [
  { id: "research", name: "Research", lead: "Priya N.", color: "var(--chart-1)", description: "Model evaluation and applied research" },
  { id: "product", name: "Product Engineering", lead: "Marcus L.", color: "var(--chart-2)", description: "Core product features" },
  { id: "platform", name: "Platform", lead: "Dana K.", color: "var(--chart-3)", description: "Infra, CI, internal tooling" },
  { id: "marketing", name: "Marketing", lead: "Jules O.", color: "var(--chart-4)", description: "Content and campaign tooling" },
];

export const budgets: Budget[] = [
  { teamId: "research", period, allocated: 120_000, unit: "credits" },
  { teamId: "product", period, allocated: 150_000, unit: "credits" },
  { teamId: "platform", period, allocated: 60_000, unit: "credits" },
  { teamId: "marketing", period, allocated: 30_000, unit: "credits" },
];

// Minimal spending: 22 days of Oct, research running hot, product running cool.
function daily(teamId: string, perDay: Record<string, number>, provider: string, days = 22): SpendingRecord[] {
  const out: SpendingRecord[] = [];
  for (let d = 1; d <= days; d++) {
    const date = `2026-10-${String(d).padStart(2, "0")}`;
    const weekend = [3, 4, 10, 11, 17, 18].includes(d) ? 0.35 : 1;
    for (const [component, base] of Object.entries(perDay)) {
      const jitter = 0.85 + ((d * 7 + teamId.length) % 10) / 33;
      const isFixed = component === "subscription";
      out.push({
        id: `${teamId}-${date}-${component}`,
        teamId, date,
        component: component as SpendingRecord["component"],
        provider,
        amount: Math.round(isFixed ? base : base * jitter * weekend),
        unit: "credits",
        provenance: component === "api" ? "reported_charge" : component === "included_usage" ? "usage_only" : "estimate",
        source: component === "api" ? "Anthropic cost report export 2026-10-22" : "Cursor Admin API export 2026-10-22",
        complete: d <= 21,
      });
    }
  }
  return out;
}

export const spending: SpendingRecord[] = [
  ...daily("research", { subscription: 900, included_usage: 1200, extra_usage: 1800, api: 3400 }, "anthropic"),
  ...daily("product", { subscription: 1500, included_usage: 2000, extra_usage: 400, api: 1600 }, "anthropic"),
  ...daily("platform", { subscription: 600, included_usage: 700, extra_usage: 300, api: 900 }, "openai"),
  ...daily("marketing", { subscription: 300, included_usage: 350, extra_usage: 100, api: 350 }, "openai"),
];

export const forecasts: Forecast[] = [
  {
    teamId: "research", period, status: "available", unit: "credits",
    projected: 148_000, low: 136_000, high: 162_000,
    assumptions: ["Eval expansion continues at current pace through Oct 31", "No new model price changes"],
    limitations: ["Based on 21 complete days; Oct 22 is partial", "Subscription fees treated as fixed"],
    generatedAt: "2026-10-22T09:00:00Z",
  },
  {
    teamId: "product", period, status: "available", unit: "credits",
    projected: 112_000, low: 104_000, high: 121_000,
    assumptions: ["Launch freeze reduces feature work through Nov 4"],
    limitations: ["Cursor extra usage is an estimate until invoice arrives"],
    generatedAt: "2026-10-22T09:00:00Z",
  },
  {
    teamId: "platform", period, status: "available", unit: "credits",
    projected: 58_000, low: 54_000, high: 63_000,
    assumptions: ["Steady state"], limitations: [],
    generatedAt: "2026-10-22T09:00:00Z",
  },
  {
    teamId: "marketing", period, status: "unavailable", unit: "credits",
    assumptions: [], limitations: ["Fewer than 14 complete days of API data"],
    unavailableReason: "Insufficient history for this team after provider workspace was re-mapped on Oct 9",
    generatedAt: "2026-10-22T09:00:00Z",
  },
];

export const context: ContextItem[] = [
  {
    id: "ctx-eval-expansion",
    teamIds: ["research"],
    title: "Evaluation suite expanding to 3 new benchmarks",
    summary: "Research plans to run the full eval harness nightly on three additional benchmark sets starting Oct 14, roughly doubling eval token volume for the rest of the quarter.",
    kind: "plan",
    effectiveFrom: "2026-10-14", effectiveTo: "2026-12-31",
    expectedEffect: "increase", confidence: "high",
    sources: [
      { documentId: "doc-q4-research-plan", title: "Q4 Research Plan", excerpt: "Nightly runs across HELM-lite, SWE-bench Verified, and our internal agentic suite begin Oct 14.", locator: "§2.3", date: "2026-10-06", kind: "plan" },
      { documentId: "msg-priya-1012", title: "Slack #research, Priya N.", excerpt: "heads up finance, eval volume is about to go up a lot", date: "2026-10-12", kind: "correspondence" },
    ],
    uncertainty: "Plan does not state per-run token cost; the doubling estimate is the forecasting team's.",
  },
  {
    id: "ctx-launch-freeze",
    teamIds: ["product"],
    title: "Feature freeze ahead of Nov 5 launch",
    summary: "Product Engineering enters a code freeze Oct 20 to Nov 4. Expect fewer coding-tool sessions and lower API usage from feature development.",
    kind: "project_doc",
    effectiveFrom: "2026-10-20", effectiveTo: "2026-11-04",
    expectedEffect: "decrease", confidence: "medium",
    sources: [
      { documentId: "doc-launch-runbook", title: "v4.0 Launch Runbook", excerpt: "Freeze window: Oct 20 – Nov 4. Only P0 fixes.", locator: "p.2", date: "2026-10-01", kind: "project_doc" },
    ],
    uncertainty: "Incident response during launch week could spike usage briefly.",
  },
];

export const proposals: AllocationProposal[] = [];
export const decisions: Decision[] = [];

export const threads: Record<string, AssistantMessage[]> = {
  main: [
    {
      id: "msg-welcome", threadId: "main", role: "assistant",
      createdAt: "2026-10-22T09:05:00Z",
      content: "Research is tracking **23% over** its October allocation and Product Engineering is **25% under**. Ask me to redistribute, or tell me how much new budget is available and how to prioritize it.",
    },
  ],
};

/**
 * Scripted assistant replies for the mock. Pattern-matched on the finance message.
 * The 50,000-credit scenario is the canonical demo. Fixtures owner: add more cases here.
 */
export function scriptedReply(
  content: string,
  state: { proposals: AllocationProposal[]; budgets: Budget[] },
): { message: Omit<AssistantMessage, "id" | "threadId" | "role" | "createdAt">; proposal?: AllocationProposal } {
  const text = content.toLowerCase();
  const b = (id: string) => state.budgets.find((x) => x.teamId === id)!.allocated;
  const now = new Date().toISOString();

  if (/50[, ]?000|50k/.test(text) || text.includes("add")) {
    const proposal: AllocationProposal = {
      id: `prop_${Date.now()}`,
      kind: "add_budget", unit: "credits", period,
      totalBefore: state.budgets.reduce((s, x) => s + x.allocated, 0),
      totalAfter: state.budgets.reduce((s, x) => s + x.allocated, 0) + 50_000,
      addedAmount: 50_000,
      lines: [
        { teamId: "research", before: b("research"), after: b("research") + 35_000 },
        { teamId: "platform", before: b("platform"), after: b("platform") + 10_000 },
        { teamId: "marketing", before: b("marketing"), after: b("marketing") + 5_000 },
        { teamId: "product", before: b("product"), after: b("product") },
      ],
      rationale:
        "Research is projected at 148k against 120k allocated, driven by the eval expansion in the Q4 Research Plan. 35k closes most of that gap. Platform gets 10k headroom for launch-week support. Marketing has no forecast, so 5k is a conservative buffer. Product is projected under allocation during the freeze and needs nothing new.",
      citations: context.flatMap((c) => c.sources),
      createdAt: now, status: "proposed",
    };
    return {
      proposal,
      message: {
        content: "Here's how I'd allocate the additional **50,000 credits**, prioritizing Research:\n\n- **Research +35,000** to cover the eval expansion\n- **Platform +10,000** for launch-week headroom\n- **Marketing +5,000** as a buffer (no forecast available)\n- **Product +0**, projected under allocation during the freeze\n\nReview the before/after and apply when ready.",
        proposalId: proposal.id,
        citations: proposal.citations,
        toolCalls: [
          { name: "get_spending", summary: "Pulled Oct 1–22 spending for 4 teams" },
          { name: "get_forecasts", summary: "Read October projections (Marketing unavailable)" },
          { name: "search_documents", summary: "Found Q4 Research Plan §2.3 and v4.0 Launch Runbook" },
        ],
      },
    };
  }

  if (text.includes("redistribut") || text.includes("rebalanc") || text.includes("move")) {
    const proposal: AllocationProposal = {
      id: `prop_${Date.now()}`,
      kind: "redistribute", unit: "credits", period,
      totalBefore: state.budgets.reduce((s, x) => s + x.allocated, 0),
      totalAfter: state.budgets.reduce((s, x) => s + x.allocated, 0),
      lines: [
        { teamId: "product", before: b("product"), after: b("product") - 30_000 },
        { teamId: "research", before: b("research"), after: b("research") + 30_000 },
        { teamId: "platform", before: b("platform"), after: b("platform") },
        { teamId: "marketing", before: b("marketing"), after: b("marketing") },
      ],
      rationale:
        "Product Engineering is projected at 112k against 150k during the launch freeze. Moving 30k to Research brings Research to 150k, just above its 148k projection, while leaving Product 8k of headroom above its high estimate.",
      citations: context.flatMap((c) => c.sources),
      createdAt: now, status: "proposed",
    };
    return {
      proposal,
      message: {
        content: "Without adding budget, I'd move **30,000 credits from Product Engineering to Research**. Product stays above its high-end projection during the freeze, and Research lands just above its projected spend. Total budget is unchanged.",
        proposalId: proposal.id,
        citations: proposal.citations,
        toolCalls: [
          { name: "get_budgets", summary: "Read current October allocations" },
          { name: "get_forecasts", summary: "Compared projections to allocations" },
        ],
      },
    };
  }

  return {
    message: {
      content: "I can help with two kinds of changes: **redistribute** the existing budget between teams, or **add** new budget and allocate it. Which would you like, and should I prioritize any team?",
    },
  };
}
