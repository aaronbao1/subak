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
  AllocationProposal, AssistantMessage, Budget, Company, CompanyDocument, ContextItem, Decision, Forecast,
  ForecastDailyPoint, Integration, Period, Person, SignalKind, SpendingRecord, Team,
} from "@/lib/contracts";

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
  state: { proposals: AllocationProposal[]; budgets: Budget[]; budgetVersion: string },
) => { message: Omit<AssistantMessage, "id" | "threadId" | "role" | "createdAt">; proposal?: AllocationProposal };

export const MAX_TEAMS = 16;
export const DEFAULT_TEAM_COUNT = 8;

/* ------------------------------------------------------------------ */
/* Calendar                                                            */
/* ------------------------------------------------------------------ */

const DAY_MS = 86_400_000;
const WEEK_MS = 7 * DAY_MS;
const pad = (n: number) => String(n).padStart(2, "0");
const localIso = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const toTs = (iso: string) => { const [y, m, d] = iso.split("-").map(Number); return Date.UTC(y, m - 1, d); };
const fromTs = (ts: number) => new Date(ts).toISOString().slice(0, 10);
export const addDays = (iso: string, n: number) => fromTs(toTs(iso) + n * DAY_MS);
const range = (from: string, to: string) => { const out: string[] = []; for (let ts = toTs(from); ts <= toTs(to); ts += DAY_MS) out.push(fromTs(ts)); return out; };
const weekday = (iso: string) => new Date(toTs(iso)).getUTCDay();
const isWeekend = (iso: string) => weekday(iso) === 0 || weekday(iso) === 6;
export const monthDay = (iso: string) => new Date(toTs(iso)).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });

const now = new Date();
/** Today in local time: the partial day. */
export const asOf = localIso(now);
const mondayOffset = (weekday(asOf) + 6) % 7;
const periodStart = addDays(asOf, -mondayOffset);
/** The current Monday-to-Sunday week. */
export const period: Period = { start: periodStart, end: addDays(periodStart, 6), label: `Week of ${monthDay(periodStart)}` };
export const HISTORY_WEEKS = 8;
/** Every recorded day: eight weeks of history plus this week through today. */
export const RECORDED_DATES = range(addDays(period.start, -7 * HISTORY_WEEKS), asOf);
/** Days the projection covers day by day: today (full-day total) through Sunday. */
export const PROJECTED_DATES = range(asOf, period.end);
/** Share of today already elapsed, so the partial day visibly is partial. */
const PARTIAL_FRACTION = Math.min(0.95, Math.max(0.15, (now.getHours() + now.getMinutes() / 60) / 24));
/** Weekend activity relative to a weekday. */
const WEEKEND = 0.35;
const dayWeight = (iso: string) => (isWeekend(iso) ? WEEKEND : 1);
const WEEK_WEIGHT = 5 + 2 * WEEKEND;
/** Expected spend on a day for a team that spends `weekly` per week. */
const expectedOn = (weekly: number, iso: string) => (weekly * dayWeight(iso)) / WEEK_WEIGHT;

export const money = (n: number) => `$${Math.round(n).toLocaleString("en-US")}`;

/* ------------------------------------------------------------------ */
/* Teams                                                               */
/* ------------------------------------------------------------------ */

