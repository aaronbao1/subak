/**
 * SHARED COMPANY EXAMPLE — matches docs/frontend-plan.md exactly. Demo data, clearly fictional.
 * Company: Northstar Software. Teams: Research, Product, Engineering. Unit: USD. One planning period (horizon TBD by forecasting).
 *
 *   Team         Allocation   Spent so far   Projection
 *   Research       60,000       45,000        85,000
 *   Product        80,000       20,000        50,000
 *   Engineering    60,000       30,000        65,000
 *   Total         200,000       95,000       200,000
 *
 * Two canonical outcomes (independent alternatives from this starting state):
 *   Redistribute: product −25k → research, product −5k → engineering  ⇒ 85k / 50k / 65k, envelope 200k
 *   Add funding:  +50k authorized, research first: +35k research, +15k engineering ⇒ 95k / 80k / 75k, envelope 250k
 *
 * Fixtures owner may enrich (more days, more docs, more scripted replies) but these totals are fixed.
 */
import type {
  AllocationProposal, AssistantMessage, Budget, Company, CompanyDocument, ContextItem, Decision, Forecast,
  SpendingRecord, Team,
} from "@/lib/contracts";
import { dailySeries, period, asOf, type Dataset, type ScriptedReplyFn } from "./generate";

export { period, asOf, generateCompany, MAX_TEAMS, type Dataset } from "./generate";
const BUDGET_VERSION = "v1";

export const company: Company = {
  id: "northstar",
  name: "Northstar Software",
  isDemo: true,
  budgetUnit: "usd",
  currentPeriod: period,
};

export const teams: Team[] = [
  { id: "research", name: "Research", lead: "Priya N.", color: "var(--chart-1)", description: "Model evaluation and applied research" },
  { id: "product", name: "Product", lead: "Marcus L.", color: "var(--chart-2)", description: "Customer-facing product features" },
  { id: "engineering", name: "Engineering", lead: "Dana K.", color: "var(--chart-3)", description: "Platform, infrastructure, internal tooling" },
];

export const budgets: Budget[] = [
  { teamId: "research", period, allocated: 60_000, unit: "usd", version: BUDGET_VERSION },
  { teamId: "product", period, allocated: 80_000, unit: "usd", version: BUDGET_VERSION },
  { teamId: "engineering", period, allocated: 60_000, unit: "usd", version: BUDGET_VERSION },
];

export const spending: SpendingRecord[] = [
  // Research ramps up after Oct 14 (eval expansion). API-heavy.
  ...dailySeries("research", 45_000, { subscription: 1, included_usage: 1.2, extra_usage: 1.5, api: 5 }, "anthropic", (d) => (d >= 14 ? 1.6 : 1), 11),
  // Product cools after Oct 15 (launch moved). Seat-heavy.
  ...dailySeries("product", 20_000, { subscription: 2.5, included_usage: 2, extra_usage: 0.4, api: 1.2 }, "anthropic", (d) => (d >= 15 ? 0.6 : 1), 12),
  // Engineering steady.
  ...dailySeries("engineering", 30_000, { subscription: 1.5, included_usage: 1.2, extra_usage: 0.8, api: 2.2 }, "openai", () => 1, 13),
];

export const forecasts: Forecast[] = [
  {
    id: "fc-research-1", teamId: "research", period, status: "available", unit: "usd",
    basis: "full_period", kind: "forecast", origin: "placeholder",
    projected: 85_000, low: 76_000, high: 96_000,
    assumptions: ["Approved Q4 Research Plan: evaluation runs expand from Oct 14 through the end of the planning period", "Provider pricing unchanged"],
    limitations: ["Shared placeholder projection, not the output of a selected model", "Oct 22 data is partial"],
    generatedAt: "2026-10-22T09:00:00Z",
  },
  {
    id: "fc-product-1", teamId: "product", period, status: "available", unit: "usd",
    basis: "full_period", kind: "forecast", origin: "placeholder",
    projected: 50_000, low: 44_000, high: 58_000,
    assumptions: ["v4 launch milestone moved to Q1 2027; near-term feature work reduced"],
    limitations: ["Shared placeholder projection", "Cursor overage is an estimate until the invoice arrives"],
    generatedAt: "2026-10-22T09:00:00Z",
  },
  {
    id: "fc-engineering-1", teamId: "engineering", period, status: "available", unit: "usd",
    basis: "full_period", kind: "forecast", origin: "placeholder",
    projected: 65_000, low: 60_000, high: 71_000,
    assumptions: ["Observability migration continues at the current pace through December"],
    limitations: ["Shared placeholder projection"],
    generatedAt: "2026-10-22T09:00:00Z",
  },
];

