/**
 * SHARED COMPANY EXAMPLE — matches docs/frontend-plan.md exactly, as one planning week in USD.
 * Company: Northstar Software. Teams: Research, Product, Engineering. Reached with `?teams=northstar`;
 * the default demo is the generated 8-team company (src/fixtures/generate.ts).
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
 * Fixtures owner may enrich (more docs, more scripted replies) but these totals are fixed.
 */
import type {
  AllocationProposal, AssistantMessage, Budget, Company, CompanyDocument, ContextItem, Decision, Forecast, ForecastDailyPoint,
  Person, SpendingRecord, Team,
} from "@/lib/contracts";
import {
  addDays, asOf, completeSpent, dailyProjection, dailySeries, macroModelContext, money, monthDay, NEW_MODEL, parseAmount, period,
  personContext, splitExact, type Dataset, type PersonProfile, type ScriptedReplyFn,
} from "./generate";

export { period, asOf, generateCompany, DEFAULT_TEAM_COUNT, MAX_TEAMS, type Dataset } from "./generate";
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

/**
 * People per team. Every spending record and projection is attributed to one of them; the team is the sum.
 * `share` splits the team's fixed totals; `signal` is what the connectors say about this week; `growth` shapes history.
 */
const PEOPLE: Record<string, Array<Omit<PersonProfile, "person"> & { name: string; role: string; tool: string }>> = {
  research: [
    { name: "Priya N.", role: "Lead", tool: "Claude Code", share: 1.2, signal: "steady", integration: "document", modifier: 1, growth: 1.1 },
    { name: "Sam R.", role: "Researcher", tool: "Cursor", share: 0.7, signal: "project_deferred", integration: "slack", modifier: 0.55, growth: 0.84 },
    { name: "Yuki T.", role: "Research engineer", tool: "Claude Code", share: 1.0, signal: "steady", integration: "document", modifier: 1, growth: 1.1 },
    { name: "Omar K.", role: "Researcher", tool: "Claude Code", share: 1.3, signal: "model_change", integration: "asana", modifier: 1.4, growth: 1.18 },
  ],
  product: [
    { name: "Marcus L.", role: "Lead", tool: "Cursor", share: 1.0, signal: "steady", integration: "document", modifier: 1, growth: 1.0 },
    { name: "Chloe W.", role: "Product manager", tool: "Claude Code", share: 0.9, signal: "steady", integration: "document", modifier: 1, growth: 1.0 },
    { name: "Theo B.", role: "Engineer", tool: "Cursor", share: 0.8, signal: "out_of_office", integration: "monday", modifier: 0.12, growth: 1.0 },
  ],
  engineering: [
    { name: "Dana K.", role: "Lead", tool: "Cursor", share: 1.0, signal: "steady", integration: "document", modifier: 1, growth: 1.04 },
    { name: "Ravi S.", role: "Staff engineer", tool: "Claude Code", share: 1.3, signal: "model_change", integration: "asana", modifier: 1.4, growth: 1.18 },
    { name: "Lena F.", role: "Engineer", tool: "Cursor", share: 0.5, signal: "onboarding", integration: "slack", modifier: 1.15, growth: 1.3 },
    { name: "Kai M.", role: "SRE", tool: "GitHub Copilot", share: 0.9, signal: "steady", integration: "document", modifier: 1, growth: 1.04 },
  ],
};

const slugName = (name: string) => name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
const profiles: PersonProfile[] = teams.flatMap((t) =>
  PEOPLE[t.id].map((x) => ({
    person: {
      id: `${t.id}-${slugName(x.name)}`, teamId: t.id, name: x.name, role: x.role, primaryTool: x.tool,
      email: `${slugName(x.name).replace(/-/g, ".")}@northstar.example`,
      integrations: x.integration === "document" ? ["slack"] : ["slack", x.integration],
    } satisfies Person,
    share: x.share, signal: x.signal, integration: x.integration, modifier: x.modifier, growth: x.growth,
  })),
);
export const people: Person[] = profiles.map((x) => x.person);
const teamProfiles = (teamId: string) => profiles.filter((x) => x.person.teamId === teamId);

