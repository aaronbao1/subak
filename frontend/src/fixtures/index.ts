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
import { interpretActionIntent } from "@/lib/action-intent";
import {
  addDays, asOf, nextDemoTimestamp, attachAdjustments, companyEvidence, completeSpent, dailyProjection, dailySeries, evidenceLines, macroModelContext,
  modelSwitchEvidence, money, monthDay, NEW_MODEL, onboardingWaveEvidence, makeGenericReply, withBudgetRequestConsideration, period, personContext, renovationEvidence,
  signedMoney, splitExact, type Dataset, type PersonProfile, type ScriptedReplyFn,
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
    // Marcus, Chloe and Alice share one project; the office renovation pauses it mid-week (ctx-product-renovation-pause).
    { name: "Marcus L.", role: "Lead", tool: "Cursor", share: 1.0, signal: "project_paused", integration: "slack", modifier: 0.55, growth: 1.0 },
    { name: "Chloe W.", role: "Product manager", tool: "Claude Code", share: 0.9, signal: "project_paused", integration: "slack", modifier: 0.55, growth: 1.0 },
    { name: "Theo B.", role: "Engineer", tool: "Cursor", share: 0.8, signal: "out_of_office", integration: "monday", modifier: 0.12, growth: 1.0 },
    { name: "Alice D.", role: "Engineer", tool: "Claude Code", share: 0.8, signal: "project_paused", integration: "slack", modifier: 0.55, growth: 1.0 },
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
const teamSeries = (teamId: string, total: number, mix: Partial<Record<SpendingRecord["component"], number>>, provider: string, seed: number) => {
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
    pricing_change: "Provider price change takes effect",
    policy_change: "New model or tool allowed by policy",
    project_paused: "Project paused for an external reason",
  };
  return ps.map((x, j) => {
    const done = completeSpent(spending, teamId, x.person.id);
    const daily: ForecastDailyPoint[] = dailyProjection(pr[j] - done, lo[j] - done, hi[j] - done);
    return {
      id: `fc-${x.person.id}-1`, teamId, personId: x.person.id, period, status: "available", unit: "usd",
      basis: "full_period", kind: "forecast", origin: "placeholder",
      projected: pr[j], low: lo[j], high: hi[j], daily,
      assumptions: [note[x.signal], "Weekend usage at about a third of a weekday"],
      limitations: ["Not the output of a selected model", `${monthDay(asOf)} data is partial`],
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
    limitations: ["Not the output of a selected model", `${monthDay(asOf)} data is partial`],
    generatedAt: `${asOf}T09:00:00Z`,
  },
  {
    id: "fc-product-1", teamId: "product", period, status: "available", unit: "usd",
    basis: "full_period", kind: "forecast", origin: "placeholder",
    projected: 50_000, low: 44_000, high: 58_000,
    daily: daily("product", 50_000, 44_000, 58_000),
    assumptions: ["v4 launch moved to next quarter; near-term feature work reduced", "Weekend usage at about a third of a weekday"],
    limitations: ["Not the output of a selected model", "Cursor overage is an estimate until the invoice arrives"],
    generatedAt: `${asOf}T09:00:00Z`,
  },
  {
    id: "fc-engineering-1", teamId: "engineering", period, status: "available", unit: "usd",
    basis: "full_period", kind: "forecast", origin: "placeholder",
    projected: 65_000, low: 60_000, high: 71_000,
    daily: daily("engineering", 65_000, 60_000, 71_000),
    assumptions: ["Observability migration continues at the current pace", "Weekend usage at about a third of a weekday"],
    limitations: ["Not the output of a selected model"],
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

/** Company-wide evidence (pricing, policy, seat consolidation, API-key freeze, one assistant interpretation). */
const companyWide = companyEvidence(teams, NEW_MODEL);

/** Person-scope evidence naming several people. The renovation is the owner's example: three people on one team. */
const byName = (...names: string[]) => people.filter((p) => names.includes(p.name));
const renovationFrom = addDays(period.start, 2);
const renovationTo = addDays(period.end, 5);
const renovation = renovationEvidence(teams[1], byName("Marcus L.", "Chloe W.", "Alice D."), renovationFrom, renovationTo);
const cheaperModel = modelSwitchEvidence(teams[0], byName("Priya N.", "Yuki T."), "Claude Haiku 5.5");
const onboardingWave = onboardingWaveEvidence(teams[2], byName("Dana K.", "Kai M."));

/** Team-scope staffing and project evidence on top of the plan documents. */
const hiringFreezeFrom = addDays(period.start, -1);
const rehearsalFrom = addDays(period.end, -1);
const teamEvidence: ContextItem[] = [
  {
    id: "ctx-research-hiring-freeze", teamIds: ["research"], scope: "team", category: "staffing", signal: "policy_change",
    title: "Research hiring freeze: two open researcher roles stay unfilled",
    summary: "Priya N. told the research leads in Slack that the two open researcher roles stay unfilled through the quarter. Their seats and API keys are not provisioned, so the growth the Q4 plan assumed for new hires does not land this period.",
    kind: "correspondence", claimType: "stated_plan",
    effectiveFrom: hiringFreezeFrom, effectiveTo: quarterEnd,
    expectedEffect: "decrease", confidence: "medium",
    magnitude: { pct: -3, basis: "two planned seats not provisioned; their expected first-month usage removed" },
    attribution: "Priya N. in #research-leads",
    sources: [{ documentId: "msg-research-hiring-freeze", title: "Slack #research-leads: hiring update", excerpt: "both researcher reqs are on hold until next quarter — don't provision seats for them, we'll revisit after close", locator: "#research-leads", date: hiringFreezeFrom, kind: "correspondence", integration: "slack", author: "Priya N." }],
    uncertainty: "If one role is backfilled by an internal transfer, that seat appears mid-period.",
  },
  {
    id: "ctx-engineering-cutover-rehearsal", teamIds: ["engineering"], scope: "team", category: "project", signal: "project_accelerated",
    title: `Observability cutover rehearsal on ${monthDay(rehearsalFrom)}`,
    summary: `The engineering Monday board schedules a full cutover rehearsal for the observability migration on ${monthDay(rehearsalFrom)}. The rehearsal replays a day of traffic through the new pipeline with LLM-assisted log triage, a one-off that lifts API usage for the weekend.`,
    kind: "project_doc", claimType: "stated_plan",
    effectiveFrom: rehearsalFrom, effectiveTo: period.end,
    expectedEffect: "increase", confidence: "medium",
    magnitude: { pct: 6, basis: "one-off replay of a day of traffic with LLM log triage, weekend only" },
    attribution: "Dana K., monday.com migration board",
    sources: [{ documentId: "doc-eng-cutover-rehearsal", title: "monday.com: Observability migration board", excerpt: `Cutover rehearsal — ${monthDay(rehearsalFrom)}. Replay one day of production traffic through the new pipeline; triage diffs with the assistant.`, locator: "row · Cutover rehearsal", date: addDays(period.start, -4), kind: "project_doc", integration: "monday", author: "Dana K." }],
    uncertainty: "If the rehearsal is cut short the lift is smaller; if it finds problems it may be repeated next weekend.",
  },
];

export const context: ContextItem[] = [
  {
    id: "ctx-research-eval-expansion",
    teamIds: ["research"], scope: "team", category: "project",
    magnitude: { pct: 25, basis: "nightly runs on three additional benchmark suites, every day including the weekend" },
    attribution: "Research leadership, approved Q4 plan",
    title: "Approved Q4 plan expands model-evaluation work",
    summary: `The approved Q4 Research Plan adds nightly evaluation runs on three additional benchmark suites starting ${monthDay(planStart)} and continuing through the quarter. This is the current plan of record for Research and the reason this week runs hot.`,
    kind: "plan",
    claimType: "stated_plan",
    effectiveFrom: planStart, effectiveTo: quarterEnd,
    expectedEffect: "increase", confidence: "high",
    supersedes: ["ctx-research-old-timeline"],
    sources: [
      { documentId: "doc-q4-research-plan", title: "Q4 Research Plan (approved)", excerpt: `Nightly runs across HELM-lite, SWE-bench Verified, and the internal agentic suite begin ${monthDay(planStart)} and continue through Q4. This plan supersedes the earlier timeline discussed in #research.`, locator: "§2.3", date: addDays(planStart, -8), kind: "plan", integration: "pdf", author: "Research leadership" },
      { documentId: "mail-research-finance", title: "Email: Re: AI spend this week", excerpt: "Heads up: the nightly eval sweep is live from this week, so our API line will run roughly 1.5× until the benchmark set is trimmed. Approval for the additional spend is attached.", locator: "finance@northstar", date: addDays(period.start, -2), kind: "correspondence", integration: "gmail", author: "Priya N." },
    ],
    uncertainty: "The plan does not state a per-run cost. How much it should move the projection is a forecasting decision.",
  },
  {
    id: "ctx-product-launch-moved",
    teamIds: ["product"], scope: "team", category: "project",
    magnitude: { pct: -20, basis: "feature work paused except P0; stabilization and escalations only" },
    attribution: "Marcus L. in the product roadmap update",
    title: "v4 launch milestone moved to next quarter",
    summary: "A product update moves the v4 launch into next quarter. Near-term feature development is reduced relative to the earlier roadmap, so Product's AI usage is expected to run below its original plan.",
    kind: "project_doc",
    claimType: "stated_plan",
    effectiveFrom: addDays(period.start, -6), effectiveTo: quarterEnd,
    expectedEffect: "decrease", confidence: "medium",
    sources: [
      { documentId: "doc-product-update-oct", title: "Product Roadmap Update", excerpt: "v4 GA moves into next quarter. Focus shifts to stabilization and customer escalations. Feature development pauses except P0.", locator: "Roadmap · Q4", date: addDays(period.start, -6), kind: "project_doc", integration: "notion", author: "Marcus L." },
    ],
    uncertainty: "Stabilization work could still use coding tools heavily if incident load is high.",
  },
  {
    id: "ctx-research-old-timeline",
    teamIds: ["research"], category: "project",
    attribution: "Priya N. in #research (superseded)",
    title: "Older #research thread with a different eval timeline (superseded)",
    summary: "An earlier Slack thread discussed starting expanded evals a month later with a smaller benchmark set. The approved Q4 Research Plan explicitly supersedes this timeline. Shown for traceability only.",
    kind: "correspondence",
    claimType: "stated_plan",
    effectiveFrom: addDays(period.start, 14),
    expectedEffect: "unknown", confidence: "low",
    supersededBy: "ctx-research-eval-expansion",
    sources: [
      { documentId: "msg-research-0918", title: "Slack #research thread", excerpt: "thinking we kick off the bigger eval sweep next month once the new harness lands, probably just two suites to start", locator: "#research", date: addDays(period.start, -35), kind: "correspondence", integration: "slack", author: "Priya N." },
    ],
    uncertainty: "Superseded. Do not use for projections.",
  },
  {
    id: "ctx-engineering-migration",
    teamIds: ["engineering"], scope: "team", category: "project",
    magnitude: { basis: "no stated change; the trend carries" },
    attribution: "Dana K., engineering status note",
    title: "Observability migration continues through the quarter",
    summary: "An engineering note confirms the observability platform migration continues at its current pace through the end of the quarter, with no planned change in coding-tool or API usage.",
    kind: "project_doc",
    claimType: "stated_plan",
    effectiveFrom: addDays(period.start, -56), effectiveTo: quarterEnd,
    expectedEffect: "neutral", confidence: "medium",
    sources: [
      { documentId: "doc-eng-note-migration", title: "Engineering note: observability migration status", excerpt: "Migration is on track; we expect steady effort through the quarter with no staffing change.", locator: "Status · week 3", date: addDays(period.start, -10), kind: "project_doc", integration: "google_docs", author: "Dana K." },
    ],
  },
  ...personSignals.map((x) => x.item),
  macro.item,
  ...teamEvidence,
  renovation.item,
  cheaperModel.item,
  onboardingWave.item,
  ...companyWide.items,
];

// Every available projection (team and person) now carries its trend baseline and signed evidence adjustments;
// the fixed projections (85k / 50k / 65k and the person splits) are unchanged, baseline = projected − Σ adjustments.
attachAdjustments(forecasts, context, people);
const teamForecast = (teamId: string) => forecasts.find((f) => f.teamId === teamId && !f.personId);
const evidenceCount = context.filter((c) => !c.supersededBy).length;
const companyEvidenceCount = context.filter((c) => c.scope === "company" && !c.supersededBy).length;

/** Readable source documents behind the context items. */
export const documents: CompanyDocument[] = [
  {
    id: "doc-q4-research-plan", title: "Q4 Research Plan (approved)", kind: "plan", date: addDays(planStart, -8), teamIds: ["research"],
    origin: "Uploaded PDF (Research leadership)", integration: "pdf",
    body: `# Q4 Research Plan\n\n## 2.3 Evaluation expansion\n\nNightly runs across HELM-lite, SWE-bench Verified, and the internal agentic suite begin **${monthDay(planStart)}** and continue through Q4. This plan supersedes the earlier timeline discussed in #research.\n\nExpected effect: evaluation token volume roughly doubles. Per-run cost is not estimated here.`,
  },
  {
    id: "doc-product-update-oct", title: "Product Roadmap Update", kind: "project_doc", date: addDays(period.start, -6), teamIds: ["product"],
    origin: "Notion (Roadmap · Q4, via connector)", integration: "notion",
    body: "# Product Roadmap Update\n\nv4 GA moves into **next quarter**. Focus shifts to stabilization and customer escalations. Feature development pauses except P0.",
  },
  {
    id: "msg-research-0918", title: "Slack #research thread", kind: "correspondence", date: addDays(period.start, -35), teamIds: ["research"],
    origin: "Slack (#research, via connector)", integration: "slack", supersededBy: "doc-q4-research-plan",
    body: "**Priya N.** 10:42 — thinking we kick off the bigger eval sweep next month once the new harness lands, probably just two suites to start\n\n**Sam R.** 10:45 — works for me, let's revisit when the Q4 plan is approved",
  },
  {
    id: "doc-eng-note-migration", title: "Engineering note: observability migration status", kind: "project_doc", date: addDays(period.start, -10), teamIds: ["engineering"],
    origin: "Google Docs (via connector)", integration: "google_docs",
    body: "# Observability migration: status\n\nMigration is on track; we expect steady effort through the quarter with no staffing change. Tooling usage should remain at current levels.",
  },
  {
    id: "mail-research-finance", title: "Email: Re: AI spend this week", kind: "correspondence", date: addDays(period.start, -2), teamIds: ["research"],
    origin: "Gmail (finance@northstar thread, via connector)", integration: "gmail",
    body: `**From:** Priya N. <priya@northstar.example>\n**To:** finance@northstar.example\n**Date:** ${monthDay(addDays(period.start, -2))}\n**Subject:** Re: AI spend this week\n\n---\n\nHeads up: the nightly eval sweep is live from this week, so our API line will run roughly 1.5× until the benchmark set is trimmed. Approval for the additional spend is attached.\n\nWe expect it to settle once the two slowest suites are cut, probably within two weeks.\n\nPriya`,
  },
  ...personSignals.map((x) => x.doc),
  macro.doc,
  {
    id: "msg-research-hiring-freeze", title: "Slack #research-leads: hiring update", kind: "correspondence", date: hiringFreezeFrom, teamIds: ["research"],
    origin: "Slack (#research-leads, via connector)", integration: "slack",
    body: `**Priya N.** ${monthDay(hiringFreezeFrom)} 11:20 — both researcher reqs are on hold until next quarter — don't provision seats for them, we'll revisit after close\n\n**People Ops** 11:26 — noted, the two seats are released back to the pool\n\n**Priya N.** 11:30 — the eval expansion is unaffected, that's existing people and existing keys`,
  },
  {
    id: "doc-eng-cutover-rehearsal", title: "monday.com: Observability migration board", kind: "project_doc", date: addDays(period.start, -4), teamIds: ["engineering"],
    origin: "monday.com (board item, via connector)", integration: "monday",
    body: `# Observability migration\n\n| Item | Owner | Date | Status |\n|---|---|---|---|\n| Cutover rehearsal | Dana K. | ${monthDay(rehearsalFrom)} | Scheduled |\n| Cutover | Dana K. | next quarter | Planned |\n\nReplay one day of production traffic through the new pipeline; triage diffs with the assistant. Expect a weekend of elevated API usage from the triage passes.`,
  },
  renovation.doc,
  cheaperModel.doc,
  onboardingWave.doc,
  ...companyWide.docs,
];

export const proposals: AllocationProposal[] = [];
export const decisions: Decision[] = [];

export const threads: Record<string, AssistantMessage[]> = {
  main: [
    {
      id: "msg-welcome", threadId: "main", role: "assistant",
      createdAt: `${asOf}T09:05:00Z`,
      content: `This week Research is projected at **$85k against a $60k allocation**, and Product at **$50k against $80k**. The projections take ${evidenceCount} evidence items into account (${companyEvidenceCount} company-wide, the rest about teams and named people). I can redistribute the existing envelope, or allocate new funding if finance authorizes it.`,
    },
  ],
};

const allSources = () => context.filter((c) => !c.supersededBy).flatMap((c) => c.sources);
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
const genericReply = makeGenericReply(teams, forecasts, context, people);
export const scriptedReply: ScriptedReplyFn = withBudgetRequestConsideration((content, state, conversationContext) => {
  const intent = interpretActionIntent(content, teams, { context: conversationContext, proposals: state.proposals, planningPeriod: period });
  if (intent.action === "clarify" || intent.ask) return { message: { content: intent.ask!, conversationContext: intent.context } };
  if ((intent.action === "addition" && (intent.amount !== "50000" || intent.targetTeamId || intent.reviseProposalId)) || (intent.action === "transfer" && (intent.amount || intent.sourceTeamId || intent.targetTeamId || intent.reviseProposalId))) return genericReply(content, state, conversationContext);
  const text = content.toLowerCase();
  const b = (id: string) => state.budgets.find((x) => x.teamId === id)!.allocated;
  const total = state.budgets.reduce((s, x) => s + x.allocated, 0);
  const now = nextDemoTimestamp();
  const base = {
    unit: "usd" as const, period, createdAt: now, status: "proposed" as const,
    basedOnBudgetVersion: state.budgetVersion,
    forecastsReviewed: structuredClone(forecasts),
  };

  if (/compare/.test(text)) {
    return {
      message: {
        conversationContext: intent.context,
        content: `**Research** is projected at **$85k against $60k** (likely over): nightly evaluation runs under the approved Q4 plan have run every day this week. **Product** is projected at **$50k against $80k** (under) after the v4 launch moved to next quarter and three people paused for the office renovation. **Engineering** is projected at **$65k against $60k** with steady migration work.\n\nNet: the company is projected at $200k against a $200k envelope, but the team split no longer matches where the work is. Each projection is its trend baseline plus ${evidenceCount} evidence items: ${teams.map((t) => `${t.name} ${signedMoney((teamForecast(t.id)?.projected ?? 0) - (teamForecast(t.id)?.baseline ?? 0))}`).join(", ")}.`,
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
        conversationContext: intent.context,
        content: "I can't run that scenario yet. The forecasting service has not supplied a conditional projection for that assumption, and I won't invent a number. I can show the current projection and its range, or prepare an allocation proposal against it.",
        toolCalls: [{ name: "run_forecast", summary: "Requested scenario; forecasting returned unsupported" }],
      },
    };
  }

  if (intent.action === "addition") {
    const proposal: AllocationProposal = {
      ...base,
      id: `prop_${crypto.randomUUID()}`, version: 1,
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
        conversationContext: { ...intent.context, selected_proposal_id: proposal.id, selected_proposal_version: proposal.version },
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

  if (intent.action === "transfer") {
    const proposal: AllocationProposal = {
      ...base,
      id: `prop_${crypto.randomUUID()}`, version: 1,
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
        conversationContext: { ...intent.context, selected_proposal_id: proposal.id, selected_proposal_version: proposal.version },
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
        conversationContext: intent.context,
        content: `Product is running under because the **product roadmap update** moved the v4 launch into next quarter. Feature work paused except P0, so daily coding-tool and API usage has run at roughly 0.6× the earlier pace, and Marcus, Chloe and Alice are paused for the office renovation until ${monthDay(renovationTo)}. The projection of **$50k against $80k** assumes stabilization work stays light through the weekend.${byPerson("product")}${evidenceLines(teamForecast("product"))}`,
        citations: [...context[1].sources, ...personSources("product"), ...companyWide.items.flatMap((c) => c.sources)],
        toolCalls: [
          { name: "get_spending", summary: "Compared Product daily spend this week with the prior baseline" },
          { name: "search_documents", summary: "Read Product Roadmap Update (p.1) and the #product renovation thread" },
          { name: "explain_forecast", summary: `Attributed ${signedMoney((teamForecast("product")?.projected ?? 0) - (teamForecast("product")?.baseline ?? 0))} of the projection to ${teamForecast("product")?.adjustments?.length ?? 0} evidence items` },
        ],
      },
    };
  }

  if (/why|explain|over|exceed/.test(text) && text.includes("research")) {
    return {
      message: {
        conversationContext: intent.context,
        content: `Research is running over because the **approved Q4 Research Plan** started nightly evaluation runs on three new benchmark suites on **${monthDay(planStart)}**. Daily API spend has been roughly 1.6× the earlier baseline every day since, and the runs continue over the weekend. Priya and Yuki moving the two slowest suites to a smaller model and the hiring freeze pull the other way, but not enough. An older thread proposed a smaller, later start, but the approved plan explicitly supersedes it.${byPerson("research")}${evidenceLines(teamForecast("research"))}`,
        citations: [...context[0].sources, ...personSources("research"), ...companyWide.items.flatMap((c) => c.sources)],
        toolCalls: [
          { name: "get_spending", summary: "Compared Research daily API spend this week with the prior baseline" },
          { name: "search_documents", summary: "Read Q4 Research Plan §2.3, the #research-leads hiring update and the older #research thread" },
          { name: "explain_forecast", summary: `Attributed ${signedMoney((teamForecast("research")?.projected ?? 0) - (teamForecast("research")?.baseline ?? 0))} of the projection to ${teamForecast("research")?.adjustments?.length ?? 0} evidence items` },
        ],
      },
    };
  }

  return {
    message: {
      conversationContext: intent.context,
      content: "I can help with two kinds of changes: **redistribute** the existing $200,000 weekly envelope between teams, or **add** new funding and allocate it. I can also explain why a team is tracking over or under. What would you like?",
    },
  };
}, teams);

/** The plan's canonical 3-team example as a Dataset (`?teams=northstar`). */
export const northstar: Dataset = {
  company, teams, people, budgets, spending, forecasts, context, documents, proposals, decisions, threads, scriptedReply,
};
