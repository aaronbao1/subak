/**
 * Scalable synthetic company generator: 0..16 teams, deterministic per team count.
 * The default demo company has DEFAULT_TEAM_COUNT teams; `?teams=N` overrides it and `?teams=northstar`
 * returns the plan's 3-team example (src/fixtures/index.ts).
 *
 * The calendar hangs off "today": the planning period is the current Monday-to-Sunday week, every day up to
 * yesterday is complete, today is partial, and the rest of the week is projected day by day. Eight earlier
 * weeks of spending history sit behind the period so the overview chart can scroll back and show growth.
 */
import type {
  AllocationProposal, AssistantMessage, Budget, Company, CompanyDocument, ContextItem, Decision, EffectMagnitude,
  EvidenceCategory, Forecast, ForecastAdjustment, ForecastDailyPoint, ForecastQuestionContext, Integration, Period, Person, SignalKind,
  SpendingRecord, Team, ToolCallSummary,
} from "@/lib/contracts";
import { interpretActionIntent, type ActionIntentContext } from "@/lib/action-intent";
import type { BudgetRequest } from "@/lib/contracts/budget-requests";

export interface Dataset {
  company: Company;
  teams: Team[];
  /** Everyone whose usage rolls up into a team. Spending and forecasts are attributed per person. */
  people: Person[];
  budgets: Budget[];
  spending: SpendingRecord[];
  forecasts: Forecast[];
  context: ContextItem[];
  documents: CompanyDocument[];
  proposals: AllocationProposal[];
  decisions: Decision[];
  threads: Record<string, AssistantMessage[]>;
  scriptedReply: ScriptedReplyFn;
}

export type ScriptedReplyFn = (
  content: string,
  state: { proposals: AllocationProposal[]; budgets: Budget[]; budgetVersion: string; budgetRequests?: BudgetRequest[] },
  conversationContext?: ActionIntentContext,
  forecastContext?: ForecastQuestionContext,
) => { message: Omit<AssistantMessage, "id" | "threadId" | "role" | "createdAt">; proposal?: AllocationProposal };

export const MAX_TEAMS = 16;
export const DEFAULT_TEAM_COUNT = 8;

/* ------------------------------------------------------------------ */
/* Calendar                                                            */
/* ------------------------------------------------------------------ */

const DAY_MS = 86_400_000;
const WEEK_MS = 7 * DAY_MS;
const toTs = (iso: string) => { const [y, m, d] = iso.split("-").map(Number); return Date.UTC(y, m - 1, d); };
const fromTs = (ts: number) => new Date(ts).toISOString().slice(0, 10);
export const addDays = (iso: string, n: number) => fromTs(toTs(iso) + n * DAY_MS);
const range = (from: string, to: string) => { const out: string[] = []; for (let ts = toTs(from); ts <= toTs(to); ts += DAY_MS) out.push(fromTs(ts)); return out; };
const weekday = (iso: string) => new Date(toTs(iso)).getUTCDay();
const isWeekend = (iso: string) => weekday(iso) === 0 || weekday(iso) === 6;
export const monthDay = (iso: string) => new Date(toTs(iso)).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });

/** One deterministic UTC clock for all synthetic observations and initial publications. */
export const DEMO_NOW = "2026-10-25T12:00:00Z";
export function demoCalendar(instant = DEMO_NOW) {
  const clock = new Date(instant);
  if (!Number.isFinite(clock.getTime())) throw new Error("Invalid demo clock");
  const asOf = clock.toISOString().slice(0, 10);
  const start = addDays(asOf, -((weekday(asOf) + 6) % 7));
  const period: Period = { start, end:addDays(start,6), label:`Week of ${monthDay(start)}` };
  const leaveStart = addDays(asOf,1);
  const leaveEnd = leaveStart > period.end ? addDays(period.end,7) : period.end;
  return {asOf,period,leaveStart,leaveEnd,partialFraction:Math.min(0.95,Math.max(0.15,(clock.getUTCHours()+clock.getUTCMinutes()/60)/24))};
}
const calendar = demoCalendar();
export const asOf = calendar.asOf;
export const period = calendar.period;
export const HISTORY_WEEKS = 8;
export const RECORDED_DATES = range(addDays(period.start,-7*HISTORY_WEEKS),asOf);
export const PROJECTED_DATES = range(asOf,period.end);
const PARTIAL_FRACTION = calendar.partialFraction;
let demoSequence = 0;
/** Monotonic interaction time, after every initial fixture message. */
export const nextDemoTimestamp = () => new Date(Date.parse(DEMO_NOW) + ++demoSequence * 1000).toISOString();
/** Weekend activity relative to a weekday. */
const WEEKEND = 0.35;
const dayWeight = (iso: string) => (isWeekend(iso) ? WEEKEND : 1);
const WEEK_WEIGHT = 5 + 2 * WEEKEND;
/** Expected spend on a day for a team that spends `weekly` per week. */
const expectedOn = (weekly: number, iso: string) => (weekly * dayWeight(iso)) / WEEK_WEIGHT;

export const money = (n: number) => `$${Math.round(n).toLocaleString("en-US")}`;

/* ------------------------------------------------------------------ */
/* Providers and models                                                */
/* ------------------------------------------------------------------ */

export type ProviderId = "anthropic" | "openai" | "google";
export const PROVIDER_LABEL: Record<ProviderId, string> = { anthropic: "Anthropic", openai: "OpenAI", google: "Google" };

/** API usage per provider is split across its models; `usdPerMTok` is a blended list price used to derive tokens. */
export const MODELS: Record<ProviderId, Array<{ model: string; share: number; usdPerMTok: number }>> = {
  anthropic: [
    { model: "Claude Opus 5.5", share: 0.45, usdPerMTok: 15 },
    { model: "Claude Sonnet 5.5", share: 0.4, usdPerMTok: 4 },
    { model: "Claude Haiku 5.5", share: 0.15, usdPerMTok: 1 },
  ],
  openai: [
    { model: "GPT-5.5", share: 0.65, usdPerMTok: 6 },
    { model: "GPT-5.5 mini", share: 0.35, usdPerMTok: 1 },
  ],
  google: [
    { model: "Gemini 3 Pro", share: 0.6, usdPerMTok: 5 },
    { model: "Gemini 3 Flash", share: 0.4, usdPerMTok: 0.6 },
  ],
};

const asProvider = (p: string): ProviderId => (p === "openai" || p === "google" ? p : "anthropic");
/** Every team runs most API usage on its main provider and about a third on a second one, chosen by team id. */
function secondaryProvider(primary: ProviderId, teamId: string): ProviderId {
  const h = [...teamId].reduce((a, c) => a + c.charCodeAt(0), 0);
  const others = (["anthropic", "openai", "google"] as ProviderId[]).filter((x) => x !== primary);
  return others[h % others.length];
}
const exportName = (p: ProviderId) => (p === "google" ? `Google Cloud billing export ${asOf}` : `${PROVIDER_LABEL[p]} cost report export ${asOf}`);

/* ------------------------------------------------------------------ */
/* Teams                                                               */
/* ------------------------------------------------------------------ */

const TEAM_POOL: Array<Pick<Team, "name" | "description" | "lead"> & { provider: string; mix: Partial<Record<SpendingRecord["component"], number>>; pace: number }> = [
  { name: "Research", description: "Model evaluation and applied research", lead: "Priya N.", provider: "anthropic", mix: { subscription: 1, included_usage: 1.2, extra_usage: 1.5, api: 5 }, pace: 1.45 },
  { name: "Product", description: "Customer-facing product features", lead: "Marcus L.", provider: "anthropic", mix: { subscription: 2.5, included_usage: 2, extra_usage: 0.4, api: 1.2 }, pace: 0.62 },
  { name: "Engineering", description: "Platform, infrastructure, internal tooling", lead: "Dana K.", provider: "openai", mix: { subscription: 1.5, included_usage: 1.2, extra_usage: 0.8, api: 2.2 }, pace: 1.08 },
  { name: "Data Science", description: "Analytics pipelines and experimentation", lead: "Wei Z.", provider: "openai", mix: { subscription: 1, included_usage: 1, extra_usage: 0.6, api: 3 }, pace: 1.2 },
  { name: "Security", description: "AppSec reviews and threat modeling", lead: "Tomás R.", provider: "anthropic", mix: { subscription: 1.2, included_usage: 1, extra_usage: 0.3, api: 0.8 }, pace: 0.9 },
  { name: "Marketing", description: "Content and campaign tooling", lead: "Jules O.", provider: "openai", mix: { subscription: 1, included_usage: 1, extra_usage: 0.2, api: 0.9 }, pace: 0.75 },
  { name: "Sales Engineering", description: "Technical evaluations, POCs, and RFP responses", lead: "Aisha B.", provider: "anthropic", mix: { subscription: 1.5, included_usage: 1.3, extra_usage: 0.5, api: 0.6 }, pace: 1.0 },
  { name: "Customer Support", description: "Ticket triage and reply drafting", lead: "Noor H.", provider: "openai", mix: { subscription: 2, included_usage: 1.8, extra_usage: 0.4, api: 2.5 }, pace: 1.3 },
  { name: "Design", description: "Product design and prototyping", lead: "Elena V.", provider: "anthropic", mix: { subscription: 1.2, included_usage: 1, extra_usage: 0.2, api: 0.3 }, pace: 0.7 },
  { name: "Developer Relations", description: "Docs, samples, community", lead: "Kofi A.", provider: "anthropic", mix: { subscription: 1, included_usage: 0.9, extra_usage: 0.4, api: 1.0 }, pace: 0.95 },
  { name: "Finance Ops", description: "Close automation and reporting", lead: "Hana S.", provider: "openai", mix: { subscription: 0.8, included_usage: 0.7, extra_usage: 0.1, api: 0.5 }, pace: 0.55 },
  { name: "Legal & Compliance", description: "Contract review assistance", lead: "Rafael M.", provider: "anthropic", mix: { subscription: 0.8, included_usage: 0.6, extra_usage: 0.1, api: 0.7 }, pace: 0.85 },
  { name: "Infrastructure", description: "Cloud, CI/CD, observability", lead: "Ingrid F.", provider: "openai", mix: { subscription: 1.4, included_usage: 1.2, extra_usage: 0.9, api: 1.8 }, pace: 1.1 },
  { name: "Growth", description: "Lifecycle experiments and onboarding", lead: "Diego P.", provider: "anthropic", mix: { subscription: 1, included_usage: 0.9, extra_usage: 0.5, api: 1.6 }, pace: 1.25 },
  { name: "QA & Release", description: "Test generation and release notes", lead: "Mei T.", provider: "openai", mix: { subscription: 1.2, included_usage: 1.1, extra_usage: 0.6, api: 1.1 }, pace: 0.9 },
  { name: "People Ops", description: "Recruiting and internal comms", lead: "Sam R.", provider: "anthropic", mix: { subscription: 0.7, included_usage: 0.6, extra_usage: 0.05, api: 0.3 }, pace: 0.6 },
];

const slug = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");