/** Per-person daily series whose parts sum EXACTLY to the team's fixed total. */
const teamSeries = (teamId: string, total: number, mix: Record<SpendingRecord["component"], number>, provider: string, seed: number) => {
  const ps = teamProfiles(teamId);
  const targets = splitExact(total, ps.map((x) => x.share), 10);
  return ps.flatMap((x, j) => dailySeries(teamId, targets[j], mix, provider, seed + j * 3, x.growth, x.person.id));
};

export const spending: SpendingRecord[] = [
  // Research: nightly eval runs, growing fast. API-heavy. (sums to 45,000)
  ...teamSeries("research", 45_000, { subscription: 1, included_usage: 1.2, extra_usage: 1.5, api: 5 }, "anthropic", 11),
  // Product: launch moved, feature work paused. Seat-heavy, flat. (sums to 20,000)
  ...teamSeries("product", 20_000, { subscription: 2.5, included_usage: 2, extra_usage: 0.4, api: 1.2 }, "anthropic", 12),
  // Engineering: steady migration work. (sums to 30,000)
  ...teamSeries("engineering", 30_000, { subscription: 1.5, included_usage: 1.2, extra_usage: 0.8, api: 2.2 }, "openai", 13),
];

/** Day-by-day projection for today (partial) through Sunday, consistent with the fixed full-week totals above. */
const daily = (teamId: string, projected: number, low: number, high: number) => {
  const done = completeSpent(spending, teamId);
  return dailyProjection(projected - done, low - done, high - done);
};

const planStart = addDays(period.start, -7);
const quarterEnd = addDays(period.end, 63);

/**
 * Person-level projections that sum EXACTLY to the team's fixed projection (85k / 50k / 65k). The split follows
 * each person's share scaled by this week's signal (deferred work down, model migration up, out of office near zero).
 */
function personForecasts(teamId: string, projected: number, low: number, high: number): Forecast[] {
  const ps = teamProfiles(teamId);
  const weights = ps.map((x) => x.share * x.modifier);
  const pr = splitExact(projected, weights, 100);
  const lo = splitExact(low, weights, 100);
  const hi = splitExact(high, weights, 100);
  const note: Record<PersonProfile["signal"], string> = {
    project_deferred: "Build pushed back; staying on the design doc (Slack)",
    model_change: `Migrating to ${NEW_MODEL}; comparison runs at full context (Asana)`,
    out_of_office: `Out of office from ${monthDay(addDays(asOf, 1))} (Monday)`,
    project_accelerated: "Deadline pulled into this week (Asana)",
    onboarding: "Ramping up after joining (Slack)",
    tool_change: "Switching tools",
    steady: "No change signalled",
  };
  return ps.map((x, j) => {
    const done = completeSpent(spending, teamId, x.person.id);
    const daily: ForecastDailyPoint[] = dailyProjection(pr[j] - done, lo[j] - done, hi[j] - done);
    return {
      id: `fc-${x.person.id}-1`, teamId, personId: x.person.id, period, status: "available", unit: "usd",
      basis: "full_period", kind: "forecast", origin: "placeholder",
      projected: pr[j], low: lo[j], high: hi[j], daily,
      assumptions: [note[x.signal], "Weekend usage at about a third of a weekday"],
      limitations: ["Shared placeholder projection", `${monthDay(asOf)} data is partial`],
      generatedAt: `${asOf}T09:00:00Z`,
    };
  });
}

export const forecasts: Forecast[] = [
  {
    id: "fc-research-1", teamId: "research", period, status: "available", unit: "usd",
    basis: "full_period", kind: "forecast", origin: "placeholder",
    projected: 85_000, low: 76_000, high: 96_000,
    daily: daily("research", 85_000, 76_000, 96_000),
    assumptions: [`Approved Q4 Research Plan: nightly evaluation runs continue every day this week, including the weekend (since ${monthDay(planStart)})`, "Provider pricing unchanged"],
    limitations: ["Shared placeholder projection, not the output of a selected model", `${monthDay(asOf)} data is partial`],
    generatedAt: `${asOf}T09:00:00Z`,
  },
  {
    id: "fc-product-1", teamId: "product", period, status: "available", unit: "usd",
    basis: "full_period", kind: "forecast", origin: "placeholder",
    projected: 50_000, low: 44_000, high: 58_000,
    daily: daily("product", 50_000, 44_000, 58_000),
    assumptions: ["v4 launch moved to next quarter; near-term feature work reduced", "Weekend usage at about a third of a weekday"],
    limitations: ["Shared placeholder projection", "Cursor overage is an estimate until the invoice arrives"],
    generatedAt: `${asOf}T09:00:00Z`,
  },
  {
    id: "fc-engineering-1", teamId: "engineering", period, status: "available", unit: "usd",
    basis: "full_period", kind: "forecast", origin: "placeholder",
    projected: 65_000, low: 60_000, high: 71_000,
    daily: daily("engineering", 65_000, 60_000, 71_000),
    assumptions: ["Observability migration continues at the current pace", "Weekend usage at about a third of a weekday"],
    limitations: ["Shared placeholder projection"],
    generatedAt: `${asOf}T09:00:00Z`,
  },
  ...personForecasts("research", 85_000, 76_000, 96_000),
  ...personForecasts("product", 50_000, 44_000, 58_000),
  ...personForecasts("engineering", 65_000, 60_000, 71_000),
];