export const context: ContextItem[] = [
  {
    id: "ctx-research-eval-expansion",
    teamIds: ["research"],
    title: "Approved Q4 plan expands model-evaluation work",
    summary: "The approved Q4 Research Plan adds nightly evaluation runs on three additional benchmark suites starting Oct 14 and continuing through the planning period. This is the current plan of record for Research.",
    kind: "plan",
    claimType: "stated_plan",
    effectiveFrom: "2026-10-14", effectiveTo: "2026-12-31",
    expectedEffect: "increase", confidence: "high",
    supersedes: ["ctx-research-old-timeline"],
    sources: [
      { documentId: "doc-q4-research-plan", title: "Q4 Research Plan (approved)", excerpt: "Nightly runs across HELM-lite, SWE-bench Verified, and the internal agentic suite begin Oct 14 and continue through Q4. This plan supersedes the September timeline discussed in #research.", locator: "§2.3", date: "2026-10-06", kind: "plan" },
    ],
    uncertainty: "The plan does not state a per-run cost. How much it should move the projection is a forecasting decision.",
  },
  {
    id: "ctx-product-launch-moved",
    teamIds: ["product"],
    title: "v4 launch milestone moved to next period",
    summary: "A product update moves the v4 launch from Dec 3 into Q1 2027. Near-term feature development is reduced relative to the earlier roadmap, so Product's AI usage is expected to run below its original plan.",
    kind: "project_doc",
    claimType: "stated_plan",
    effectiveFrom: "2026-10-15", effectiveTo: "2026-12-31",
    expectedEffect: "decrease", confidence: "medium",
    sources: [
      { documentId: "doc-product-update-oct", title: "Product Roadmap Update, October", excerpt: "v4 GA moves from Dec 3 to the week of Jan 19. Q4 focus shifts to stabilization.", locator: "p.1", date: "2026-10-15", kind: "project_doc" },
    ],
    uncertainty: "Stabilization work could still use coding tools heavily if incident load is high.",
  },
  {
    id: "ctx-research-old-timeline",
    teamIds: ["research"],
    title: "Older #research thread with a different eval timeline (superseded)",
    summary: "A September Slack thread discussed starting expanded evals in November with a smaller benchmark set. The approved Q4 Research Plan explicitly supersedes this timeline. Shown for traceability only.",
    kind: "correspondence",
    claimType: "stated_plan",
    effectiveFrom: "2026-11-01",
    expectedEffect: "unknown", confidence: "low",
    supersededBy: "ctx-research-eval-expansion",
    sources: [
      { documentId: "msg-research-0918", title: "Slack #research, Sep 18", excerpt: "thinking we kick off the bigger eval sweep in Nov once the new harness lands, probably just two suites to start", date: "2026-09-18", kind: "correspondence" },
    ],
    uncertainty: "Superseded. Do not use for projections.",
  },
  {
    id: "ctx-engineering-migration",
    teamIds: ["engineering"],
    title: "Observability migration continues through Q4",
    summary: "An engineering note confirms the observability platform migration continues at its current pace through the end of the period, with no planned change in coding-tool or API usage.",
    kind: "project_doc",
    claimType: "stated_plan",
    effectiveFrom: "2026-10-01", effectiveTo: "2026-12-31",
    expectedEffect: "neutral", confidence: "medium",
    sources: [
      { documentId: "doc-eng-note-migration", title: "Engineering note: observability migration status", excerpt: "Migration is on track; we expect steady effort through December with no staffing change.", date: "2026-10-12", kind: "project_doc" },
    ],
  },
];