/** Deterministic PRNG so the same team count always renders the same company. */
function mulberry32(seed: number) {
  return () => {
    seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Evenly spaced calm hues so 16 teams stay distinguishable. First 5 reuse theme chart tokens. */
export function teamColor(index: number, total: number): string {
  if (total <= 5) return `var(--chart-${index + 1})`;
  const hue = Math.round((index * 360) / total + 20) % 360;
  return `oklch(0.62 0.13 ${hue})`;
}

/* ------------------------------------------------------------------ */
/* Spending and projections                                            */
/* ------------------------------------------------------------------ */

/**
 * Daily USD records for every recorded day. The records inside the planning period sum EXACTLY to
 * `periodTarget`; earlier weeks are scaled from the same daily rate, shrinking by `growth` per week back,
 * so scrolling into history shows the team's usage growing into the present. Exported so Northstar uses it.
 */
export function dailySeries(
  teamId: string,
  periodTarget: number,
  mix: Partial<Record<SpendingRecord["component"], number>>,
  provider: string,
  seed = 1,
  growth = 1.06,
  personId?: string,
): SpendingRecord[] {
  const rnd = mulberry32(seed);
  const primary = asProvider(provider);
  const secondary = secondaryProvider(primary, teamId);
  // API rows are split per model: most on the team's main provider, the rest on its secondary.
  const apiSlices = [
    ...MODELS[primary].map((m) => ({ provider: primary, ...m, share: m.share * 0.7 })),
    ...MODELS[secondary].map((m) => ({ provider: secondary, ...m, share: m.share * 0.3 })),
  ];
  const raw: Omit<SpendingRecord, "amount">[] = [];
  const weights: number[] = [];
  const prices: Array<number | undefined> = [];
  for (const date of RECORDED_DATES) {
    const partial = date === asOf;
    const weekIndex = Math.floor((toTs(date) - toTs(period.start)) / WEEK_MS); // 0 this week, -1 last week, ...
    const level = growth ** weekIndex * (partial ? PARTIAL_FRACTION : 1);
    for (const [component, w] of Object.entries(mix) as [SpendingRecord["component"], number][]) {
      // Seat fees are flat across the week; usage follows the weekday/weekend rhythm with some noise.
      const activity = component === "subscription" ? level : level * dayWeight(date) * (0.8 + rnd() * 0.4);
      const common = {
        teamId, ...(personId ? { personId } : {}), date, component, unit: "usd" as const, complete: !partial,
        provenance: (component === "included_usage" ? "usage_only" : "simulated") as SpendingRecord["provenance"],
      };
      if (component === "api") {
        for (const slice of apiSlices) {
          weights.push(w * activity * slice.share * (0.9 + rnd() * 0.2));
          prices.push(slice.usdPerMTok);
          raw.push({
            ...common,
            id: `${personId ?? teamId}-${date}-api-${slug(slice.model)}`,
            provider: slice.provider, model: slice.model,
            source: `Synthetic demo: ${exportName(slice.provider)}`,
          });
        }
        continue;
      }
      weights.push(w * activity);
      prices.push(undefined);
      raw.push({
        ...common,
        id: `${personId ?? teamId}-${date}-${component}`,
        provider: primary,
        source: `Synthetic demo: ${component === "subscription" ? exportName(primary) : `Cursor Admin API export ${asOf}`}`,
      });
    }
  }
  if (periodTarget <= 0 || raw.length === 0) return raw.map((r) => ({ ...r, amount: 0 }));
  const inPeriod = raw.map((r) => r.date >= period.start && r.component !== "included_usage" && r.component !== "unpriced_usage");
  const periodWeight = weights.reduce((s, w, i) => s + (inPeriod[i] ? w : 0), 0);
  if (periodWeight <= 0) return raw.map(r => ({...r,amount:0}));
  const out = raw.map((r, i) => ({ ...r, amount: Math.round((weights[i] / periodWeight) * periodTarget) }));
  const lastInPeriod = inPeriod.lastIndexOf(true);
  out[lastInPeriod].amount += periodTarget - out.reduce((s, r, i) => s + (inPeriod[i] ? r.amount : 0), 0);
  // Tokens follow from dollars at the model's blended list price.
  return out.map((r, i) => (prices[i] ? { ...r, tokens: Math.round((r.amount / prices[i]!) * 1_000_000) } : r));
}

/** Spend recorded on complete days inside the period; the partial day is excluded because its projection replaces it. */
export function completeSpent(spending: SpendingRecord[], teamId: string, personId?: string) {
  return spending
    .filter((r) => r.teamId === teamId && (personId === undefined || r.personId === personId) && r.component !== "included_usage" && r.component !== "unpriced_usage" && r.provenance !== "usage_only" && r.complete && r.date >= period.start && r.date <= period.end)
    .reduce((s, r) => s + r.amount, 0);
}

/**
 * Split a team amount across people by weight so the parts sum EXACTLY to `total`; the rounding residual
 * lands on the heaviest share. Used for spending targets and for fixed projections alike.
 */
export function splitExact(total: number, weights: number[], step = 1): number[] {
  const sum = weights.reduce((a, b) => a + b, 0);
  if (weights.length === 0 || sum <= 0) return weights.map(() => 0);
  const parts = weights.map((w) => Math.round((w / sum) * total / step) * step);
  const top = weights.reduce((bi, w, i, arr) => (w > arr[bi] ? i : bi), 0);
  parts[top] += total - parts.reduce((a, b) => a + b, 0);
  return parts;
}

/**
 * Spread the projection for the incomplete days (and its range) over PROJECTED_DATES by weekday weight;
 * sums exactly to `remaining`, which is the full-period projection minus spend on complete days.
 */
export function dailyProjection(remaining: number, lowRemaining?: number, highRemaining?: number): ForecastDailyPoint[] {
  const weights = PROJECTED_DATES.map(dayWeight);
  const total = weights.reduce((a, b) => a + b, 0);
  const spread = (amount: number) => {
    const parts = weights.map((w) => Math.round((w / total) * amount));
    parts[0] += amount - parts.reduce((s, x) => s + x, 0);
    return parts;
  };
  const p = spread(Math.max(0, remaining));
  const lo = typeof lowRemaining === "number" ? spread(Math.max(0, lowRemaining)) : undefined;
  const hi = typeof highRemaining === "number" ? spread(Math.max(0, highRemaining)) : undefined;
  return PROJECTED_DATES.map((date, i) => ({ date, projected: p[i], ...(lo ? { low: lo[i] } : {}), ...(hi ? { high: hi[i] } : {}) }));
}


/* ------------------------------------------------------------------ */
/* People                                                              */
/* ------------------------------------------------------------------ */

const FIRST_NAMES = ["Ava", "Liam", "Maya", "Noah", "Zara", "Ethan", "Leila", "Omar", "Ines", "Theo", "Nadia", "Felix", "Yuki", "Arjun", "Sofia", "Mateo", "Hana", "Lucas", "Amara", "Jonas", "Chloe", "Ravi", "Elif", "Kai", "Nina", "Idris", "Freya", "Tariq", "Lena", "Mason"];
const LAST_INITIALS = ["A", "B", "C", "D", "E", "F", "G", "H", "J", "K", "L", "M", "N", "O", "P", "R", "S", "T", "V", "W"];
const ROLES = ["Senior engineer", "Engineer", "Staff engineer", "Analyst", "Designer", "Product manager", "Researcher", "Specialist"];
const TOOLS = ["Cursor", "Claude Code", "Cursor", "GitHub Copilot", "Claude Code"];

/**
 * The signal that explains how a person's usage is moving this week, and the channel it arrived through.
 * One of each kind per team (when the team is big enough) so every team page shows the pattern:
 * a manager pushing work back on Slack, an Asana task moving someone to a new model, a Monday item for time off.
 */
export interface PersonProfile {
  person: Person;
  /** Share of the team's usage (relative weight). */
  share: number;
  signal: SignalKind;
  integration: Integration;
  /** This-week usage relative to the prior baseline, applied to the projected days. */
  modifier: number;
  /** Week-over-week growth used for history; <1 means earlier weeks were higher (usage dropped). */
  growth: number;
  /**
   * An evidence-driven change to the projected days from a date: e.g. a paused project (factor 0.4 from the day
   * the floor closed). Applied on top of `modifier`; history is untouched.
   */
  override?: { from: string; factor: number };
}

/** Grouping and stated size for the single-person signals `personContext` produces. */
const SIGNAL_CATEGORY: Record<SignalKind, EvidenceCategory> = {
  project_deferred: "project", project_accelerated: "project", project_paused: "project",
  model_change: "model", tool_change: "policy", pricing_change: "pricing", policy_change: "policy",
  out_of_office: "staffing", onboarding: "staffing", steady: "project",
};
const SIGNAL_MAGNITUDE: Partial<Record<SignalKind, EffectMagnitude>> = {
  project_deferred: { pct: -45, basis: "one person at last week's rate while the build is on hold" },
  model_change: { pct: 40, basis: "comparison runs at full context on the new model until prompts are tuned" },
  out_of_office: { pct: -90, basis: "near-zero usage during the scheduled leave dates" },
  project_accelerated: { pct: 25, basis: "extra generation and review passes before the pulled-in due date" },
  onboarding: { pct: 15, basis: "a new seat ramping toward the team's median rate" },
};

const SIGNAL_PLAN: Array<{ signal: SignalKind; integration: Integration; modifier: number; growth: number }> = [
  { signal: "steady", integration: "document", modifier: 1, growth: 1.05 },
  { signal: "project_deferred", integration: "slack", modifier: 0.55, growth: 0.84 },
  { signal: "model_change", integration: "asana", modifier: 1.4, growth: 1.18 },
  { signal: "out_of_office", integration: "monday", modifier: 0.12, growth: 1.02 },
  { signal: "project_accelerated", integration: "asana", modifier: 1.25, growth: 1.12 },
  { signal: "onboarding", integration: "slack", modifier: 1.15, growth: 1.3 },
];

export function makePeople(team: Team, teamIndex: number, teamGrowth: number): PersonProfile[] {
  const rnd = mulberry32(500 + teamIndex * 7);
  const count = 3 + Math.floor(rnd() * 4); // 3..6
  const out: PersonProfile[] = [];
  for (let i = 0; i < count; i++) {
    const isLead = i === 0 && !!team.lead;
    const name = isLead ? team.lead! : `${FIRST_NAMES[(teamIndex * 5 + i * 3) % FIRST_NAMES.length]} ${LAST_INITIALS[(teamIndex * 3 + i * 7) % LAST_INITIALS.length]}.`;
    const plan = SIGNAL_PLAN[i % SIGNAL_PLAN.length];
    const integrations: Integration[] = ["slack", ...(i % 2 === 0 ? ["asana" as const] : ["monday" as const])];
    if (!integrations.includes(plan.integration) && plan.integration !== "document") integrations.push(plan.integration);
    const person: Person = {
      id: `${team.id}-${slug(name)}`,
      teamId: team.id,
      name,
      role: isLead ? "Lead" : ROLES[(teamIndex + i * 5) % ROLES.length],
      email: `${slug(name).replace(/-/g, ".")}@northstar.example`,
      integrations,
      primaryTool: TOOLS[(teamIndex + i) % TOOLS.length],
    };
    out.push({
      person,
      share: isLead ? 0.8 : 0.6 + rnd() * 0.9,
      signal: plan.signal,
      integration: plan.integration,
      modifier: plan.modifier,
      growth: plan.signal === "steady" ? teamGrowth : plan.growth,
    });
  }
  return out;
}

const SIGNAL_EFFECT: Record<SignalKind, ContextItem["expectedEffect"]> = {
  project_deferred: "decrease", project_accelerated: "increase", model_change: "increase", tool_change: "unknown",
  out_of_office: "decrease", onboarding: "increase", steady: "neutral",
  pricing_change: "increase",
  policy_change: "unknown",
  project_paused: "decrease",
};

/**
 * One context item (and its readable source) per person signal, phrased the way the connector would surface it:
 * a Slack message from the manager, an Asana task, a Monday board item.
 */
export function personContext(team: Team, profile: PersonProfile, managerName: string, newModel: string): { item: ContextItem; doc: CompanyDocument } | undefined {
  const { person, signal } = profile;
  const first = person.name.split(" ")[0];
  const base = {
    teamIds: [team.id], personIds: [person.id], scope: "person" as const, signal, expectedEffect: SIGNAL_EFFECT[signal],
    category: SIGNAL_CATEGORY[signal], ...(SIGNAL_MAGNITUDE[signal] ? { magnitude: SIGNAL_MAGNITUDE[signal] } : {}),
  };
  const since = addDays(period.start, -3);
  const docId = `doc-${person.id}-${signal}`;
  switch (signal) {
    case "project_deferred":
      return {
        item: {
          ...base, id: `ctx-${person.id}-deferred`, kind: "correspondence", claimType: "stated_plan", confidence: "high",
          attribution: `${managerName} in a Slack DM`,
          title: `${first} asked to push the build back and stay on the design doc`,
          summary: `${managerName} told ${first} in Slack to hold the implementation work and spend another week on the design document, so ${first}'s coding-tool and API usage drops for the rest of this week.`,
          effectiveFrom: since, effectiveTo: addDays(period.end, 7),
          sources: [{ documentId: docId, title: `Slack DM: ${managerName} → ${first}`, integration: "slack", author: managerName, date: since, kind: "correspondence",
            excerpt: `let's push the build back a week — stay on the design doc until review signs off, no need to spin up the harness yet` }],
          uncertainty: "If review signs off early the build could restart before the week ends.",
        },
        doc: { id: docId, title: `Slack DM: ${managerName} → ${first}`, kind: "correspondence", date: since, teamIds: [team.id], personIds: [person.id], integration: "slack", origin: `Slack (DM, via connector)`,
          body: `**${managerName}** ${monthDay(since)} 9:12 — let's push the build back a week — stay on the design doc until review signs off, no need to spin up the harness yet\n\n**${person.name}** 9:15 — got it, I'll keep the draft moving and pause the implementation branch` },
      };
    case "model_change":
      return {
        item: {
          ...base, id: `ctx-${person.id}-model`, kind: "project_doc", claimType: "stated_plan", confidence: "high",
          attribution: `${person.name}'s Asana task`,
          title: `${first} is moving the pipeline to ${newModel}`,
          summary: `An Asana task assigned to ${first} migrates the team's main workflow to ${newModel} this week. Early runs use longer contexts, so ${first}'s API usage runs well above the prior baseline until the prompts are tuned.`,
          effectiveFrom: since, effectiveTo: addDays(period.end, 14),
          sources: [{ documentId: docId, title: `Asana: Migrate pipeline to ${newModel}`, integration: "asana", author: person.name, date: since, kind: "project_doc", locator: "task · In progress",
            excerpt: `Switch default model to ${newModel}; re-run the regression set at full context before cutting over.` }],
          uncertainty: "Per-token price of the new model is not confirmed in the task; the forecast assumes current list pricing.",
        },
        doc: { id: docId, title: `Asana: Migrate pipeline to ${newModel}`, kind: "project_doc", date: since, teamIds: [team.id], personIds: [person.id], integration: "asana", origin: "Asana (project task, via connector)",
          body: `# Migrate pipeline to ${newModel}\n\n**Assignee:** ${person.name} · **Status:** In progress · **Due:** ${monthDay(period.end)}\n\nSwitch default model to ${newModel}; re-run the regression set at full context before cutting over. Expect higher token volume during the comparison runs.` },
      };
    case "out_of_office":
      return {
        item: {
          ...base, id: `ctx-${person.id}-ooo`, kind: "correspondence", claimType: "observed_event", confidence: "high",
          attribution: "monday.com availability board",
          title: `${first} is out of office from ${monthDay(addDays(asOf, 1))}`,
          summary: `The team's Monday board marks ${first} out of office from ${monthDay(calendar.leaveStart)} through ${monthDay(calendar.leaveEnd)}, so usage falls during those dates.`,
          effectiveFrom: calendar.leaveStart, effectiveTo: calendar.leaveEnd,
          sources: [{ documentId: docId, title: "monday.com: Team availability board", integration: "monday", author: person.name, date: addDays(asOf, -2), kind: "correspondence", locator: "row · Out of office",
            excerpt: `${person.name} — Out of office ${monthDay(calendar.leaveStart)} to ${monthDay(calendar.leaveEnd)}` }],
        },
        doc: { id: docId, title: "monday.com: Team availability board", kind: "correspondence", date: addDays(asOf, -2), teamIds: [team.id], personIds: [person.id], integration: "monday", origin: "monday.com (board item, via connector)",
          body: `# Team availability\n\n| Person | Status | Dates |\n|---|---|---|\n| ${person.name} | Out of office | ${monthDay(calendar.leaveStart)} – ${monthDay(calendar.leaveEnd)} |` },
      };
    case "project_accelerated":
      return {
        item: {
          ...base, id: `ctx-${person.id}-accel`, kind: "project_doc", claimType: "stated_plan", confidence: "medium",
          attribution: `${managerName} in Asana`,
          title: `${first}'s deadline moved up to this week`,
          summary: `An Asana task owned by ${first} had its due date pulled into this week, so ${first} is running more generation and review passes than usual.`,
          effectiveFrom: since, effectiveTo: period.end,
          sources: [{ documentId: docId, title: "Asana: Due date changed", integration: "asana", author: managerName, date: since, kind: "project_doc", locator: "task · activity",
            excerpt: `${managerName} changed the due date to ${monthDay(period.end)} (was next sprint)` }],
          uncertainty: "The task does not say how much of the work is already done.",
        },
        doc: { id: docId, title: "Asana: Due date changed", kind: "project_doc", date: since, teamIds: [team.id], personIds: [person.id], integration: "asana", origin: "Asana (task activity, via connector)",
          body: `# Task activity\n\n**${managerName}** changed the due date to **${monthDay(period.end)}** (was next sprint).\n\n**${person.name}** commented: pulling in the remaining review passes this week.` },
      };
    case "onboarding":
      return {
        item: {
          ...base, id: `ctx-${person.id}-onboarding`, kind: "correspondence", claimType: "observed_event", confidence: "medium",
          attribution: `${managerName} in #${team.id}`,
          title: `${first} joined the team this month and is ramping up`,
          summary: `A Slack welcome thread shows ${first} started recently; usage is climbing week over week as ${first} picks up the team's tooling.`,
          effectiveFrom: addDays(period.start, -21), effectiveTo: addDays(period.end, 21),
          sources: [{ documentId: docId, title: `Slack #${team.id}: welcome thread`, integration: "slack", author: managerName, date: addDays(period.start, -21), kind: "correspondence",
            excerpt: `welcome ${first}! seats for Cursor and the API workspace are set up, pair with the lead this week` }],
        },
        doc: { id: docId, title: `Slack #${team.id}: welcome thread`, kind: "correspondence", date: addDays(period.start, -21), teamIds: [team.id], personIds: [person.id], integration: "slack", origin: `Slack (#${team.id}, via connector)`,
          body: `**${managerName}** — welcome ${first}! seats for Cursor and the API workspace are set up, pair with the lead this week\n\n**${person.name}** — thanks, excited to be here` },
      };
    default:
      return undefined;
  }
}

/** Company-wide (macro) change: a new model everyone is moving to. Attached to every team, no single person. */
export function macroModelContext(teams: Team[], newModel: string): { item: ContextItem; doc: CompanyDocument } {
  const since = addDays(period.start, -2);
  const docId = "doc-company-new-model";
  return {
    item: {
      id: "ctx-company-new-model", teamIds: teams.map((t) => t.id), personIds: [], scope: "company", signal: "model_change",
      kind: "correspondence", claimType: "stated_plan", confidence: "medium",
      category: "model", attribution: "Platform lead in #announcements",
      magnitude: { pct: 6, basis: "early adopters' comparison runs; assumes one in four pipelines trials the model this period" },
      title: `${newModel} is generally available; teams are told to migrate`,
      summary: `An #announcements post from the platform lead says ${newModel} is available in the company workspace and asks teams to migrate by the end of the quarter. Early adopters run comparison passes, which raises usage before it settles.`,
      effectiveFrom: since, effectiveTo: addDays(period.end, 63), expectedEffect: "increase",
      sources: [{ documentId: docId, title: "Slack #announcements: new model available", integration: "slack", author: "Platform lead", date: since, kind: "correspondence",
        excerpt: `${newModel} is live in the workspace. Please migrate pipelines by end of quarter; expect higher token use during comparison runs.` }],
      uncertainty: "How many teams migrate this week, and the new model's effective price per token, are not stated.",
    },
    doc: { id: docId, title: "Slack #announcements: new model available", kind: "correspondence", date: since, teamIds: teams.map((t) => t.id), integration: "slack", origin: "Slack (#announcements, via connector)",
      body: `**Platform lead** ${monthDay(since)} — ${newModel} is live in the workspace. Please migrate pipelines by end of quarter; expect higher token use during comparison runs. Pricing follows the provider's list rate.` },
  };
}

export const NEW_MODEL = "Claude Opus 5.5";

/* ------------------------------------------------------------------ */
/* Company-scope evidence (macro / pricing / policy / model)           */
/* ------------------------------------------------------------------ */

/** "Ava K., Liam B. and Maya C." */
export const listNames = (people: Person[]) => {
  const names = people.map((p) => p.name);
  return names.length <= 1 ? names.join("") : `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
};

/**
 * Company-wide evidence every team carries, beyond the model announcement from `macroModelContext`: a provider
 * price rise due next week, a policy opening the new model to everyone, an observed seat consolidation, a finance
 * freeze on new API keys, and one assistant interpretation that reads two of those together. All demo documents;
 * no real provider prices or announcements are quoted.
 */
export function companyEvidence(teams: Team[], newModel: string): { items: ContextItem[]; docs: CompanyDocument[] } {
  const all = teams.map((t) => t.id);
  const nextMonday = addDays(period.end, 1);
  const policyFrom = addDays(period.start, 3);
  const quarterEnd = addDays(period.end, 63);
  const seatRemoval = addDays(period.start, -3);
  const noticeDate = addDays(asOf, -1);
  const common = { teamIds: all, personIds: [] as string[], scope: "company" as const };
  const items: ContextItem[] = [
    {
      ...common, id: "ctx-company-pricing-update", category: "pricing", signal: "pricing_change", kind: "correspondence",
      claimType: "stated_plan", confidence: "high", expectedEffect: "increase",
      title: `Provider raises frontier-model API prices from ${monthDay(nextMonday)}`,
      summary: `A provider pricing notice says per-token rates for its frontier model class rise by about 8% from ${monthDay(nextMonday)}. Nothing changes inside this period; from next week the same token volume costs more unless teams shift their model mix toward the smaller models, whose rates are unchanged.`,
      effectiveFrom: nextMonday,
      magnitude: { pct: 8, basis: "frontier-class API rows at the new list rate; model mix unchanged. Starts after this period, so it moves next week's number, not this one" },
      attribution: "Provider pricing update",
      sources: [{ documentId: "doc-company-pricing-update", title: "Provider pricing update", integration: "email", author: "Provider billing notice", date: noticeDate, kind: "correspondence", locator: "Notice · effective dates",
        excerpt: `Effective ${monthDay(nextMonday)}, input and output rates for the frontier model class increase by approximately 8%. Rates for the mid-size and small models are unchanged.` }],
      uncertainty: "Only the frontier class is affected. Each team's exposure is the frontier share of its API rows in the usage export, which varies from under a tenth to over half.",
    },
    {
      ...common, id: "ctx-company-model-policy", category: "policy", signal: "policy_change", kind: "plan",
      claimType: "stated_plan", confidence: "low", expectedEffect: "increase",
      title: `${newModel} approved for all employees from ${monthDay(policyFrom)}`,
      summary: `An IT policy update opens ${newModel} to every employee from ${monthDay(policyFrom)}; until then only the pilot teams could call it. The projection assumes one in five API calls moves to it in the first week at list price. If teams wait for the migration guide, the first-week effect is close to zero.`,
      effectiveFrom: policyFrom, effectiveTo: quarterEnd,
      magnitude: { pct: 5, basis: "assumes one in five API calls moves to the newly allowed model in week one, at list price" },
      attribution: "IT policy page",
      sources: [{ documentId: "doc-company-model-policy", title: "Approved AI models and tools", integration: "notion", author: "IT security", date: addDays(policyFrom, -2), kind: "plan", locator: "§3 Approved models",
        excerpt: `${newModel} moves from pilot to approved for all employees on ${monthDay(policyFrom)}. No request is needed; it appears in the shared workspace automatically.` }],
      uncertainty: "Adoption is an assumption, not a measurement. Revisit once two full days of usage on the new model are in the export.",
    },
    {
      ...common, id: "ctx-company-seat-consolidation", category: "policy", signal: "tool_change", kind: "project_doc",
      claimType: "observed_event", confidence: "high", expectedEffect: "decrease",
      title: "IT removed 40 idle coding-assistant seats",
      summary: `The admin console export shows 40 seats with no activity in 60 days were removed on ${monthDay(seatRemoval)}, consolidating two coding-assistant tools onto one. Subscription rows fall from the removal date; usage rows are unaffected because the seats were idle.`,
      effectiveFrom: seatRemoval, effectiveTo: quarterEnd,
      magnitude: { pct: -3, basis: "subscription rows only: 40 idle seats at the seat rate, spread over every team" },
      attribution: "IT admin console export",
      sources: [{ documentId: "doc-company-seat-consolidation", title: "Seat consolidation export", integration: "document", author: "IT admin", date: seatRemoval, kind: "project_doc", locator: "Removed seats · 40 rows",
        excerpt: "40 seats removed (no activity in 60 days). Remaining seats: one coding assistant per person. Billing adjusts from the removal date." }],
    },
    {
      ...common, id: "ctx-company-api-key-freeze", category: "macro", signal: "policy_change", kind: "plan",
      claimType: "stated_plan", confidence: "medium", expectedEffect: "decrease",
      title: "Finance froze new API keys until the quarter closes",
      summary: `A finance memo stops issuing new API keys and raising rate limits until the quarter closes on ${monthDay(quarterEnd)}. Existing workloads continue unchanged; new workloads that would have started this period do not, which trims every team's growth slightly.`,
      effectiveFrom: period.start, effectiveTo: quarterEnd,
      magnitude: { pct: -4, basis: "new workloads that would have started this period do not; existing keys unaffected" },
      attribution: "Finance memo",
      sources: [{ documentId: "doc-company-api-key-freeze", title: "Finance memo: API key freeze", integration: "gmail", author: "Finance", date: addDays(period.start, -1), kind: "plan", locator: "finance@northstar · all-hands",
        excerpt: `No new API keys or rate-limit increases will be issued until the quarter closes on ${monthDay(quarterEnd)}. Existing keys keep working. Exceptions go through the CFO.` }],
      uncertainty: "Teams may route new work through existing keys, in which case the freeze changes attribution rather than spend.",
    },
    {
      ...common, id: "ctx-company-frontload-interpretation", category: "macro", signal: "model_change", kind: "research_note",
      claimType: "interpretation", confidence: "low", expectedEffect: "increase",
      title: "Teams likely front-load comparison runs before the price change",
      summary: `The assistant's reading of two items together: with the migration ask open and a frontier price rise due ${monthDay(nextMonday)}, teams that planned comparison runs are likely to run them this period at the current rate. This is an interpretation, not something any team has stated.`,
      effectiveFrom: asOf, effectiveTo: period.end,
      magnitude: { pct: 3, basis: "assistant's read of the migration ask plus the pricing notice; no team has stated it" },
      attribution: "Assistant interpretation of two sources",
      sources: [
        { documentId: "doc-company-pricing-update", title: "Provider pricing update", integration: "email", author: "Provider billing notice", date: noticeDate, kind: "correspondence", excerpt: `Effective ${monthDay(nextMonday)}, input and output rates for the frontier model class increase by approximately 8%.` },
        { documentId: "doc-company-new-model", title: "Slack #announcements: new model available", integration: "slack", author: "Platform lead", date: addDays(period.start, -2), kind: "correspondence", excerpt: "Please migrate pipelines by end of quarter; expect higher token use during comparison runs." },
      ],
      uncertainty: "Drop this item if the comparison runs do not show up in the next complete day's export.",
    },
  ];
  const docs: CompanyDocument[] = [
    {
      id: "doc-company-pricing-update", title: "Provider pricing update", kind: "correspondence", date: noticeDate, teamIds: all, integration: "email", origin: "Email notice from the provider (via connector)",
      body: `# Provider pricing update\n\n**From:** billing-notices@provider.example · **Date:** ${monthDay(noticeDate)}\n\nThis is a fictional notice. It does not quote any real provider's prices.\n\nEffective **${monthDay(nextMonday)}**, input and output rates for the frontier model class increase by approximately **8%**. Rates for the mid-size and small models are unchanged. Usage recorded before the effective date is billed at the current rate, including runs that start before midnight and finish after.\n\nCommitted-use agreements keep their contracted rate until renewal. Workspaces with a monthly spend cap keep the cap; the cap is reached sooner at the new rate.\n\nTo estimate the effect, multiply the frontier-class share of your API spend by 8%. Moving a workload to a mid-size model where quality allows avoids the increase entirely.`,
    },
    {
      id: "doc-company-model-policy", title: "Approved AI models and tools", kind: "plan", date: addDays(policyFrom, -2), teamIds: all, integration: "notion", origin: "Notion (IT security policy page, via connector)",
      body: `# Approved AI models and tools\n\n_Maintained by IT security._\n\n## 3. Approved models\n\n**${newModel}** moves from *pilot* to *approved for all employees* on **${monthDay(policyFrom)}**. No request is needed; it appears in the shared API workspace and in the coding assistants automatically. Until then it stays limited to the pilot teams.\n\nThe security review found no change to data handling: prompts and outputs stay inside the existing enterprise agreement, and the retention setting is unchanged.\n\n## 4. What this means for budgets\n\nThe model is priced above the mid-size tier. Finance should expect some workloads to move to it in the first weeks after approval; teams are asked to compare quality on their own evaluation sets before switching defaults.`,
    },
    {
      id: "doc-company-seat-consolidation", title: "Seat consolidation export", kind: "project_doc", date: seatRemoval, teamIds: all, integration: "document", origin: "Uploaded CSV from the admin console",
      body: `# Seat consolidation export\n\n_Exported ${monthDay(seatRemoval)} from the coding-assistant admin console._\n\n40 seats with no activity in the last 60 days were removed. Each affected person keeps one coding-assistant seat; the second tool's seats were the ones retired. Billing for the removed seats stops from the removal date and shows as a credit on the next invoice.\n\n| Team | Seats removed |\n|---|---|\n${teams.map((t, i) => `| ${t.name} | ${Math.max(1, Math.round(40 / Math.max(1, teams.length)) + (i % 2))} |`).join("\n")}\n\nUsage rows are not affected: the removed seats recorded no usage in the window, so the change shows only in the subscription component.`,
    },
    {
      id: "doc-company-api-key-freeze", title: "Finance memo: API key freeze", kind: "plan", date: addDays(period.start, -1), teamIds: all, integration: "gmail", origin: "Gmail (finance@northstar all-hands thread, via connector)",
      body: `**From:** Finance <finance@northstar.example>\n**To:** all-hands@northstar.example\n**Date:** ${monthDay(addDays(period.start, -1))}\n**Subject:** API key freeze until quarter close\n\n---\n\nTo land the quarter on plan, we are pausing the issue of new API keys and rate-limit increases from today until the quarter closes on **${monthDay(quarterEnd)}**. Existing keys keep working at their current limits.\n\nThis is not a usage cut. Work already running continues; what moves is the start of new workloads, which wait until the next quarter unless the CFO approves an exception.\n\nTeams planning a new workload this period: tell finance now so it is in the next quarter's allocation from day one.`,
    },
  ];
  return { items, docs };
}