/** Connector-sourced signals per person (Slack DM, Asana task, Monday board) plus the company-wide model change. */
const personSignals = profiles
  .map((x) => personContext(teams.find((t) => t.id === x.person.teamId)!, x, teams.find((t) => t.id === x.person.teamId)!.lead ?? "Team lead", NEW_MODEL))
  .filter((x): x is NonNullable<typeof x> => x !== undefined);
const macro = macroModelContext(teams, NEW_MODEL);

export const context: ContextItem[] = [
  {
    id: "ctx-research-eval-expansion",
    teamIds: ["research"], scope: "team",
    title: "Approved Q4 plan expands model-evaluation work",
    summary: `The approved Q4 Research Plan adds nightly evaluation runs on three additional benchmark suites starting ${monthDay(planStart)} and continuing through the quarter. This is the current plan of record for Research and the reason this week runs hot.`,
    kind: "plan",
    claimType: "stated_plan",
    effectiveFrom: planStart, effectiveTo: quarterEnd,
    expectedEffect: "increase", confidence: "high",
    supersedes: ["ctx-research-old-timeline"],
    sources: [
      { documentId: "doc-q4-research-plan", title: "Q4 Research Plan (approved)", excerpt: `Nightly runs across HELM-lite, SWE-bench Verified, and the internal agentic suite begin ${monthDay(planStart)} and continue through Q4. This plan supersedes the earlier timeline discussed in #research.`, locator: "§2.3", date: addDays(planStart, -8), kind: "plan" },
    ],
    uncertainty: "The plan does not state a per-run cost. How much it should move the projection is a forecasting decision.",
  },
  {
    id: "ctx-product-launch-moved",
    teamIds: ["product"], scope: "team",
    title: "v4 launch milestone moved to next quarter",
    summary: "A product update moves the v4 launch into next quarter. Near-term feature development is reduced relative to the earlier roadmap, so Product's AI usage is expected to run below its original plan.",
    kind: "project_doc",
    claimType: "stated_plan",
    effectiveFrom: addDays(period.start, -6), effectiveTo: quarterEnd,
    expectedEffect: "decrease", confidence: "medium",
    sources: [
      { documentId: "doc-product-update-oct", title: "Product Roadmap Update", excerpt: "v4 GA moves into next quarter. Focus shifts to stabilization.", locator: "p.1", date: addDays(period.start, -6), kind: "project_doc" },
    ],
    uncertainty: "Stabilization work could still use coding tools heavily if incident load is high.",
  },
  {
    id: "ctx-research-old-timeline",
    teamIds: ["research"],
    title: "Older #research thread with a different eval timeline (superseded)",
    summary: "An earlier Slack thread discussed starting expanded evals a month later with a smaller benchmark set. The approved Q4 Research Plan explicitly supersedes this timeline. Shown for traceability only.",
    kind: "correspondence",
    claimType: "stated_plan",
    effectiveFrom: addDays(period.start, 14),
    expectedEffect: "unknown", confidence: "low",
    supersededBy: "ctx-research-eval-expansion",
    sources: [
      { documentId: "msg-research-0918", title: "Slack #research thread", excerpt: "thinking we kick off the bigger eval sweep next month once the new harness lands, probably just two suites to start", date: addDays(period.start, -35), kind: "correspondence" },
    ],
    uncertainty: "Superseded. Do not use for projections.",
  },
  {
    id: "ctx-engineering-migration",
    teamIds: ["engineering"], scope: "team",
    title: "Observability migration continues through the quarter",
    summary: "An engineering note confirms the observability platform migration continues at its current pace through the end of the quarter, with no planned change in coding-tool or API usage.",
    kind: "project_doc",
    claimType: "stated_plan",
    effectiveFrom: addDays(period.start, -56), effectiveTo: quarterEnd,
    expectedEffect: "neutral", confidence: "medium",
    sources: [
      { documentId: "doc-eng-note-migration", title: "Engineering note: observability migration status", excerpt: "Migration is on track; we expect steady effort through the quarter with no staffing change.", date: addDays(period.start, -10), kind: "project_doc" },
    ],
  },
  ...personSignals.map((x) => x.item),
  macro.item,
];