/** Readable source documents behind the context items. Fixtures owner: expand bodies to a few paragraphs each. */
export const documents: CompanyDocument[] = [
  {
    id: "doc-q4-research-plan", title: "Q4 Research Plan (approved)", kind: "plan", date: "2026-10-06", teamIds: ["research"],
    origin: "Uploaded PDF (Research leadership)",
    body: "# Q4 Research Plan\n\n## 2.3 Evaluation expansion\n\nNightly runs across HELM-lite, SWE-bench Verified, and the internal agentic suite begin **Oct 14** and continue through Q4. This plan supersedes the September timeline discussed in #research.\n\nExpected effect: evaluation token volume roughly doubles. Per-run cost is not estimated here.",
  },
  {
    id: "doc-product-update-oct", title: "Product Roadmap Update, October", kind: "project_doc", date: "2026-10-15", teamIds: ["product"],
    origin: "Notion export",
    body: "# Product Roadmap Update\n\nv4 GA moves from **Dec 3** to the **week of Jan 19**. Q4 focus shifts to stabilization and customer escalations. Feature development pauses except P0.",
  },
  {
    id: "msg-research-0918", title: "Slack #research, Sep 18", kind: "correspondence", date: "2026-09-18", teamIds: ["research"],
    origin: "Slack export #research", supersededBy: "doc-q4-research-plan",
    body: "**Priya N.** 10:42 — thinking we kick off the bigger eval sweep in Nov once the new harness lands, probably just two suites to start\n\n**Sam R.** 10:45 — works for me, let's revisit when the Q4 plan is approved",
  },
  {
    id: "doc-eng-note-migration", title: "Engineering note: observability migration status", kind: "project_doc", date: "2026-10-12", teamIds: ["engineering"],
    origin: "Uploaded Markdown",
    body: "# Observability migration: status\n\nMigration is on track; we expect steady effort through December with no staffing change. Tooling usage should remain at current levels.",
  },
];

export const proposals: AllocationProposal[] = [];
export const decisions: Decision[] = [];

export const threads: Record<string, AssistantMessage[]> = {
  main: [
    {
      id: "msg-welcome", threadId: "main", role: "assistant",
      createdAt: "2026-10-22T09:05:00Z",
      content: "Research is projected at **$85k against a $60k allocation**, and Product is projected at **$50k against $80k**. I can redistribute the existing envelope, or allocate new funding if finance authorizes it.",
    },
  ],
};

const allSources = () => context.filter((c) => !c.supersededBy).flatMap((c) => c.sources);

/**
 * Scripted assistant replies for the mock, pattern-matched on the finance message.
 * Fixtures owner: add cases (e.g. "why is research over?", "compare research and product").
 */