/* ------------------------------------------------------------------ */
/* Person-scope evidence naming several people                         */
/* ------------------------------------------------------------------ */

export interface GroupEvidence { item: ContextItem; doc: CompanyDocument }

/**
 * The owner's example: three named people on one team have their project paused for an office renovation, so
 * their token usage drops while the floor is closed. Slack excerpt from the team lead.
 */
export function renovationEvidence(team: Team, members: Person[], from: string, to: string): GroupEvidence {
  const names = listNames(members);
  const lead = team.lead ?? `${team.name} lead`;
  const docId = `doc-${team.id}-renovation`;
  const posted = addDays(from, -2);
  return {
    item: {
      id: `ctx-${team.id}-renovation-pause`, teamIds: [team.id], personIds: members.map((p) => p.id), scope: "person",
      signal: "project_paused", category: "project", kind: "correspondence", claimType: "stated_plan", confidence: "high",
      title: `Office renovation pauses ${names} until ${monthDay(to)}`,
      summary: `${lead} posted in #${team.id} that the ${team.name} floor is closed for renovation from ${monthDay(from)} to ${monthDay(to)}. ${names} park their project until the floor reopens, so their coding-tool and API usage drops to the small amount of review work they can do from home.`,
      effectiveFrom: from, effectiveTo: to, expectedEffect: "decrease",
      magnitude: { pct: -60, basis: `${members.length} people at their last-week rate while paused` },
      attribution: `${lead} in #${team.id}`,
      sources: [{ documentId: docId, title: `Slack #${team.id}: floor closed for renovation`, integration: "slack", author: lead, date: posted, kind: "correspondence", locator: `#${team.id} · pinned`,
        excerpt: `floor is closed ${monthDay(from)}–${monthDay(to)} for the renovation — ${names}, park the build until we're back; no eval runs in the meantime` }],
      uncertainty: `If the contractor finishes early the project restarts before ${monthDay(to)}.`,
    },
    doc: {
      id: docId, title: `Slack #${team.id}: floor closed for renovation`, kind: "correspondence", date: posted, teamIds: [team.id], personIds: members.map((p) => p.id), integration: "slack", origin: `Slack (#${team.id}, via connector)`,
      body: `**${lead}** ${monthDay(posted)} 16:40 — floor is closed ${monthDay(from)}–${monthDay(to)} for the renovation — ${names}, park the build until we're back; no eval runs in the meantime\n\n**${members[0].name}** 16:44 — ok, I'll leave the branch where it is and do reviews from home\n\n**${members[members.length - 1].name}** 16:51 — same; facilities say ${monthDay(to)} is firm\n\n**${lead}** 16:53 — thanks, I'll tell finance the ${team.name} number drops for the week`,
    },
  };
}