const TEAM_POOL: Array<Pick<Team, "name" | "description" | "lead"> & { provider: string; mix: Record<SpendingRecord["component"], number>; pace: number }> = [
  { name: "Research", description: "Model evaluation and applied research", lead: "Priya N.", provider: "anthropic", mix: { subscription: 1, included_usage: 1.2, extra_usage: 1.5, api: 5 }, pace: 1.45 },
  { name: "Product", description: "Customer-facing product features", lead: "Marcus L.", provider: "anthropic", mix: { subscription: 2.5, included_usage: 2, extra_usage: 0.4, api: 1.2 }, pace: 0.62 },
  { name: "Engineering", description: "Platform, infrastructure, internal tooling", lead: "Dana K.", provider: "openai", mix: { subscription: 1.5, included_usage: 1.2, extra_usage: 0.8, api: 2.2 }, pace: 1.08 },
  { name: "Data Science", description: "Analytics pipelines and experimentation", lead: "Wei Z.", provider: "openai", mix: { subscription: 1, included_usage: 1, extra_usage: 0.6, api: 3 }, pace: 1.2 },
  { name: "Security", description: "AppSec reviews and threat modeling", lead: "Tomás R.", provider: "anthropic", mix: { subscription: 1.2, included_usage: 1, extra_usage: 0.3, api: 0.8 }, pace: 0.9 },
  { name: "Marketing", description: "Content and campaign tooling", lead: "Jules O.", provider: "openai", mix: { subscription: 1, included_usage: 1, extra_usage: 0.2, api: 0.9 }, pace: 0.75 },
  { name: "Sales Engineering", description: "Demos, POCs, and RFP responses", lead: "Aisha B.", provider: "anthropic", mix: { subscription: 1.5, included_usage: 1.3, extra_usage: 0.5, api: 0.6 }, pace: 1.0 },
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
  mix: Record<SpendingRecord["component"], number>,
  provider: string,
  seed = 1,
  growth = 1.06,
  personId?: string,
): SpendingRecord[] {
  const rnd = mulberry32(seed);
  const raw: Omit<SpendingRecord, "amount">[] = [];
  const weights: number[] = [];
  for (const date of RECORDED_DATES) {
    const partial = date === asOf;
    const weekIndex = Math.floor((toTs(date) - toTs(period.start)) / WEEK_MS); // 0 this week, -1 last week, ...
    const level = growth ** weekIndex * (partial ? PARTIAL_FRACTION : 1);
    for (const [component, w] of Object.entries(mix) as [SpendingRecord["component"], number][]) {
      // Seat fees are flat across the week; usage follows the weekday/weekend rhythm with some noise.
      const activity = component === "subscription" ? level : level * dayWeight(date) * (0.8 + rnd() * 0.4);
      weights.push(w * activity);
      raw.push({
        id: `${personId ?? teamId}-${date}-${component}`,
        teamId, ...(personId ? { personId } : {}), date, component, provider, unit: "usd",
        provenance: component === "api" || component === "subscription" ? "reported_charge" : component === "included_usage" ? "usage_only" : "estimate",
        source: component === "api" || component === "subscription"
          ? `${provider === "anthropic" ? "Anthropic" : "OpenAI"} cost report export ${asOf}`
          : `Cursor Admin API export ${asOf}`,
        complete: !partial,
      });
    }
  }
  if (periodTarget <= 0 || raw.length === 0) return raw.map((r) => ({ ...r, amount: 0 }));
  const inPeriod = raw.map((r) => r.date >= period.start);
  const periodWeight = weights.reduce((s, w, i) => s + (inPeriod[i] ? w : 0), 0);
  const out = raw.map((r, i) => ({ ...r, amount: Math.round((weights[i] / periodWeight) * periodTarget) }));
  const lastInPeriod = out.length - 1;
  out[lastInPeriod].amount += periodTarget - out.reduce((s, r, i) => s + (inPeriod[i] ? r.amount : 0), 0);
  return out;
}

/** Spend recorded on complete days inside the period; the partial day is excluded because its projection replaces it. */
export function completeSpent(spending: SpendingRecord[], teamId: string, personId?: string) {
  return spending
    .filter((r) => r.teamId === teamId && (personId === undefined || r.personId === personId) && r.complete && r.date >= period.start && r.date <= period.end)
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
}

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
};

/**
 * One context item (and its readable source) per person signal, phrased the way the connector would surface it:
 * a Slack message from the manager, an Asana task, a Monday board item.
 */
