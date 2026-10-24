/**
 * Scalable synthetic company generator: 0..16 teams, deterministic per team count.
 * Used when the URL has ?teams=N. Northstar (src/fixtures/index.ts) stays the plan's canonical 3-team example.
 */
import type {
  AllocationProposal, AssistantMessage, Budget, Company, CompanyDocument, ContextItem, Decision, Forecast,
  Period, SpendingRecord, Team,
} from "@/lib/contracts";

export interface Dataset {
  company: Company;
  teams: Team[];
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

export const period: Period = { start: "2026-10-01", end: "2026-12-31", label: "Current planning period" };
export const asOf = "2026-10-22";
const DAYS_RECORDED = 22;
const DAYS_IN_PERIOD = 92;
const WEEKENDS = new Set([3, 4, 10, 11, 17, 18]);

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

/** Daily records Oct 1..22 that sum EXACTLY to `target`. Exported so Northstar uses the same shape. */
export function dailySeries(
  teamId: string,
  target: number,
  mix: Record<SpendingRecord["component"], number>,
  provider: string,
  ramp: (day: number) => number = () => 1,
  seed = 1,
): SpendingRecord[] {
  const rnd = mulberry32(seed);
  const raw: Omit<SpendingRecord, "amount">[] = [];
  const weights: number[] = [];
  for (let d = 1; d <= DAYS_RECORDED; d++) {
    const date = `2026-10-${String(d).padStart(2, "0")}`;
    for (const [component, w] of Object.entries(mix) as [SpendingRecord["component"], number][]) {
      const fixed = component === "subscription";
      const activity = fixed ? 1 : (WEEKENDS.has(d) ? 0.3 : 1) * ramp(d) * (0.8 + rnd() * 0.4);
      weights.push(w * activity);
      raw.push({
        id: `${teamId}-${date}-${component}`,
        teamId, date, component, provider, unit: "usd",
        provenance: component === "api" || component === "subscription" ? "reported_charge" : component === "included_usage" ? "usage_only" : "estimate",
        source: component === "api" || component === "subscription"
          ? `${provider === "anthropic" ? "Anthropic" : "OpenAI"} cost report export ${asOf}`
          : `Cursor Admin API export ${asOf}`,
        complete: d <= DAYS_RECORDED - 1,
      });
    }
  }
  if (target <= 0 || raw.length === 0) return raw.map((r) => ({ ...r, amount: 0 }));
  const total = weights.reduce((a, b) => a + b, 0);
  const out = raw.map((r, i) => ({ ...r, amount: Math.round((weights[i] / total) * target) }));
  out[out.length - 1].amount += target - out.reduce((s, r) => s + r.amount, 0);
  return out;
}

const CONTEXT_TEMPLATES: Array<(t: Team) => Omit<ContextItem, "id" | "teamIds"> & { body: string; origin: string }> = [
  (t) => ({
    title: `${t.name} plan expands AI-assisted work this period`, kind: "plan", claimType: "stated_plan",
    summary: `An approved ${t.name} plan increases AI tool and API usage starting mid-October and continuing through the planning period.`,
    effectiveFrom: "2026-10-14", effectiveTo: period.end, expectedEffect: "increase", confidence: "high",
    sources: [{ documentId: `doc-${t.id}-plan`, title: `${t.name} plan (approved)`, excerpt: "Usage of coding assistants and API-driven automation is expected to roughly double from mid-October.", locator: "§2", date: "2026-10-06", kind: "plan" }],
    uncertainty: "The plan does not estimate cost; the projection impact is a forecasting decision.",
    origin: "Uploaded PDF", body: `# ${t.name} plan\n\n## 2. Scope\n\nUsage of coding assistants and API-driven automation is expected to roughly double from mid-October through the end of the period. Headcount is unchanged.`,
  }),
  (t) => ({
    title: `${t.name} milestone deferred to next period`, kind: "project_doc", claimType: "stated_plan",
    summary: `A roadmap update defers ${t.name}'s main Q4 milestone into the following period, reducing near-term work relative to the earlier plan.`,
    effectiveFrom: "2026-10-15", effectiveTo: period.end, expectedEffect: "decrease", confidence: "medium",
    sources: [{ documentId: `doc-${t.id}-roadmap`, title: `${t.name} roadmap update`, excerpt: "The milestone moves into the next period; the team shifts to stabilization.", locator: "p.1", date: "2026-10-15", kind: "project_doc" }],
    uncertainty: "Stabilization could still consume tooling if incident load is high.",
    origin: "Notion export", body: `# ${t.name} roadmap update\n\nThe milestone moves into the next period. The team shifts to stabilization and escalations for the remainder of this period.`,
  }),
  (t) => ({
    title: `${t.name} work continues at current pace`, kind: "project_doc", claimType: "stated_plan",
    summary: `A team note confirms ${t.name} continues current work through the period with no planned change in tool use.`,
    effectiveFrom: period.start, effectiveTo: period.end, expectedEffect: "neutral", confidence: "medium",
    sources: [{ documentId: `doc-${t.id}-note`, title: `${t.name} status note`, excerpt: "On track; steady effort expected through December.", date: "2026-10-12", kind: "project_doc" }],
    origin: "Uploaded Markdown", body: `# ${t.name} status\n\nOn track; steady effort expected through December with no staffing or tooling change.`,
  }),
];

export function generateCompany(teamCount: number): Dataset {
  const n = Math.max(0, Math.min(MAX_TEAMS, Math.floor(teamCount)));
  const rnd = mulberry32(1000 + n);
  const pool = TEAM_POOL.slice(0, n);

  const teams: Team[] = pool.map((p, i) => ({ id: slug(p.name), name: p.name, description: p.description, lead: p.lead, color: teamColor(i, n) }));

  const budgets: Budget[] = teams.map((t) => ({
    teamId: t.id, period, unit: "usd", version: "v1",
    allocated: Math.round((20_000 + rnd() * 120_000) / 5_000) * 5_000,
  }));

  const spending: SpendingRecord[] = [];
  const forecasts: Forecast[] = [];
  teams.forEach((t, i) => {
    const p = pool[i];
    const alloc = budgets[i].allocated;
    const dailyRate = (alloc / DAYS_IN_PERIOD) * p.pace;
    const spent = Math.round((dailyRate * DAYS_RECORDED) / 100) * 100;
    const ramp = p.pace > 1.2 ? (d: number) => (d >= 14 ? 1.5 : 1) : p.pace < 0.7 ? (d: number) => (d >= 15 ? 0.6 : 1) : () => 1;
    spending.push(...dailySeries(t.id, spent, p.mix, p.provider, ramp, 7 + i));
    const projected = Math.round((dailyRate * DAYS_IN_PERIOD) / 1_000) * 1_000;
    const unavailable = n > 3 && i % 5 === 4;
    forecasts.push(
      unavailable
        ? {
            id: `fc-${t.id}-1`, teamId: t.id, period, status: "unavailable", unit: "usd", basis: "full_period", kind: "forecast", origin: "placeholder",
            assumptions: [], limitations: ["Fewer than 14 complete days of attributable data"],
            unavailableReason: `Insufficient history for ${t.name} after its provider workspace was re-mapped on Oct 9.`,
            generatedAt: "2026-10-22T09:00:00Z",
          }
        : {
            id: `fc-${t.id}-1`, teamId: t.id, period, status: "available", unit: "usd", basis: "full_period", kind: "forecast", origin: "placeholder",
            projected, low: Math.round((projected * 0.88) / 1_000) * 1_000, high: Math.round((projected * 1.13) / 1_000) * 1_000,
            assumptions: [p.pace > 1.2 ? "Planned expansion continues through the period" : p.pace < 0.7 ? "Deferred milestone keeps activity low" : "Steady state"],
            limitations: ["Shared placeholder projection, not the output of a selected model", "Oct 22 data is partial"],
            generatedAt: "2026-10-22T09:00:00Z",
          },
    );
  });

  const context: ContextItem[] = [];
  const documents: CompanyDocument[] = [];
  teams.forEach((t, i) => {
    const p = pool[i];
    const tpl = CONTEXT_TEMPLATES[p.pace > 1.2 ? 0 : p.pace < 0.7 ? 1 : 2](t);
    const { body, origin, ...item } = tpl;
    context.push({ id: `ctx-${t.id}-1`, teamIds: [t.id], ...item });
    const src = item.sources[0];
    documents.push({ id: src.documentId, title: src.title, kind: item.kind, date: src.date ?? asOf, teamIds: [t.id], origin, body });
  });

  const company: Company = {
    id: `synthetic-${n}`, name: n === 0 ? "New Company (no teams yet)" : `Northstar Software (${n} teams)`,
    isDemo: true, budgetUnit: "usd", currentPeriod: period,
  };

  const over = teams.filter((t, i) => (forecasts[i].projected ?? 0) > budgets[i].allocated).map((t) => t.name);
  const threads: Record<string, AssistantMessage[]> = {
    main: [{
      id: "msg-welcome", threadId: "main", role: "assistant", createdAt: "2026-10-22T09:05:00Z",
      content: n === 0
        ? "No teams are set up yet. Once the backend supplies teams and budgets, I can help you plan allocations."
        : over.length
          ? `**${over.join(", ")}** ${over.length === 1 ? "is" : "are"} projected over allocation this period. I can redistribute the existing envelope or allocate new funding if finance authorizes it.`
          : "Every team is projected within its allocation this period. Ask me to compare teams or explain any projection.",
    }],
  };

  return {
    company, teams, budgets, spending, forecasts, context, documents, proposals: [], decisions: [], threads,
    scriptedReply: makeGenericReply(teams, forecasts, context),
  };
}

/** Generic assistant for N teams: add funding proportional to projected gaps; redistribute from under- to over-allocated teams. */
export function makeGenericReply(teams: Team[], forecasts: Forecast[], context: ContextItem[]): ScriptedReplyFn {
  const sources = context.filter((c) => !c.supersededBy).flatMap((c) => c.sources);
  const fc = (id: string) => forecasts.find((f) => f.teamId === id);
  const round = (x: number) => Math.round(x / 1_000) * 1_000;
  const money = (x: number) => `$${x.toLocaleString("en-US")}`;

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

    const amountMatch = text.match(/(\d{1,3}(?:[, ]\d{3})+|\d+)\s*k?/);
    const parsedAmount = (() => {
      if (!amountMatch) return 50_000;
      const raw = amountMatch[1].replace(/[, ]/g, "");
      const num = Number(raw);
      return /k\b/.test(amountMatch[0]) ? num * 1_000 : num < 1_000 ? num * 1_000 : num;
    })();

    if (/\badd|additional|more (credits|budget|funding)|authoriz|\d+k\b|\d{2},?\d{3}/.test(text)) {
      const amount = parsedAmount;
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
          ? `Distributed ${money(amount)} in proportion to each team's projected shortfall (projection minus allocation). Teams projected within allocation receive nothing new.`
          : `No team is projected over allocation, so the full ${money(amount)} is parked with ${teams[0].name} pending a finance decision.`,
      };
      const bullets = lines.filter((l) => l.after !== l.before).map((l) => `- **${teams.find((t) => t.id === l.teamId)!.name} +${money(l.after - l.before)}** → ${money(l.after)}`).join("\n");
      return {
        proposal,
        message: {
          content: `Here's how I'd allocate the additional **${money(amount)}**:\n\n${bullets}\n\nEnvelope goes from **${money(total)} to ${money(total + amount)}**.`,
          proposalId: proposal.id, citations: sources,
          toolCalls: [
            { name: "get_spending", summary: `Pulled Oct 1–22 spending for ${teams.length} teams` },
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
        rationale: `Moved ${money(taken)} from teams projected under allocation to teams projected over it, in proportion to headroom and shortfall. The ${money(total)} envelope is unchanged.`,
      };
      const bullets = lines.filter((l) => l.after !== l.before).map((l) => `- **${teams.find((t) => t.id === l.teamId)!.name} ${l.after > l.before ? "+" : "−"}${money(Math.abs(l.after - l.before))}** → ${money(l.after)}`).join("\n");
      return {
        proposal,
        message: {
          content: `Without adding funding, I'd move **${money(taken)}** between teams:\n\n${bullets}\n\nEnvelope stays at **${money(total)}**.`,
          proposalId: proposal.id, citations: sources,
          toolCalls: [
            { name: "get_budgets", summary: `Read current allocations (${money(total)} envelope)` },
            { name: "get_forecasts", summary: "Compared projections to allocations" },
          ],
        },
      };
    }

    if (/why|explain|over|under|exceed/.test(text)) {
      const named = teams.find((t) => text.includes(t.name.toLowerCase()));
      if (named) {
        const f = fc(named.id);
        const c = context.find((x) => x.teamIds.includes(named.id));
        const status = f?.status !== "available" ? "has no available projection" : (f.projected ?? 0) > alloc(named.id) ? `is projected at ${money(f.projected!)} against ${money(alloc(named.id))}` : `is projected at ${money(f.projected!)} against ${money(alloc(named.id))}, within allocation`;
        return {
          message: {
            content: `**${named.name}** ${status}.${c ? ` ${c.summary}` : ""}`,
            citations: c?.sources,
            toolCalls: [{ name: "get_forecasts", summary: `Read ${named.name} projection` }, { name: "search_documents", summary: c ? `Found "${c.sources[0].title}"` : "No relevant documents" }],
          },
        };
      }
    }

    return {
      message: {
        content: `I can help with two kinds of changes: **redistribute** the existing ${money(total)} envelope between ${teams.length} teams, or **add** new funding and allocate it. I can also explain why a team is tracking over or under.`,
      },
    };
  };
}