/** Two or three people move the heaviest nightly runs to a smaller, cheaper model. */
export function modelSwitchEvidence(team: Team, members: Person[], cheaperModel: string): GroupEvidence {
  const names = listNames(members);
  const docId = `doc-${team.id}-cheaper-model`;
  const from = addDays(period.start, 1);
  return {
    item: {
      id: `ctx-${team.id}-cheaper-model`, teamIds: [team.id], personIds: members.map((p) => p.id), scope: "person",
      signal: "model_change", category: "model", kind: "correspondence", claimType: "stated_plan", confidence: "medium",
      title: `${names} move the nightly suite to ${cheaperModel}`,
      summary: `A #${team.id} thread shows ${names} moving the two slowest nightly suites to ${cheaperModel}, a smaller model at a fraction of the per-token rate. The same runs cost less from ${monthDay(from)}; quality on those suites is being spot-checked.`,
      effectiveFrom: from, effectiveTo: addDays(period.end, 63), expectedEffect: "decrease",
      magnitude: { pct: -15, basis: `${members.length} people's API rows at the smaller model's rate for the two suites` },
      attribution: `${members[0].name} in #${team.id}`,
      sources: [{ documentId: docId, title: `Slack #${team.id}: cheaper model for the slow suites`, integration: "slack", author: members[0].name, date: addDays(from, -1), kind: "correspondence",
        excerpt: `moving the two slowest suites to ${cheaperModel} from tomorrow — same harness, about a fifth of the token cost, I'll spot-check quality daily` }],
      uncertainty: "If the smaller model fails the spot checks the suites move back and the saving disappears.",
    },
    doc: {
      id: docId, title: `Slack #${team.id}: cheaper model for the slow suites`, kind: "correspondence", date: addDays(from, -1), teamIds: [team.id], personIds: members.map((p) => p.id), integration: "slack", origin: `Slack (#${team.id}, via connector)`,
      body: `**${members[0].name}** ${monthDay(addDays(from, -1))} 18:02 — moving the two slowest suites to ${cheaperModel} from tomorrow — same harness, about a fifth of the token cost, I'll spot-check quality daily\n\n**${members[members.length - 1].name}** 18:10 — I'll switch mine too; the long-context ones stay where they are\n\n**${team.lead ?? "Lead"}** 18:15 — good, flag it to finance as a saving for the week`,
    },
  };
}