/** Readable source documents behind the context items. */
export const documents: CompanyDocument[] = [
  {
    id: "doc-q4-research-plan", title: "Q4 Research Plan (approved)", kind: "plan", date: addDays(planStart, -8), teamIds: ["research"],
    origin: "Uploaded PDF (Research leadership)",
    body: `# Q4 Research Plan\n\n## 2.3 Evaluation expansion\n\nNightly runs across HELM-lite, SWE-bench Verified, and the internal agentic suite begin **${monthDay(planStart)}** and continue through Q4. This plan supersedes the earlier timeline discussed in #research.\n\nExpected effect: evaluation token volume roughly doubles. Per-run cost is not estimated here.`,
  },
  {
    id: "doc-product-update-oct", title: "Product Roadmap Update", kind: "project_doc", date: addDays(period.start, -6), teamIds: ["product"],
    origin: "Notion export",
    body: "# Product Roadmap Update\n\nv4 GA moves into **next quarter**. Focus shifts to stabilization and customer escalations. Feature development pauses except P0.",
  },
  {
    id: "msg-research-0918", title: "Slack #research thread", kind: "correspondence", date: addDays(period.start, -35), teamIds: ["research"],
    origin: "Slack export #research", supersededBy: "doc-q4-research-plan",
    body: "**Priya N.** 10:42 — thinking we kick off the bigger eval sweep next month once the new harness lands, probably just two suites to start\n\n**Sam R.** 10:45 — works for me, let's revisit when the Q4 plan is approved",
  },
  {
    id: "doc-eng-note-migration", title: "Engineering note: observability migration status", kind: "project_doc", date: addDays(period.start, -10), teamIds: ["engineering"],
    origin: "Uploaded Markdown",
    body: "# Observability migration: status\n\nMigration is on track; we expect steady effort through the quarter with no staffing change. Tooling usage should remain at current levels.",
  },
  ...personSignals.map((x) => x.doc),
  macro.doc,
];

export const proposals: AllocationProposal[] = [];
export const decisions: Decision[] = [];

export const threads: Record<string, AssistantMessage[]> = {
  main: [
    {
      id: "msg-welcome", threadId: "main", role: "assistant",
      createdAt: `${asOf}T09:05:00Z`,
      content: "This week Research is projected at **$85k against a $60k allocation**, and Product at **$50k against $80k**. I can redistribute the existing envelope, or allocate new funding if finance authorizes it.",
    },
  ],
};

const allSources = () => context.filter((c) => !c.supersededBy).flatMap((c) => c.sources);
const name = (id: string) => teams.find((t) => t.id === id)!.name;
const personItems = (teamId: string) => context.filter((c) => c.scope === "person" && c.teamIds.includes(teamId));
const personSources = (teamId: string) => personItems(teamId).flatMap((c) => c.sources);
/** "By person" lines for a why-reply: who is moving the team number, in which direction, and through which connector. */
function byPerson(teamId: string): string {
  const lines = personItems(teamId).map((c) => {
    const person = people.find((p) => c.personIds?.includes(p.id));
    const pf = forecasts.find((f) => f.personId === person?.id);
    const via = c.sources[0]?.integration;
    const viaLabel = via === "monday" ? "Monday" : via ? via[0].toUpperCase() + via.slice(1) : undefined;
    const dir = c.expectedEffect === "increase" ? "up" : c.expectedEffect === "decrease" ? "down" : "flat";
    return `- **${person?.name ?? "Someone"}** (${dir}${pf?.projected != null ? `, projected ${money(pf.projected)}` : ""}): ${c.summary}${viaLabel ? ` _(via ${viaLabel})_` : ""}`;
  });
  const macroLine = `\n\n**Company-wide:** ${macro.item.summary}`;
  return lines.length ? `\n\n**By person:**\n${lines.join("\n")}${macroLine}` : macroLine;
}