export function personContext(team: Team, profile: PersonProfile, managerName: string, newModel: string): { item: ContextItem; doc: CompanyDocument } | undefined {
  const { person, signal } = profile;
  const first = person.name.split(" ")[0];
  const base = { teamIds: [team.id], personIds: [person.id], scope: "person" as const, signal, expectedEffect: SIGNAL_EFFECT[signal] };
  const since = addDays(period.start, -3);
  const docId = `doc-${person.id}-${signal}`;
  switch (signal) {
    case "project_deferred":
      return {
        item: {
          ...base, id: `ctx-${person.id}-deferred`, kind: "correspondence", claimType: "stated_plan", confidence: "high",
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
          title: `${first} is out of office from ${monthDay(addDays(asOf, 1))}`,
          summary: `The team's Monday board marks ${first} out of office for the rest of the week, so ${first}'s usage stops after today.`,
          effectiveFrom: addDays(asOf, 1), effectiveTo: period.end,
          sources: [{ documentId: docId, title: "monday.com: Team availability board", integration: "monday", author: person.name, date: addDays(asOf, -2), kind: "correspondence", locator: "row · Out of office",
            excerpt: `${person.name} — Out of office ${monthDay(addDays(asOf, 1))} to ${monthDay(period.end)}` }],
        },
        doc: { id: docId, title: "monday.com: Team availability board", kind: "correspondence", date: addDays(asOf, -2), teamIds: [team.id], personIds: [person.id], integration: "monday", origin: "monday.com (board item, via connector)",
          body: `# Team availability\n\n| Person | Status | Dates |\n|---|---|---|\n| ${person.name} | Out of office | ${monthDay(addDays(asOf, 1))} – ${monthDay(period.end)} |` },
      };
    case "project_accelerated":
      return {
        item: {
          ...base, id: `ctx-${person.id}-accel`, kind: "project_doc", claimType: "stated_plan", confidence: "medium",
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
/* Context                                                             */
/* ------------------------------------------------------------------ */

const CONTEXT_TEMPLATES: Array<(t: Team) => Omit<ContextItem, "id" | "teamIds"> & { body: string; origin: string }> = [
  (t) => {
    const from = addDays(period.start, -14);
    return {
      title: `${t.name} plan expands AI-assisted work`, kind: "plan", claimType: "stated_plan",
      summary: `An approved ${t.name} plan increases AI tool and API usage from ${monthDay(from)} onward, so recent weeks run well above the earlier baseline.`,
      effectiveFrom: from, effectiveTo: addDays(period.end, 56), expectedEffect: "increase", confidence: "high",
      sources: [{ documentId: `doc-${t.id}-plan`, title: `${t.name} plan (approved)`, excerpt: "Usage of coding assistants and API-driven automation is expected to roughly double over the coming weeks.", locator: "§2", date: addDays(from, -8), kind: "plan" }],
      uncertainty: "The plan does not estimate cost; the projection impact is a forecasting decision.",
      origin: "Uploaded PDF", body: `# ${t.name} plan\n\n## 2. Scope\n\nUsage of coding assistants and API-driven automation is expected to roughly double from ${monthDay(from)} through the end of the quarter. Headcount is unchanged.`,
    };
  },
  (t) => {
    const from = addDays(period.start, -7);
    return {
      title: `${t.name} milestone deferred`, kind: "project_doc", claimType: "stated_plan",
      summary: `A roadmap update defers ${t.name}'s main milestone into next quarter, reducing near-term work relative to the earlier plan.`,
      effectiveFrom: from, effectiveTo: addDays(period.end, 56), expectedEffect: "decrease", confidence: "medium",
      sources: [{ documentId: `doc-${t.id}-roadmap`, title: `${t.name} roadmap update`, excerpt: "The milestone moves into next quarter; the team shifts to stabilization.", locator: "p.1", date: from, kind: "project_doc" }],
      uncertainty: "Stabilization could still consume tooling if incident load is high.",
      origin: "Notion export", body: `# ${t.name} roadmap update\n\nThe milestone moves into next quarter. The team shifts to stabilization and escalations for the rest of this one.`,
    };
  },
  (t) => {
    const from = addDays(period.start, -56);
    return {
      title: `${t.name} work continues at current pace`, kind: "project_doc", claimType: "stated_plan",
      summary: `A team note confirms ${t.name} continues current work with no planned change in tool use.`,
      effectiveFrom: from, effectiveTo: addDays(period.end, 56), expectedEffect: "neutral", confidence: "medium",
      sources: [{ documentId: `doc-${t.id}-note`, title: `${t.name} status note`, excerpt: "On track; steady effort expected through the quarter.", date: addDays(period.start, -10), kind: "project_doc" }],
      origin: "Uploaded Markdown", body: `# ${t.name} status\n\nOn track; steady effort expected through the quarter with no staffing or tooling change.`,
    };
  },
];

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
  };

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
        const e = expectedOn((weekly * x.share) / shareSum, d) * mod;
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
              limitations: ["Shared placeholder projection, not the output of a selected model", `${monthDay(asOf)} data is partial`],
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
            limitations: ["Shared placeholder projection, not the output of a selected model", `${monthDay(asOf)} data is partial`],
            generatedAt: `${asOf}T09:00:00Z`,
          },
    );
  });

  const context: ContextItem[] = [];
  const documents: CompanyDocument[] = [];
  teams.forEach((t, i) => {
    const p = pool[i];
    const tpl = CONTEXT_TEMPLATES[p.pace > 1.2 ? 0 : p.pace < 0.7 ? 1 : 2](t);
    const { body, origin, ...item } = tpl;
    context.push({ id: `ctx-${t.id}-1`, teamIds: [t.id], scope: "team", ...item });
    const src = item.sources[0];
    documents.push({ id: src.documentId, title: src.title, kind: item.kind, date: src.date ?? asOf, teamIds: [t.id], origin, body });
  });
  context.push(...personContextItems);
  documents.push(...personDocs);
  if (n > 0) {
    const macro = macroModelContext(teams, NEW_MODEL);
    context.push(macro.item);
    documents.push(macro.doc);
  }

  const company: Company = {
    id: `synthetic-${n}`, name: n === 0 ? "New Company (no teams yet)" : "Northstar Software",
    isDemo: true, budgetUnit: "usd", currentPeriod: period,
  };

  const over = teams.filter((t, i) => (forecasts[i].projected ?? 0) > budgets[i].allocated).map((t) => t.name);
  const threads: Record<string, AssistantMessage[]> = {
    main: [{
      id: "msg-welcome", threadId: "main", role: "assistant", createdAt: `${asOf}T09:05:00Z`,
      content: n === 0
        ? "No teams are set up yet. Once the backend supplies teams and budgets, I can help you plan allocations."
        : over.length
          ? `**${over.join(", ")}** ${over.length === 1 ? "is" : "are"} projected over allocation this week. I can redistribute the existing envelope or allocate new funding if finance authorizes it.`
          : "Every team is projected within its allocation this week. Ask me to compare teams or explain any projection.",
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

/**
 * Dollar amounts as finance types them: "$50k", "50,000", "1.2m", or a bare number
 * (bare numbers under 1,000 are read as thousands). Undefined when the message names no amount.
 */
export function parseAmount(text: string): number | undefined {
  const m = text.match(/\$?\s?(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(million|thousand|mm|m|k)?\b/i);
  if (!m) return undefined;
  const num = Number(m[1].replace(/,/g, ""));
  if (!Number.isFinite(num)) return undefined;
  const suffix = m[2]?.toLowerCase();
  if (!suffix) return num < 1_000 ? num * 1_000 : num;
  if (/^(m|mm|million)$/.test(suffix)) return Math.round(num * 1_000_000);
  return Math.round(num * 1_000);
}

/** Generic assistant for N teams: add funding proportional to projected gaps; redistribute from under- to over-allocated teams. */
export function makeGenericReply(teams: Team[], allForecasts: Forecast[], context: ContextItem[], people: Person[] = []): ScriptedReplyFn {
  const sources = context.filter((c) => !c.supersededBy).flatMap((c) => c.sources);
  const forecasts = allForecasts.filter((f) => !f.personId);
  const personForecasts = allForecasts.filter((f) => !!f.personId);
  const fc = (id: string) => forecasts.find((f) => f.teamId === id);
  const round = (x: number) => Math.round(x / 500) * 500;

  return (content, state) => {
    const text = content.toLowerCase();
    const total = state.budgets.reduce((s, b) => s + b.allocated, 0);
    const alloc = (id: string) => state.budgets.find((b) => b.teamId === id)!.allocated;
    const base = {
      unit: "usd" as const, period, createdAt: new Date().toISOString(), status: "proposed" as const,
      basedOnBudgetVersion: state.budgetVersion, forecastsReviewed: structuredClone(forecasts), citations: sources,
    };
    const gaps = teams.map((t) => ({ t, gap: Math.max(0, (fc(t.id)?.projected ?? 0) - alloc(t.id)) }));
    const surplus = teams.map((t) => ({ t, surplus: fc(t.id)?.status === "available" ? Math.max(0, alloc(t.id) - (fc(t.id)!.projected ?? 0)) : 0 }));

    if (teams.length === 0) return { message: { content: "There are no teams yet, so there is nothing to allocate." } };

    if (/\badd|additional|more (credits|budget|funding)|authoriz|\$\s?\d|\d+\s?k\b/.test(text)) {
      const amount = parseAmount(text) ?? 25_000;
      const gapTotal = gaps.reduce((s, g) => s + g.gap, 0);
      const lines = teams.map((t) => ({ teamId: t.id, before: alloc(t.id), after: alloc(t.id) }));
      if (gapTotal > 0) {
        const shares = gaps.map((g) => round((g.gap / gapTotal) * amount));
        const residual = amount - shares.reduce((s, x) => s + x, 0);
        const top = gaps.reduce((bi, g, i, arr) => (g.gap > arr[bi].gap ? i : bi), 0);
        shares[top] += residual;
        shares.forEach((s, i) => (lines[i].after += s));
      } else {
        lines[0].after += amount;
      }
      const proposal: AllocationProposal = {
        ...base, id: `prop_${Date.now()}`, kind: "add_budget", totalBefore: total, totalAfter: total + amount, addedAmount: amount, lines,
        rationale: gapTotal > 0
          ? `Distributed ${money(amount)} in proportion to each team's projected shortfall this week (projection minus allocation). Teams projected within allocation receive nothing new.`
          : `No team is projected over allocation, so the full ${money(amount)} is parked with ${teams[0].name} pending a finance decision.`,
      };
      const bullets = lines.filter((l) => l.after !== l.before).map((l) => `- **${teams.find((t) => t.id === l.teamId)!.name} +${money(l.after - l.before)}** → ${money(l.after)}`).join("\n");
      return {
        proposal,
        message: {
          content: `Here's how I'd allocate the additional **${money(amount)}**:\n\n${bullets}\n\nWeekly envelope goes from **${money(total)} to ${money(total + amount)}**.`,
          proposalId: proposal.id, citations: sources,
          toolCalls: [
            { name: "get_spending", summary: `Pulled ${monthDay(period.start)}–${monthDay(asOf)} spending for ${teams.length} teams` },
            { name: "get_forecasts", summary: `Compared ${forecasts.filter((f) => f.status === "available").length} available projections to allocations` },
            { name: "search_documents", summary: `Reviewed ${context.length} context items for planned changes` },
          ],
        },
      };
    }

    if (/redistribut|rebalanc|\bmove\b|shift|reallocat|without (adding|new)/.test(text)) {
      const gapTotal = gaps.reduce((s, g) => s + g.gap, 0);
      const surplusTotal = surplus.reduce((s, x) => s + x.surplus, 0);
      const movable = Math.min(gapTotal, surplusTotal * 0.75);
      if (movable <= 0) {
        return { message: { content: "I can't find a sensible redistribution: either no team is projected over allocation, or no team has headroom to give. Adding funding is the alternative." } };
      }
      const lines = teams.map((t) => ({ teamId: t.id, before: alloc(t.id), after: alloc(t.id) }));
      let taken = 0;
      surplus.forEach((s, i) => { if (s.surplus > 0) { const take = round((s.surplus / surplusTotal) * movable); lines[i].after -= take; taken += take; } });
      gaps.forEach((g, i) => { if (g.gap > 0) lines[i].after += round((g.gap / gapTotal) * taken); });
      const drift = lines.reduce((s, l) => s + l.after, 0) - total;
      const topGap = gaps.reduce((bi, g, i, arr) => (g.gap > arr[bi].gap ? i : bi), 0);
      lines[topGap].after -= drift;
      const proposal: AllocationProposal = {
        ...base, id: `prop_${Date.now()}`, kind: "redistribute", totalBefore: total, totalAfter: total, lines,
        rationale: `Moved ${money(taken)} from teams projected under allocation to teams projected over it, in proportion to headroom and shortfall. The ${money(total)} weekly envelope is unchanged.`,
      };
      const bullets = lines.filter((l) => l.after !== l.before).map((l) => `- **${teams.find((t) => t.id === l.teamId)!.name} ${l.after > l.before ? "+" : "−"}${money(Math.abs(l.after - l.before))}** → ${money(l.after)}`).join("\n");
      return {
        proposal,
        message: {
          content: `Without adding funding, I'd move **${money(taken)}** between teams:\n\n${bullets}\n\nEnvelope stays at **${money(total)}**.`,
          proposalId: proposal.id, citations: sources,
          toolCalls: [
            { name: "get_budgets", summary: `Read current allocations (${money(total)} weekly envelope)` },
            { name: "get_forecasts", summary: "Compared projections to allocations" },
          ],
        },
      };
    }

    if (/why|explain|over|under|exceed/.test(text)) {
      const named = teams.find((t) => text.includes(t.name.toLowerCase()));
      if (named) {
        const f = fc(named.id);
        const c = context.find((x) => x.teamIds.includes(named.id) && x.scope !== "person" && x.scope !== "company");
        const status = f?.status !== "available" ? "has no available projection" : (f.projected ?? 0) > alloc(named.id) ? `is projected at ${money(f.projected!)} against ${money(alloc(named.id))} this week` : `is projected at ${money(f.projected!)} against ${money(alloc(named.id))} this week, within allocation`;
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
        const content = [
          `**${named.name}** ${status}.${c ? ` ${c.summary}` : ""}`,
          signals.length ? `\n**By person:**\n${signals.map((s) => s.line).join("\n")}` : "",
          macro ? `\n**Company-wide:** ${macro.summary}` : "",
        ].filter(Boolean).join("\n");
        return {
          message: {
            content,
            citations: [...(c?.sources ?? []), ...signals.flatMap((s) => s.x.sources), ...(macro?.sources ?? [])],
            toolCalls: [
              { name: "get_forecasts", summary: `Read ${named.name} projection and ${personForecasts.filter((y) => y.teamId === named.id).length} individual projections` },
              { name: "search_documents", summary: c ? `Found "${c.sources[0].title}"` : "No relevant documents" },
              ...(signals.length ? [{ name: "read_integrations", summary: `Pulled ${signals.length} person-level signals from Slack, Asana and Monday` }] : []),
            ],
          },
        };
      }
    }

    return {
      message: {
        content: `I can help with two kinds of changes: **redistribute** the existing ${money(total)} weekly envelope between ${teams.length} teams, or **add** new funding and allocate it. I can also explain why a team is tracking over or under.`,
      },
    };
  };
}