/** Two or three people are onboarding buddies for new contractors; their seats carry the extra usage for two weeks. */
export function onboardingWaveEvidence(team: Team, members: Person[]): GroupEvidence {
  const names = listNames(members);
  const docId = `doc-${team.id}-onboarding-wave`;
  const from = period.start;
  const to = addDays(period.end, 7);
  return {
    item: {
      id: `ctx-${team.id}-onboarding-wave`, teamIds: [team.id], personIds: members.map((p) => p.id), scope: "person",
      signal: "onboarding", category: "staffing", kind: "correspondence", claimType: "observed_event", confidence: "medium",
      title: `${names} each pair with a new contractor from ${monthDay(from)}`,
      summary: `The monday.com onboarding board shows ${members.length} contractors starting on ${monthDay(from)}. ${names} are their onboarding buddies and share seats while accounts are provisioned, so their usage runs above the usual rate until ${monthDay(to)}.`,
      effectiveFrom: from, effectiveTo: to, expectedEffect: "increase",
      magnitude: { pct: 12, basis: `${members.length} buddies' seats carry the contractors' first two weeks of usage` },
      attribution: "monday.com onboarding board",
      sources: [{ documentId: docId, title: "monday.com: Onboarding board", integration: "monday", author: team.lead ?? "Team lead", date: addDays(from, -3), kind: "correspondence", locator: "rows · Starting this week",
        excerpt: `${members.map((p) => `${p.name} — buddy for contractor starting ${monthDay(from)}`).join("; ")}` }],
      uncertainty: "Contractor accounts may be provisioned early, moving the usage onto their own seats.",
    },
    doc: {
      id: docId, title: "monday.com: Onboarding board", kind: "correspondence", date: addDays(from, -3), teamIds: [team.id], personIds: members.map((p) => p.id), integration: "monday", origin: "monday.com (board rows, via connector)",
      body: `# Onboarding board\n\n| Buddy | Status | Start | Seats |\n|---|---|---|---|\n${members.map((p) => `| ${p.name} | Buddy for contractor | ${monthDay(from)} | Shared until ${monthDay(to)} |`).join("\n")}\n\nContractors use the buddy's seat and API key until their own accounts are provisioned, usually within two weeks.`,
    },
  };
}

/* ------------------------------------------------------------------ */
/* Evidence → projection adjustments                                   */
/* ------------------------------------------------------------------ */

/** Signed dollars with a real minus sign, for adjustment notes. */
export const signedMoney = (n: number) => `${n < 0 ? "−" : "+"}${money(Math.abs(n))}`;

/**
 * Share of this period's activity an item covers: day weights (weekend about a third of a weekday) inside
 * [effectiveFrom, effectiveTo] ∩ period, over the whole period's weight. 0 when the item starts after the period
 * ends (a price change effective next week), so it is listed as evidence but moves nothing this period.
 */
export function periodCoverage(item: Pick<ContextItem, "effectiveFrom" | "effectiveTo">): number {
  const from = item.effectiveFrom && item.effectiveFrom > period.start ? item.effectiveFrom : period.start;
  const to = item.effectiveTo && item.effectiveTo < period.end ? item.effectiveTo : period.end;
  if (from > to) return 0;
  return range(from, to).reduce((s, d) => s + dayWeight(d), 0) / WEEK_WEIGHT;
}

/** An item moves a person when it names them, or is a team/company item for their team, carries a pct and is current. */
function appliesTo(item: ContextItem, person: Person): boolean {
  if (item.supersededBy) return false;
  if (typeof item.magnitude?.pct !== "number" || item.magnitude.pct === 0) return false;
  if (item.scope === "person") return !!item.personIds?.includes(person.id);
  return item.teamIds.includes(person.teamId) && !(item.personIds?.length);
}

/**
 * ADJUSTMENT RULE. Evidence moves projections at the person level and rolls up:
 *  - An item applies to a person when it names them (scope "person"), or is a team item for their team, or a
 *    company item (every team). Only current items (no `supersededBy`) with a stated `magnitude.pct` count.
 *  - Each item's pct is scaled by `periodCoverage` (the share of this period inside its effective window) and
 *    applied to the person's trend baseline: amount = baseline × pct/100 × coverage. The baseline is recovered from
 *    the projection the fixture already carries, baseline = projected / Π(1 + pct·coverage/100), so every
 *    `projected` stays exactly as it was and projected === baseline + Σ amounts holds to the dollar (the rounding
 *    residual lands on the largest adjustment).
 *  - A team forecast's adjustment for an item is the sum of its people's amounts for that item. Company items
 *    therefore land on each team in proportion to its projected spend, and person items roll up exactly. The team
 *    baseline is the sum of its people's baselines.
 * Mutates the forecasts in place (adds `baseline` and `adjustments`), so callers keep their existing arrays.
 */
export function attachAdjustments(forecasts: Forecast[], context: ContextItem[], people: Person[]): void {
  const byTeam = new Map<string, Map<string, number>>(); // teamId → contextId → Σ of its people's amounts
  const itemById = new Map(context.map((c) => [c.id, c]));
  const noteFor = (id: string, amount: number) => `${itemById.get(id)?.title ?? id}: ${signedMoney(amount)}`;

  for (const f of forecasts) {
    if (!f.personId || f.status !== "available" || typeof f.projected !== "number") continue;
    const person = people.find((p) => p.id === f.personId);
    if (!person) continue;
    const items = context
      .filter((c) => appliesTo(c, person))
      .map((c) => ({ id: c.id, k: (c.magnitude!.pct! / 100) * periodCoverage(c) }))
      .filter((x) => x.k !== 0);
    const factor = items.reduce((s, x) => s * (1 + x.k), 1);
    const baseline = factor > 0 ? Math.round(f.projected / factor) : f.projected;
    const adjustments: ForecastAdjustment[] = items.map((x) => ({ contextId: x.id, amount: Math.round(baseline * x.k) }));
    if (adjustments.length) {
      const residual = f.projected - baseline - adjustments.reduce((s, a) => s + a.amount, 0);
      const top = adjustments.reduce((bi, a, i, arr) => (Math.abs(a.amount) > Math.abs(arr[bi].amount) ? i : bi), 0);
      adjustments[top].amount += residual;
    }
    const kept = adjustments.filter((a) => a.amount !== 0).map((a) => ({ ...a, note: noteFor(a.contextId, a.amount) }));
    f.adjustments = kept;
    f.baseline = f.projected - kept.reduce((s, a) => s + a.amount, 0);
    const teamMap = byTeam.get(f.teamId) ?? new Map<string, number>();
    for (const a of kept) teamMap.set(a.contextId, (teamMap.get(a.contextId) ?? 0) + a.amount);
    byTeam.set(f.teamId, teamMap);
  }

  for (const f of forecasts) {
    if (f.personId || f.status !== "available" || typeof f.projected !== "number") continue;
    const teamMap = byTeam.get(f.teamId) ?? new Map<string, number>();
    const adjustments: ForecastAdjustment[] = context
      .filter((c) => teamMap.has(c.id) && teamMap.get(c.id) !== 0)
      .map((c) => ({ contextId: c.id, amount: teamMap.get(c.id)!, note: noteFor(c.id, teamMap.get(c.id)!) }));
    f.adjustments = adjustments;
    f.baseline = f.projected - adjustments.reduce((s, a) => s + a.amount, 0);
  }
}

/** Bullet lines for the assistant: each adjustment on a team's forecast, citing its evidence id. */
export function evidenceLines(forecast: Forecast | undefined): string {
  const adj = forecast?.adjustments ?? [];
  if (!forecast || !adj.length || typeof forecast.baseline !== "number" || typeof forecast.projected !== "number") return "";
  const lines = adj.map((a) => `- ${a.note ?? a.contextId} _(${a.contextId})_`);
  return `\n\n**Evidence adjustments** (trend baseline ${money(forecast.baseline)} → projected ${money(forecast.projected)}):\n${lines.join("\n")}`;
}

/* ------------------------------------------------------------------ */
/* Context                                                             */
/* ------------------------------------------------------------------ */

type ContextTemplate = (t: Team) => Omit<ContextItem, "id" | "teamIds"> & { body: string; origin: string; integration: Integration };