/**
 * Scripted assistant replies for the mock, pattern-matched on the finance message.
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

  // Revise the most recent open proposal: "make it 40k for research instead".
  const open = state.proposals.find((p) => p.status === "proposed");
  const reviseMatch = text.match(/(\$?\s?(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(?:million|thousand|mm|m|k)?)\s*(?:for|to)\s+(research|product|engineering)/);
  if (open && /revis|instead|change|make it|rather/.test(text) && reviseMatch && open.kind === "add_budget") {
    const amount = parseAmount(reviseMatch[1]) ?? 0;
    const target = reviseMatch[2];
    const added = open.addedAmount ?? 0;
    if (amount > added) {
      return { message: { content: `That exceeds the **${money(added)}** finance authorized. I can only split the authorized amount between teams; ask for a larger authorization if you want more.` } };
    }
    const others = open.lines.filter((l) => l.teamId !== target && l.after > l.before);
    const remainder = added - amount;
    const lines = open.lines.map((l) => ({ teamId: l.teamId, before: l.before, after: l.before }));
    const tLine = lines.find((l) => l.teamId === target)!;
    tLine.after = tLine.before + amount;
    if (others.length) {
      const otherTotal = others.reduce((s, l) => s + (l.after - l.before), 0);
      let given = 0;
      others.forEach((o, i) => {
        const share = i === others.length - 1 ? remainder - given : Math.round(((o.after - o.before) / otherTotal) * remainder / 1_000) * 1_000;
        given += share;
        const ln = lines.find((l) => l.teamId === o.teamId)!;
        ln.after = ln.before + share;
      });
    } else if (remainder > 0) {
      const eng = lines.find((l) => l.teamId !== target)!;
      eng.after = eng.before + remainder;
    }
    const proposal: AllocationProposal = {
      ...base,
      id: `prop_${Date.now()}`,
      kind: "add_budget",
      totalBefore: total,
      totalAfter: total + added,
      addedAmount: added,
      lines,
      revisesProposalId: open.id,
      rationale: `Revised at finance's request: ${name(target)} receives ${money(amount)} of the ${money(added)} authorized; the remainder keeps the earlier split between the other funded teams. Projections and evidence are unchanged from the original proposal.`,
      citations: open.citations,
    };
    const bullets = lines.filter((l) => l.after !== l.before).map((l) => `- **${name(l.teamId)} +${money(l.after - l.before)}** → ${money(l.after)}`).join("\n");
    return {
      proposal,
      message: {
        content: `Revised. The earlier proposal is marked as revised and replaced by this one:\n\n${bullets}\n\nEnvelope still goes from **${money(total)} to ${money(total + added)}**.`,
        proposalId: proposal.id,
        citations: proposal.citations,
        toolCalls: [
          { name: "get_budgets", summary: "Re-read current allocations to rebase the revision" },
          { name: "validate_proposal", summary: `Checked team totals sum to ${money(total + added)}` },
        ],
      },
    };
  }

  if (/compare/.test(text)) {
    return {
      message: {
        content: "**Research** is projected at **$85k against $60k** (likely over): nightly evaluation runs under the approved Q4 plan have run every day this week. **Product** is projected at **$50k against $80k** (under) after the v4 launch moved to next quarter. **Engineering** is projected at **$65k against $60k** with steady migration work.\n\nNet: the company is projected at $200k against a $200k envelope, but the team split no longer matches where the work is.",
        citations: allSources(),
        toolCalls: [
          { name: "get_budgets", summary: "Read this week's allocations for 3 teams" },
          { name: "get_forecasts", summary: "Read full-week projections: $85k / $50k / $65k" },
          { name: "search_documents", summary: "Linked each gap to its plan or roadmap source" },
        ],
      },
    };
  }

  if (/what if|scenario|grows|grew|another \d+%/.test(text)) {
    return {
      message: {
        content: "I can't run that scenario yet. The forecasting service has not supplied a conditional projection for that assumption, and I won't invent a number. I can show the current projection and its range, or prepare an allocation proposal against it.",
        toolCalls: [{ name: "run_forecast", summary: "Requested scenario; forecasting returned unsupported" }],
      },
    };
  }

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
        "Research is projected at $85k against $60k, driven by the approved Q4 Research Plan's nightly evaluation runs. $35k brings Research to $95k, just below its high-end projection. Engineering is projected at $65k against $60k with steady migration work; $15k gives it headroom to $75k. Product is projected well under allocation after the v4 launch moved, so it receives nothing new. The older #research timeline was superseded and not used.",
      citations: allSources(),
    };
    return {
      proposal,
      message: {
        content: "Here's how I'd allocate the additional **$50,000**, prioritizing Research:\n\n- **Research +$35,000** → $95,000, covering the nightly eval runs through Sunday\n- **Engineering +$15,000** → $75,000, headroom for the migration\n- **Product +$0** → $80,000, projected under allocation after the launch moved\n\nWeekly envelope goes from **$200,000 to $250,000**. Review the before/after and apply when ready.",
        proposalId: proposal.id,
        citations: proposal.citations,
        toolCalls: [
          { name: "get_spending", summary: `Pulled ${monthDay(period.start)}–${monthDay(asOf)} spending for 3 teams ($95,000 recorded)` },
          { name: "get_forecasts", summary: "Read week projections: $85k / $50k / $65k" },
          { name: "search_documents", summary: "Found Q4 Research Plan §2.3, product roadmap update, engineering migration note" },
          { name: "check_superseded", summary: "Excluded the older #research thread (superseded by approved plan)" },
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
        "Product is projected at $50k against $80k after the v4 launch moved. Moving $25k to Research and $5k to Engineering brings Research to $85k (its projection) and Engineering to $65k (its projection), while Product keeps $50k, matching its own projection. The envelope stays at $200k.",
      citations: allSources(),
    };
    return {
      proposal,
      message: {
        content: "Without adding funding, I'd move **$30,000 out of Product**: **$25,000 to Research** and **$5,000 to Engineering**. Each team lands at its current projection ($85k / $50k / $65k) and the weekly envelope stays at **$200,000**.",
        proposalId: proposal.id,
        citations: proposal.citations,
        toolCalls: [
          { name: "get_budgets", summary: "Read current allocations ($200,000 weekly envelope)" },
          { name: "get_forecasts", summary: "Compared projections to allocations" },
          { name: "search_documents", summary: "Confirmed launch move in the product roadmap update" },
        ],
      },
    };
  }

  if (/why|explain|under|below|headroom/.test(text) && text.includes("product")) {
    return {
      message: {
        content: `Product is running under because the **product roadmap update** moved the v4 launch into next quarter. Feature work paused except P0, so daily coding-tool and API usage has run at roughly 0.6× the earlier pace. The projection of **$50k against $80k** assumes stabilization work stays light through the weekend.${byPerson("product")}`,
        citations: [...context[1].sources, ...personSources("product")],
        toolCalls: [
          { name: "get_spending", summary: "Compared Product daily spend this week with the prior baseline" },
          { name: "search_documents", summary: "Read Product Roadmap Update (p.1)" },
        ],
      },
    };
  }

  if (/why|explain|over|exceed/.test(text) && text.includes("research")) {
    return {
      message: {
        content: `Research is running over because the **approved Q4 Research Plan** started nightly evaluation runs on three new benchmark suites on **${monthDay(planStart)}**. Daily API spend has been roughly 1.6× the earlier baseline every day since, and the runs continue over the weekend. An older thread proposed a smaller, later start, but the approved plan explicitly supersedes it.${byPerson("research")}`,
        citations: [...context[0].sources, ...personSources("research")],
        toolCalls: [
          { name: "get_spending", summary: "Compared Research daily API spend this week with the prior baseline" },
          { name: "search_documents", summary: "Read Q4 Research Plan §2.3 and the older #research thread" },
        ],
      },
    };
  }

  return {
    message: {
      content: "I can help with two kinds of changes: **redistribute** the existing $200,000 weekly envelope between teams, or **add** new funding and allocate it. I can also explain why a team is tracking over or under. What would you like?",
    },
  };
};

/** The plan's canonical 3-team example as a Dataset (`?teams=northstar`). */
export const northstar: Dataset = {
  company, teams, people, budgets, spending, forecasts, context, documents, proposals, decisions, threads, scriptedReply,
};