export const scriptedReply: ScriptedReplyFn = (content, state) => {
  const text = content.toLowerCase();
  const b = (id: string) => state.budgets.find((x) => x.teamId === id)!.allocated;
  const total = state.budgets.reduce((s, x) => s + x.allocated, 0);
  const now = new Date().toISOString();
  const base = {
    unit: "usd" as const, period, createdAt: now, status: "proposed" as const,
    basedOnBudgetVersion: state.budgetVersion,
    forecastsReviewed: structuredClone(forecasts),
  };

  if (/50[, ]?000|50k|\badd|additional|more (credits|budget|funding)/.test(text)) {
    const proposal: AllocationProposal = {
      ...base,
      id: `prop_${Date.now()}`,
      kind: "add_budget",
      totalBefore: total,
      totalAfter: total + 50_000,
      addedAmount: 50_000,
      lines: [
        { teamId: "research", before: b("research"), after: b("research") + 35_000 },
        { teamId: "product", before: b("product"), after: b("product") },
        { teamId: "engineering", before: b("engineering"), after: b("engineering") + 15_000 },
      ],
      rationale:
        "Research is projected at $85k against $60k, driven by the approved Q4 Research Plan's evaluation expansion. $35k brings Research to $95k, above its high-end projection. Engineering is projected at $65k against $60k with steady migration work; $15k gives it headroom to $75k. Product is projected well under allocation after the v4 launch moved to Q1, so it receives nothing new. The older #research timeline was superseded and not used.",
      citations: allSources(),
    };
    return {
      proposal,
      message: {
        content: "Here's how I'd allocate the additional **$50,000**, prioritizing Research:\n\n- **Research +$35,000** → $95,000, covering the approved eval expansion\n- **Engineering +$15,000** → $75,000, headroom for the migration\n- **Product +$0** → $80,000, projected under allocation after the launch moved\n\nCompany envelope goes from **$200,000 to $250,000**. Review the before/after and apply when ready.",
        proposalId: proposal.id,
        citations: proposal.citations,
        toolCalls: [
          { name: "get_spending", summary: "Pulled Oct 1–22 spending for 3 teams ($95,000 recorded)" },
          { name: "get_forecasts", summary: "Read Q4 projections: $85k / $50k / $65k" },
          { name: "search_documents", summary: "Found Q4 Research Plan §2.3, October roadmap update, engineering migration note" },
          { name: "check_superseded", summary: "Excluded Sep 18 #research thread (superseded by approved plan)" },
        ],
      },
    };
  }

  if (/redistribut|rebalanc|\bmove\b|shift|reallocat|without (adding|new)/.test(text)) {
    const proposal: AllocationProposal = {
      ...base,
      id: `prop_${Date.now()}`,
      kind: "redistribute",
      totalBefore: total,
      totalAfter: total,
      lines: [
        { teamId: "research", before: b("research"), after: b("research") + 25_000 },
        { teamId: "product", before: b("product"), after: b("product") - 30_000 },
        { teamId: "engineering", before: b("engineering"), after: b("engineering") + 5_000 },
      ],
      rationale:
        "Product is projected at $50k against $80k after the v4 launch moved to Q1. Moving $25k to Research and $5k to Engineering brings Research to $85k (its projection) and Engineering to $65k (its projection), while Product keeps $50k, matching its own projection. The envelope stays at $200k.",
      citations: allSources(),
    };
    return {
      proposal,
      message: {
        content: "Without adding funding, I'd move **$30,000 out of Product**: **$25,000 to Research** and **$5,000 to Engineering**. Each team lands at its current projection ($85k / $50k / $65k) and the envelope stays at **$200,000**.",
        proposalId: proposal.id,
        citations: proposal.citations,
        toolCalls: [
          { name: "get_budgets", summary: "Read current Q4 allocations ($200,000 envelope)" },
          { name: "get_forecasts", summary: "Compared projections to allocations" },
          { name: "search_documents", summary: "Confirmed launch move in October roadmap update" },
        ],
      },
    };
  }

  if (/why|explain|over|exceed/.test(text) && text.includes("research")) {
    return {
      message: {
        content: "Research is running over because the **approved Q4 Research Plan** started nightly evaluation runs on three new benchmark suites on **Oct 14**. Daily API spend roughly 1.6× since then. An older September thread proposed a smaller November start, but the approved plan explicitly supersedes it.",
        citations: context[0].sources,
        toolCalls: [
          { name: "get_spending", summary: "Compared Research daily API spend before/after Oct 14" },
          { name: "search_documents", summary: "Read Q4 Research Plan §2.3 and Sep 18 #research thread" },
        ],
      },
    };
  }

  return {
    message: {
      content: "I can help with two kinds of changes: **redistribute** the existing $200,000 envelope between teams, or **add** new funding and allocate it. I can also explain why a team is tracking over or under. What would you like?",
    },
  };
};

/** The plan's canonical 3-team example as a Dataset (default when no ?teams= override). */
export const northstar: Dataset = {
  company, teams, budgets, spending, forecasts, context, documents, proposals, decisions, threads, scriptedReply,
};