const CONTEXT_TEMPLATES: ContextTemplate[] = [
  (t) => {
    const from = addDays(period.start, -14);
    return {
      title: `${t.name} plan expands AI-assisted work`, kind: "plan", claimType: "stated_plan",
      category: "project", magnitude: { pct: 18, basis: "approved expansion of coding-assistant and API work; no headcount change" },
      attribution: `${t.lead ?? t.name + " lead"}, approved plan`,
      summary: `An approved ${t.name} plan increases AI tool and API usage from ${monthDay(from)} onward, so recent weeks run well above the earlier baseline.`,
      effectiveFrom: from, effectiveTo: addDays(period.end, 56), expectedEffect: "increase", confidence: "high",
      sources: [{ documentId: `doc-${t.id}-plan`, title: `${t.name} plan (approved)`, excerpt: "Usage of coding assistants and API-driven automation is expected to roughly double over the coming weeks.", locator: "§2 Scope", date: addDays(from, -8), kind: "plan", integration: "pdf", author: `${t.lead ?? t.name + " lead"}` }],
      uncertainty: "The plan does not estimate cost; the projection impact is a forecasting decision.",
      origin: "Uploaded PDF", integration: "pdf", body: `# ${t.name} plan\n\n## 2. Scope\n\nUsage of coding assistants and API-driven automation is expected to roughly double from ${monthDay(from)} through the end of the quarter. Headcount is unchanged.`,
    };
  },
  (t) => {
    const from = addDays(period.start, -7);
    return {
      title: `${t.name} milestone deferred`, kind: "project_doc", claimType: "stated_plan",
      category: "project", magnitude: { pct: -20, basis: "feature work paused except P0; stabilization only" },
      attribution: `${t.lead ?? t.name + " lead"} in the roadmap`,
      summary: `A roadmap update defers ${t.name}'s main milestone into next quarter, reducing near-term work relative to the earlier plan.`,
      effectiveFrom: from, effectiveTo: addDays(period.end, 56), expectedEffect: "decrease", confidence: "medium",
      sources: [{ documentId: `doc-${t.id}-roadmap`, title: `${t.name} roadmap update`, excerpt: "The milestone moves into next quarter; the team shifts to stabilization and escalations for the rest of this one.", locator: "Roadmap · this quarter", date: from, kind: "project_doc", integration: "notion", author: t.lead }],
      uncertainty: "Stabilization could still consume tooling if incident load is high.",
      origin: "Notion (via connector)", integration: "notion", body: `# ${t.name} roadmap update\n\nThe milestone moves into next quarter. The team shifts to stabilization and escalations for the rest of this one.`,
    };
  },
  (t) => {
    const from = addDays(period.start, -56);
    return {
      title: `${t.name} work continues at current pace`, kind: "project_doc", claimType: "stated_plan",
      category: "project", magnitude: { basis: "no stated change; the trend carries" },
      attribution: `${t.lead ?? t.name + " lead"}, status note`,
      summary: `A team note confirms ${t.name} continues current work with no planned change in tool use.`,
      effectiveFrom: from, effectiveTo: addDays(period.end, 56), expectedEffect: "neutral", confidence: "medium",
      sources: [{ documentId: `doc-${t.id}-note`, title: `${t.name} status note`, excerpt: "On track; steady effort expected through the quarter with no staffing or tooling change.", locator: "Weekly status", date: addDays(period.start, -10), kind: "project_doc", integration: "google_docs", author: t.lead }],
      origin: "Google Docs (via connector)", integration: "google_docs", body: `# ${t.name} status\n\nOn track; steady effort expected through the quarter with no staffing or tooling change.`,
    };
  },
];


/** Extra evidence some teams carry on top of their plan: an email to finance, or a Linear issue that adds work. */
const EXTRA_TEMPLATES: Record<"gmail" | "linear", ContextTemplate> = {
  gmail: (t) => {
    const sent = addDays(period.start, -2);
    const lead = t.lead ?? `${t.name} lead`;
    return {
      title: `${lead.split(" ")[0]} warned finance the ${t.name} API line will run hot`, kind: "correspondence", claimType: "stated_plan",
      category: "project", magnitude: { pct: 12, basis: "API rows at about 1.4× while the batch job finishes; seats unchanged" },
      attribution: `${lead} to finance@northstar`,
      summary: `An email from ${lead} to finance says ${t.name}'s API usage runs above baseline this week and next while a batch job completes, and asks that the overage be expected rather than flagged.`,
      effectiveFrom: sent, effectiveTo: addDays(period.end, 7), expectedEffect: "increase", confidence: "medium",
      sources: [{ documentId: `mail-${t.id}-finance`, title: "Email: Re: AI spend this week", excerpt: `Heads up — our API line will run roughly 1.4× through next Friday while the batch job finishes. Nothing to flag; it settles after that.`, locator: "finance@northstar", date: sent, kind: "correspondence", integration: "gmail", author: lead }],
      uncertainty: "The email gives a multiple, not a dollar figure; the end date is the sender's estimate.",
      origin: "Gmail (finance@northstar thread, via connector)", integration: "gmail",
      body: `**From:** ${lead}\n**To:** finance@northstar.example\n**Date:** ${monthDay(sent)}\n**Subject:** Re: AI spend this week\n\n---\n\nHeads up — our API line will run roughly 1.4× through next Friday while the batch job finishes. Nothing to flag; it settles after that.\n\n${lead.split(" ")[0]}`,
    };
  },
  linear: (t) => {
    const opened = addDays(period.start, -4);
    const key = `${t.name.replace(/[^A-Z]/g, "").slice(0, 3) || "ENG"}-${180 + t.name.length * 7}`;
    return {
      title: `${key} adds a week of LLM-assisted backfill work`, kind: "project_doc", claimType: "stated_plan",
      category: "project", magnitude: { pct: 8, basis: "one-off classifier run over historical records, capped at 8 concurrent" },
      attribution: `${t.lead ?? t.name + " lead"} in Linear ${key}`,
      summary: `A Linear issue assigned to ${t.name} schedules a backfill that runs an LLM classifier across historical records this week, a one-off that lifts API usage until it completes.`,
      effectiveFrom: opened, effectiveTo: period.end, expectedEffect: "increase", confidence: "medium",
      sources: [{ documentId: `lin-${t.id}-backfill`, title: `Linear: ${key} Backfill classifier across historical records`, excerpt: "Run the classifier over all records since January; batch by tenant, cap concurrency at 8. Expect a few days of elevated API volume.", locator: `${key} · In progress`, date: opened, kind: "project_doc", integration: "linear", author: t.lead }],
      uncertainty: "Record count is not stated in the issue, so the run length is an estimate.",
      origin: "Linear (via connector)", integration: "linear",
      body: `# ${key} Backfill classifier across historical records\n\n**Team:** ${t.name} · **Status:** In progress · **Opened:** ${monthDay(opened)}\n\nRun the classifier over all records since January; batch by tenant, cap concurrency at 8. Expect a few days of elevated API volume.\n\n- [x] Dry run on one tenant\n- [ ] Full backfill\n- [ ] Verify counts`,
    };
  },
};

/** Staffing evidence some teams carry: two open roles stay unfilled, so the growth planned for new hires does not land. */
const STAFFING_TEMPLATE: ContextTemplate = (t) => {
  const from = addDays(period.start, -1);
  const lead = t.lead ?? `${t.name} lead`;
  return {
    title: `${t.name} hiring freeze: two open roles stay unfilled`, kind: "correspondence", claimType: "stated_plan",
    category: "staffing", magnitude: { pct: -4, basis: "two planned seats not provisioned; their expected first-month usage removed" },
    attribution: `${lead} in #${t.id}-leads`,
    summary: `${lead} told the team in Slack that the two open ${t.name} roles stay unfilled through the quarter. The seats and API keys planned for them are not provisioned, so the growth the plan assumed for new hires does not land this period.`,
    effectiveFrom: from, effectiveTo: addDays(period.end, 63), expectedEffect: "decrease", confidence: "medium",
    sources: [{ documentId: `doc-${t.id}-hiring-freeze`, title: `Slack #${t.id}-leads: hiring update`, excerpt: "both open reqs are on hold until next quarter — don't provision seats for them, we'll revisit after close", locator: `#${t.id}-leads`, date: from, kind: "correspondence", integration: "slack", author: lead }],
    uncertainty: "If one role is backfilled by an internal transfer, that seat appears mid-period.",
    origin: `Slack (#${t.id}-leads, via connector)`, integration: "slack",
    body: `**${lead}** ${monthDay(from)} 11:20 — both open reqs are on hold until next quarter — don't provision seats for them, we'll revisit after close\n\n**People Ops** 11:26 — noted, the two seats are released back to the pool`,
  };
};

/* ------------------------------------------------------------------ */
/* Company                                                             */
/* ------------------------------------------------------------------ */

export function generateCompany(teamCount: number): Dataset {
  const n = Math.max(0, Math.min(MAX_TEAMS, Math.floor(teamCount)));
  const rnd = mulberry32(1000 + n);
  const pool = TEAM_POOL.slice(0, n);

  const teams: Team[] = pool.map((p, i) => ({ id: slug(p.name), name: p.name, description: p.description, lead: p.lead, color: teamColor(i, n) }));

  // Weekly internal allocations in dollars.
  const budgets: Budget[] = teams.map((t) => ({
    teamId: t.id, period, unit: "usd", version: "v1",
    allocated: Math.round((8_000 + rnd() * 32_000) / 1_000) * 1_000,
  }));

  const spending: SpendingRecord[] = [];
  const forecasts: Forecast[] = [];
  const people: Person[] = [];
  const profiles = new Map<string, PersonProfile[]>();
  const personContextItems: ContextItem[] = [];
  const personDocs: CompanyDocument[] = [];
  const SIGNAL_NOTE: Record<SignalKind, (first: string) => string> = {
    project_deferred: (f) => `${f}: build pushed back, staying on the design doc (Slack)`,
    model_change: (f) => `${f}: migrating to ${NEW_MODEL}, comparison runs at full context (Asana)`,
    out_of_office: (f) => `${f}: out of office from ${monthDay(addDays(asOf, 1))} (Monday)`,
    project_accelerated: (f) => `${f}: deadline pulled into this week (Asana)`,
    onboarding: (f) => `${f}: ramping up after joining (Slack)`,
    tool_change: (f) => `${f}: switching tools`,
    steady: (f) => `${f}: no change signalled`,
    pricing_change: (f) => `${f}'s provider changed per-token prices; the same usage costs more from the effective date.`,
    policy_change: (f) => `${f}'s team is allowed a new model or tool from the effective date; the effect depends on adoption.`,
    project_paused: (f) => `${f}'s project is paused for an external reason, so usage drops until it resumes.`,
  };

  // Person-scope evidence naming several people: the renovation pause (owner's example), a cheaper-model switch and
  // an onboarding wave, each on a different team when there are enough teams. Named people get an `override` so
  // their projected days move with the evidence; `attachAdjustments` then recovers the trend baseline.
  const groupEvidence: GroupEvidence[] = [];
  const renovationIdx = Math.min(1, n - 1);
  const modelSwitchIdx = 0;
  const waveIdx = Math.min(2, n - 1);
  const renovationFrom = addDays(period.start, 2);
  const renovationTo = addDays(period.end, 5);

  teams.forEach((t, i) => {
    const p = pool[i];
    const weekly = budgets[i].allocated * p.pace;
    const periodTarget = Math.round(
      RECORDED_DATES.filter((d) => d >= period.start).reduce((s, d) => s + expectedOn(weekly, d) * (d === asOf ? PARTIAL_FRACTION : 1), 0) / 10,
    ) * 10;
    const growth = p.pace > 1.2 ? 1.09 : p.pace < 0.7 ? 1.0 : 1.05;

    // People: every record and every projection is attributed to a person; the team is the sum.
    const team = makePeople(t, i, growth);
    profiles.set(t.id, team);
    {
      const used = new Set<string>();
      const ordered = [...team.filter((x) => x.person.name !== t.lead), ...team.filter((x) => x.person.name === t.lead)];
      const pick = (count: number) => ordered.filter((x) => x.signal !== "out_of_office" && !used.has(x.person.id)).slice(0, count);
      const mark = (xs: PersonProfile[], override: PersonProfile["override"]) => xs.forEach((x) => { used.add(x.person.id); x.override = override; });
      if (i === renovationIdx) {
        const xs = pick(3);
        if (xs.length >= 2) { mark(xs, { from: renovationFrom, factor: 0.4 }); groupEvidence.push(renovationEvidence(t, xs.map((x) => x.person), renovationFrom, renovationTo)); }
      }
      if (i === modelSwitchIdx) {
        const xs = pick(2);
        const models = MODELS[asProvider(p.provider)];
        if (xs.length >= 2) { mark(xs, { from: addDays(period.start, 1), factor: 0.85 }); groupEvidence.push(modelSwitchEvidence(t, xs.map((x) => x.person), models[models.length - 1].model)); }
      }
      if (i === waveIdx) {
        const xs = pick(2);
        if (xs.length >= 2) { mark(xs, { from: period.start, factor: 1.12 }); groupEvidence.push(onboardingWaveEvidence(t, xs.map((x) => x.person))); }
      }
    }
    people.push(...team.map((x) => x.person));
    const shareSum = team.reduce((s, x) => s + x.share, 0);
    const targets = splitExact(periodTarget, team.map((x) => x.share), 10);
    team.forEach((x, j) => spending.push(...dailySeries(t.id, targets[j], p.mix, p.provider, 7 + i * 11 + j, x.growth, x.person.id)));

    const unavailable = n > 3 && i % 5 === 4;
    const unavailableReason = `Insufficient history for ${t.name} after its provider workspace was re-mapped on ${monthDay(addDays(period.start, 1))}.`;
    const teamDaily: ForecastDailyPoint[] = PROJECTED_DATES.map((d) => ({ date: d, projected: 0, low: 0, high: 0 }));
    let teamDone = 0;
    team.forEach((x) => {
      const done = completeSpent(spending, t.id, x.person.id);
      teamDone += done;
      const daily: ForecastDailyPoint[] = PROJECTED_DATES.map((d, k) => {
        // Out of office applies from tomorrow; today is still a normal (partial) day.
        const mod = x.signal === "out_of_office" ? (k === 0 ? 1 : x.modifier) : x.modifier;
        const override = x.override && d >= x.override.from ? x.override.factor : 1;
        const e = expectedOn((weekly * x.share) / shareSum, d) * mod * override;
        return { date: d, projected: Math.round(e), low: Math.round(e * 0.85), high: Math.round(e * 1.2) };
      });
      daily.forEach((d, k) => { teamDaily[k].projected += d.projected; teamDaily[k].low! += d.low!; teamDaily[k].high! += d.high!; });
      const sum = (k: "projected" | "low" | "high") => daily.reduce((s, d) => s + (d[k] ?? 0), 0);
      forecasts.push(
        unavailable
          ? {
              id: `fc-${x.person.id}-1`, teamId: t.id, personId: x.person.id, period, status: "unavailable", unit: "usd", basis: "full_period", kind: "forecast", origin: "placeholder",
              assumptions: [], limitations: ["Team history unavailable"], unavailableReason, generatedAt: `${asOf}T09:00:00Z`,
            }
          : {
              id: `fc-${x.person.id}-1`, teamId: t.id, personId: x.person.id, period, status: "available", unit: "usd", basis: "full_period", kind: "forecast", origin: "placeholder",
              projected: done + sum("projected"), low: done + sum("low"), high: done + sum("high"), daily,
              assumptions: [SIGNAL_NOTE[x.signal](x.person.name.split(" ")[0]), "Weekend usage runs at about a third of a weekday"],
              limitations: ["Not the output of a selected model", `${monthDay(asOf)} data is partial`],
              generatedAt: `${asOf}T09:00:00Z`,
            },
      );
      const ctx = personContext(t, x, t.lead ?? "Team lead", NEW_MODEL);
      if (ctx && !(x.person.name === t.lead && x.signal === "project_deferred")) { personContextItems.push(ctx.item); personDocs.push(ctx.doc); }
    });

    const sumTeam = (k: "projected" | "low" | "high") => teamDaily.reduce((s, d) => s + (d[k] ?? 0), 0);
    const signalled = team.filter((x) => x.signal !== "steady").map((x) => SIGNAL_NOTE[x.signal](x.person.name.split(" ")[0]));
    forecasts.unshift(
      unavailable
        ? {
            id: `fc-${t.id}-1`, teamId: t.id, period, status: "unavailable", unit: "usd", basis: "full_period", kind: "forecast", origin: "placeholder",
            assumptions: [], limitations: ["Fewer than 3 complete days of attributable data this week"],
            unavailableReason, generatedAt: `${asOf}T09:00:00Z`,
          }
        : {
            id: `fc-${t.id}-1`, teamId: t.id, period, status: "available", unit: "usd", basis: "full_period", kind: "forecast", origin: "placeholder",
            projected: teamDone + sumTeam("projected"), low: teamDone + sumTeam("low"), high: teamDone + sumTeam("high"), daily: teamDaily,
            assumptions: [
              p.pace > 1.2 ? "Planned expansion continues through the week" : p.pace < 0.7 ? "Deferred milestone keeps activity low" : "Steady state",
              `Sum of ${team.length} individual projections`,
              ...signalled,
              "Weekend usage runs at about a third of a weekday",
            ],
            limitations: ["Not the output of a selected model", `${monthDay(asOf)} data is partial`],
            generatedAt: `${asOf}T09:00:00Z`,
          },
    );
  });

  const context: ContextItem[] = [];
  const documents: CompanyDocument[] = [];
  teams.forEach((t, i) => {
    const p = pool[i];
    const templates: ContextTemplate[] = [CONTEXT_TEMPLATES[p.pace > 1.2 ? 0 : p.pace < 0.7 ? 1 : 2]];
    if (i % 3 === 1) templates.push(EXTRA_TEMPLATES.gmail);
    if (i % 4 === 2) templates.push(EXTRA_TEMPLATES.linear);
    if (i % 3 === 0) templates.push(STAFFING_TEMPLATE);
    templates.forEach((make, k) => {
      const { body, origin, integration, ...item } = make(t);
      context.push({ id: `ctx-${t.id}-${k + 1}`, teamIds: [t.id], scope: "team", ...item });
      const src = item.sources[0];
      documents.push({ id: src.documentId, title: src.title, kind: item.kind, date: src.date ?? asOf, teamIds: [t.id], origin, integration, body });
    });
  });
  context.push(...personContextItems);
  documents.push(...personDocs);
  if (n > 0) {
    const macro = macroModelContext(teams, NEW_MODEL);
    context.push(macro.item);
    documents.push(macro.doc);
    const company = companyEvidence(teams, NEW_MODEL);
    context.push(...company.items);
    documents.push(...company.docs);
  }
  context.push(...groupEvidence.map((g) => g.item));
  documents.push(...groupEvidence.map((g) => g.doc));

  // Every available projection now carries its trend baseline and the signed evidence adjustments that explain it.
  attachAdjustments(forecasts, context, people);
  const evidenceCount = context.filter((c) => !c.supersededBy).length;
  const companyCount = context.filter((c) => c.scope === "company" && !c.supersededBy).length;

  const company: Company = {
    id: `synthetic-${n}`, name: n === 0 ? "New Company (no teams yet)" : "Northstar Software",
    isDemo: true, budgetUnit: "usd", currentPeriod: period,
  };

  const over = teams.filter(t => (forecasts.find(f => f.teamId === t.id && !f.personId)?.projected ?? 0) > (budgets.find(b => b.teamId === t.id)?.allocated ?? Infinity)).map(t => t.name);
  const threads: Record<string, AssistantMessage[]> = {
    main: [{
      id: "msg-welcome", threadId: "main", role: "assistant", createdAt: `${asOf}T09:05:00Z`,
      content: n === 0
        ? "No teams are set up yet. Once the backend supplies teams and budgets, I can help you plan allocations."
        : over.length
          ? `**${over.join(", ")}** ${over.length === 1 ? "is" : "are"} projected over allocation this week. The projections take ${evidenceCount} evidence items into account (${companyCount} company-wide). I can redistribute the existing envelope or allocate new funding if finance authorizes it.`
          : `Every team is projected within its allocation this week, after ${evidenceCount} evidence items (${companyCount} company-wide). Ask me to compare teams or explain any projection.`,
    }],
  };

  return {
    company, teams, people, budgets, spending, forecasts, context, documents, proposals: [], decisions: [], threads,
    scriptedReply: makeGenericReply(teams, forecasts, context, people),
  };
}

/* ------------------------------------------------------------------ */
/* Assistant                                                           */
/* ------------------------------------------------------------------ */

/** Compatibility helper: bare numbers are dollars; invalid amounts remain absent. */
export function parseAmount(text: string): number | undefined {
  const parsed = interpretActionIntent(`Add ${text}`, []);
  return parsed.action === "addition" && parsed.amount ? Number(parsed.amount) : undefined;
}

/** Current requests are planning evidence, never additional forecast spend or implicit funding links. */
export function budgetRequestConsideration(requests: BudgetRequest[] | undefined, planningPeriod: Period, teams: Team[]): { content: string; toolCalls: ToolCallSummary[] } {
  if (!requests) return { content: "", toolCalls: [] };
  const endExclusive = addDays(planningPeriod.end, 1);
  const activeStatuses = new Set(["submitted", "pending_review", "needs_revision", "partially_funded"]);
  const unique = new Map(requests.map(request => [request.id, request]));
  const current = [...unique.values()].filter(request => activeStatuses.has(request.status) && request.unit === "USD"
    && request.periodStart === planningPeriod.start && request.periodEndExclusive === endExclusive
    && request.period.startDate === planningPeriod.start && request.period.endDateExclusive === endExclusive
    && teams.some(team => team.id === request.teamId));
  const toolCalls = [{ name: "list_budget_requests", summary: `Read ${current.length} current USD request${current.length === 1 ? "" : "s"} for ${planningPeriod.start} through ${planningPeriod.end}; request amounts remain separate from the published forecast.` }];
  if (!current.length) return { content: "", toolCalls };
  const inline = (value: string) => value.replace(/\s+/g, " ").replace(/[\\[\]*_`]/g, "\\$&");
  const dollars = (amount: string) => `$${amount.replace(/\B(?=(\d{3})+(?!\d))/g, ",")}`;
  const lines = current.slice(0, 3).map(request => {
    const amount = request.remainingRequestedAmount === null ? "amount needs clarification"
      : request.status === "partially_funded" ? `${dollars(request.remainingRequestedAmount)} remaining of ${dollars(request.requestedAmount!)} requested`
      : `${dollars(request.remainingRequestedAmount)} requested`;
    const source = request.source.reference ?? request.sourceRef ?? `Update submitted by ${request.source.submittedBy}`;
    return `- [${inline(request.title)}](/requests?request=${encodeURIComponent(request.id)}) — ${inline(teams.find(team => team.id === request.teamId)!.name)}: ${amount}; ${request.status.replaceAll("_", " ")}. Source: ${inline(source)}.`;
  });
  if (current.length > 3) lines.push(`Also considered ${current.length - 3} other current requests. [View requests](/requests?status=open&period=current).`);
  return { content: `**Current team requests · ${planningPeriod.start} to ${endExclusive} (end exclusive)**\n${lines.join("\n")}\n\nRemaining requests need review and are not added to the published forecast. Considering them does not approve or link funding.`, toolCalls };
}

/** Apply the same live request consideration to canonical and generated mock responses. */
export function withBudgetRequestConsideration(reply: ScriptedReplyFn, teams: Team[], planningPeriod: Period = period): ScriptedReplyFn {
  return (content, state, conversationContext, forecastContext) => {
    const response = reply(content, state, conversationContext, forecastContext);
    // Northstar delegates explicit changes to the generic reply; include its consideration only once.
    if (response.message.toolCalls?.some(call => call.name === "list_budget_requests")) return response;
    const consideration = budgetRequestConsideration(state.budgetRequests, response.proposal?.period ?? planningPeriod, teams);
    return { ...response,
      message: { ...response.message,
        content: response.message.content + (consideration.content ? `\n\n${consideration.content}` : ""),
        toolCalls: [...(response.message.toolCalls ?? []), ...consideration.toolCalls],
      },
      ...(response.proposal ? { proposal: { ...response.proposal, rationale: response.proposal.rationale + (consideration.content ? `\n\n${consideration.content}` : "") } } : {}),
    };
  };
}

/** Generic assistant for N teams: add funding proportional to projected gaps; redistribute from under- to over-allocated teams. */
export function makeGenericReply(teams: Team[], allForecasts: Forecast[], context: ContextItem[], people: Person[] = [], planningPeriod: Period = period): ScriptedReplyFn {
  const sources = context.filter((c) => !c.supersededBy).flatMap((c) => c.sources);
  const forecasts = allForecasts.filter((f) => !f.personId);
  const personForecasts = allForecasts.filter((f) => !!f.personId);
  const fc = (id: string) => forecasts.find((f) => f.teamId === id);
  const exactMoney = (amount: number) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2, minimumFractionDigits: 0 }).format(amount);
  // Largest remainders preserve exact cents without producing a negative residual share.
  const sharesInCents = (total: number, weights: number[]) => {
    const weight = weights.reduce((sum, value) => sum + value, 0);
    const raw = weights.map((value) => weight > 0 ? value / weight * total : 0);
    const shares = raw.map(Math.floor);
    const order = raw.map((value, index) => ({ index, remainder: value - shares[index] })).sort((a, b) => b.remainder - a.remainder || a.index - b.index);
    const remaining = total - shares.reduce((sum, value) => sum + value, 0);
    for (let index = 0; index < remaining; index++) shares[order[index].index]++;
    return shares;
  };

  return withBudgetRequestConsideration((content, state, conversationContext) => {
    const text = content.toLowerCase();
    const intent = interpretActionIntent(content, teams, { context: conversationContext, proposals: state.proposals, planningPeriod });
    if (intent.action === "clarify" || intent.ask) return { message: { content: intent.ask!, conversationContext: intent.context } };
    const total = state.budgets.reduce((s, b) => s + b.allocated, 0);
    const alloc = (id: string) => state.budgets.find((b) => b.teamId === id)!.allocated;
    const base = {
      unit: "usd" as const, period: planningPeriod, createdAt: nextDemoTimestamp(), status: "proposed" as const,
      basedOnBudgetVersion: state.budgetVersion, forecastsReviewed: structuredClone(forecasts), citations: sources,
    };
    const gaps = teams.map((t) => ({ t, gap: Math.max(0, (fc(t.id)?.projected ?? 0) - alloc(t.id)) }));
    const surplus = teams.map((t) => ({ t, surplus: fc(t.id)?.status === "available" ? Math.max(0, alloc(t.id) - (fc(t.id)!.projected ?? 0)) : 0 }));

    if (teams.length === 0) return { message: { content: "There are no teams yet, so there is nothing to allocate." } };

    if (intent.action === "addition" || intent.action === "transfer") {
      const cents = (amount: number) => Math.round(amount * 100);
      const lines = teams.map((t) => ({ teamId: t.id, before: alloc(t.id), after: alloc(t.id) }));
      const gapTotal = gaps.reduce((sum, value) => sum + value.gap, 0);
      const surplusTotal = surplus.reduce((sum, value) => sum + value.surplus, 0);
      let amount = Number(intent.amount ?? 0);
      if (intent.action === "addition") {
        const weights = intent.targetTeamId ? teams.map((team) => Number(team.id === intent.targetTeamId)) : gapTotal > 0 ? gaps.map((gap) => gap.gap) : teams.map((_, index) => Number(index === 0));
        const shares = sharesInCents(cents(amount), weights);
        shares.forEach((share, index) => { lines[index].after = (cents(lines[index].before) + share) / 100; });
      } else if (intent.sourceTeamId && intent.targetTeamId) {
        const source = lines.find((line) => line.teamId === intent.sourceTeamId)!;
        const target = lines.find((line) => line.teamId === intent.targetTeamId)!;
        if (cents(amount) > cents(source.before)) return { message: { content: `The transfer exceeds ${teams.find((team) => team.id === source.teamId)!.name}'s ${exactMoney(source.before)} allocation. Choose a smaller amount.`, conversationContext: { ...intent.context, pending_slot: "amount" } } };
        source.after = (cents(source.before) - cents(amount)) / 100;
        target.after = (cents(target.before) + cents(amount)) / 100;
      } else {
        amount = Math.round(Math.min(gapTotal, surplusTotal * 0.75) * 100) / 100;
        if (amount <= 0) return { message: { content: "No transfer is available: there is no projected shortfall or no unused allocation to move.", conversationContext: intent.context } };
        const taken = sharesInCents(cents(amount), surplus.map((value) => value.surplus));
        const given = sharesInCents(cents(amount), gaps.map((value) => value.gap));
        lines.forEach((line, index) => { line.after = (cents(line.before) - taken[index] + given[index]) / 100; });
      }
      const added = intent.action === "addition" ? amount : 0;
      const previous = state.proposals.find((proposal) => proposal.id === intent.reviseProposalId);
      const proposal: AllocationProposal = {
        ...base, id: `prop_${crypto.randomUUID()}`, version: 1,
        kind: intent.action === "addition" ? "add_budget" : "redistribute",
        totalBefore: total, totalAfter: (cents(total) + cents(added)) / 100,
        ...(intent.action === "addition" ? { addedAmount: amount } : {}), lines,
        revisesProposalId: previous?.id,
        rationale: intent.action === "addition"
          ? `Adds ${exactMoney(amount)}${intent.targetTeamId ? ` to ${teams.find((team) => team.id === intent.targetTeamId)!.name}` : " in proportion to projected shortfalls"}.`
          : `Moves ${exactMoney(amount)} between teams. Total team allocations of ${exactMoney(total)} are unchanged.`,
      };
      const bullets = lines.filter((line) => line.after !== line.before).map((line) => `- **${teams.find((team) => team.id === line.teamId)!.name} ${line.after > line.before ? "+" : "−"}${exactMoney(Math.abs(line.after - line.before))}** → ${exactMoney(line.after)}`).join("\n");
      return { proposal, message: {
        content: `${previous ? "Revised proposal" : "Proposed budget change"}:\n\n${bullets}\n\n${intent.action === "addition" ? `Total team allocations go from **${exactMoney(total)} to ${exactMoney(proposal.totalAfter)}**.` : `Total team allocations stay at **${exactMoney(total)}**.`}`,
        proposalId: proposal.id, citations: sources,
        conversationContext: { ...intent.context, selected_proposal_id: proposal.id, selected_proposal_version: proposal.version },
        toolCalls: [{ name: "get_budgets", summary: "Read current allocations" }, { name: "get_forecasts", summary: "Compared projections with allocations" }],
      } };
    }

    if (intent.action === "explain" || /why|explain|over|under|exceed/.test(text)) {
      const named = teams.find((t) => text.includes(t.name.toLowerCase()));
      if (named) {
        const f = fc(named.id);
        const c = context.find((x) => x.teamIds.includes(named.id) && x.scope !== "person" && x.scope !== "company");
        const status = f?.status !== "available" ? "has no available projection" : (f.projected ?? 0) > alloc(named.id) ? `is projected at ${money(f.projected!)} against ${money(alloc(named.id))} for this period` : `is projected at ${money(f.projected!)} against ${money(alloc(named.id))} for this period, within allocation`;
        // Person-level signals from the connectors: who is moving the number and why.
        const signals = context
          .filter((x) => x.scope === "person" && x.teamIds.includes(named.id) && !x.supersededBy)
          .map((x) => {
            const person = people.find((pp) => x.personIds?.includes(pp.id));
            const pf = person ? personForecasts.find((y) => y.personId === person.id) : undefined;
            const via = x.sources[0]?.integration;
            const dir = x.expectedEffect === "increase" ? "up" : x.expectedEffect === "decrease" ? "down" : "flat";
            return { x, line: `- **${person?.name ?? "Someone"}** (${dir}${pf?.projected != null ? `, projected ${money(pf.projected)}` : ""}): ${x.summary}${via ? ` _(via ${via === "monday" ? "Monday" : via[0].toUpperCase() + via.slice(1)})_` : ""}` };
          });
        const macro = context.find((x) => x.scope === "company" && x.teamIds.includes(named.id));
        // Evidence that moved the number: the team forecast's adjustments, each citing its evidence id.
        const cited = (f?.adjustments ?? []).map((a) => context.find((x) => x.id === a.contextId)).filter((x): x is ContextItem => !!x);
        const content = [
          `**${named.name}** ${status}.${c ? ` ${c.summary}` : ""}`,
          signals.length ? `\n**By person:**\n${signals.map((s) => s.line).join("\n")}` : "",
          macro ? `\n**Company-wide:** ${macro.summary}` : "",
          evidenceLines(f),
        ].filter(Boolean).join("\n");
        return {
          message: {
            conversationContext: intent.context,
            content,
            citations: [...(c?.sources ?? []), ...signals.flatMap((s) => s.x.sources), ...(macro?.sources ?? []), ...cited.flatMap((x) => x.sources)],
            toolCalls: [
              { name: "get_forecasts", summary: `Read ${named.name} projection and ${personForecasts.filter((y) => y.teamId === named.id).length} individual projections` },
              { name: "search_documents", summary: c ? `Found "${c.sources[0].title}"` : "No relevant documents" },
              ...(signals.length ? [{ name: "read_integrations", summary: `Pulled ${signals.length} person-level signals from Slack, Asana and Monday` }] : []),
              ...(cited.length ? [{ name: "explain_forecast", summary: `Attributed ${signedMoney((f?.projected ?? 0) - (f?.baseline ?? f?.projected ?? 0))} of the projection to ${cited.length} evidence items` }] : []),
            ],
          },
        };
      }
    }

    return {
      message: {
        conversationContext: intent.context,
        content: `I can help with two kinds of changes: **redistribute** the existing ${money(total)} in team allocations between ${teams.length} teams, or **add** new funding and allocate it. I can also explain why a team is tracking over or under.`,
      },
    };
  }, teams, planningPeriod);
}
