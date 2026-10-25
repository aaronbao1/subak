import type { Budget, ContextItem, EvidenceCategory, Forecast, Person, SpendingRecord, Team, Unit } from "@/lib/contracts";
import { teamStatus } from "@/components/team/labels";

/* ------------------------------------------------------------------ */
/* Filters (URL-synced)                                                */
/* ------------------------------------------------------------------ */

export type ScopeFilter = "all" | "company" | "team" | "person";
export type EffectFilter = "all" | "increase" | "decrease";
export type CategoryFilter = "all" | EvidenceCategory;

export interface EvidenceFilters {
  scope: ScopeFilter;
  effect: EffectFilter;
  category: CategoryFilter;
  /** Team id, or undefined for every team. */
  team?: string;
}

export const SCOPE_OPTIONS: ScopeFilter[] = ["all", "company", "team", "person"];
export const EFFECT_OPTIONS: EffectFilter[] = ["all", "increase", "decrease"];
export const CATEGORY_VALUES: EvidenceCategory[] = ["project", "staffing", "policy", "pricing", "model", "macro"];
export const CATEGORY_OPTIONS: CategoryFilter[] = ["all", ...CATEGORY_VALUES];

export const DEFAULT_FILTERS: EvidenceFilters = { scope: "all", effect: "all", category: "all" };

const isScope = (v: string | null): v is ScopeFilter => !!v && (SCOPE_OPTIONS as string[]).includes(v);
const isEffect = (v: string | null): v is EffectFilter => !!v && (EFFECT_OPTIONS as string[]).includes(v);
const isCategory = (v: string | null): v is CategoryFilter => !!v && (CATEGORY_OPTIONS as string[]).includes(v);

/** Unknown or missing params fall back to "all" so a stale link never produces an empty page by accident. */
export function parseFilters(params: URLSearchParams | null, teams: Team[]): EvidenceFilters {
  const scope = params?.get("scope") ?? null;
  const effect = params?.get("effect") ?? null;
  const category = params?.get("category") ?? null;
  const team = params?.get("team") ?? undefined;
  return {
    scope: isScope(scope) ? scope : "all",
    effect: isEffect(effect) ? effect : "all",
    category: isCategory(category) ? category : "all",
    team: team && teams.some((t) => t.id === team) ? team : undefined,
  };
}

/** Only non-default values are written, so the bare URL stays clean. */
export function serializeFilters(f: EvidenceFilters): string {
  const p = new URLSearchParams();
  if (f.scope !== "all") p.set("scope", f.scope);
  if (f.effect !== "all") p.set("effect", f.effect);
  if (f.category !== "all") p.set("category", f.category);
  if (f.team) p.set("team", f.team);
  const s = p.toString();
  return s ? `?${s}` : "";
}

export const isDefaultFilters = (f: EvidenceFilters) => f.scope === "all" && f.effect === "all" && f.category === "all" && !f.team;

/* ------------------------------------------------------------------ */
/* Defaults for optional contract fields                               */
/* ------------------------------------------------------------------ */

export type EvidenceScope = "company" | "team" | "person";

/** Older items without `scope`: a named person makes it a person item, otherwise it is the team's. */
export function scopeOf(item: ContextItem): EvidenceScope {
  if (item.scope) return item.scope;
  return item.personIds && item.personIds.length > 0 ? "person" : "team";
}

/** Until the fixtures carry `category`, every item is a project item. */
export const categoryOf = (item: ContextItem): EvidenceCategory => item.category ?? "project";

/* ------------------------------------------------------------------ */
/* Adjustments: how each item moved a projection                       */
/* ------------------------------------------------------------------ */

export interface ItemAdjustment {
  teamId: string;
  amount: number;
  unit: Unit;
  note?: string;
  /** team: listed on the team forecast; person: summed from person forecasts when the team forecast has none. */
  level: "team" | "person";
}

/**
 * contextId → the signed amounts forecasts attribute to it. Team forecasts are authoritative; person forecasts
 * fill in (summed per team) only for items the team forecast does not list, so nothing is counted twice.
 */
export function indexAdjustments(teamForecasts: Forecast[], personForecasts: Forecast[]): Map<string, ItemAdjustment[]> {
  const out = new Map<string, ItemAdjustment[]>();
  const push = (a: ItemAdjustment, contextId: string) => {
    const list = out.get(contextId) ?? [];
    list.push(a);
    out.set(contextId, list);
  };
  for (const f of teamForecasts) {
    for (const adj of f.adjustments ?? []) push({ teamId: f.teamId, amount: adj.amount, unit: f.unit, note: adj.note, level: "team" }, adj.contextId);
  }
  const personSums = new Map<string, Map<string, { amount: number; unit: Unit }>>();
  for (const f of personForecasts) {
    for (const adj of f.adjustments ?? []) {
      const already = out.get(adj.contextId)?.some((a) => a.teamId === f.teamId && a.level === "team");
      if (already) continue;
      const byTeam = personSums.get(adj.contextId) ?? new Map();
      const cur = byTeam.get(f.teamId) ?? { amount: 0, unit: f.unit };
      cur.amount += adj.amount;
      byTeam.set(f.teamId, cur);
      personSums.set(adj.contextId, byTeam);
    }
  }
  for (const [contextId, byTeam] of personSums) {
    for (const [teamId, { amount, unit }] of byTeam) push({ teamId, amount, unit, level: "person" }, contextId);
  }
  return out;
}

/* ------------------------------------------------------------------ */
/* Evidence rows                                                       */
/* ------------------------------------------------------------------ */

export interface EvidenceRow {
  item: ContextItem;
  scope: EvidenceScope;
  category: EvidenceCategory;
  teams: Team[];
  people: Person[];
  adjustments: ItemAdjustment[];
  superseded: boolean;
  /** The item that replaced this one, when it is known. */
  newer?: ContextItem;
}

export function buildRows(context: ContextItem[], teams: Team[], people: Person[], adjustments: Map<string, ItemAdjustment[]>): EvidenceRow[] {
  const teamById = new Map(teams.map((t) => [t.id, t]));
  const personById = new Map(people.map((p) => [p.id, p]));
  return context.map((item) => ({
    item,
    scope: scopeOf(item),
    category: categoryOf(item),
    teams: item.teamIds.map((id) => teamById.get(id)).filter((t): t is Team => !!t),
    people: (item.personIds ?? []).map((id) => personById.get(id)).filter((p): p is Person => !!p),
    adjustments: adjustments.get(item.id) ?? [],
    superseded: !!item.supersededBy,
    newer: item.supersededBy ? context.find((c) => c.id === item.supersededBy) : undefined,
  }));
}

export function applyFilters(rows: EvidenceRow[], f: EvidenceFilters): EvidenceRow[] {
  return rows.filter((r) => {
    if (f.scope !== "all" && r.scope !== f.scope) return false;
    if (f.effect !== "all" && r.item.expectedEffect !== f.effect) return false;
    if (f.category !== "all" && r.category !== f.category) return false;
    if (f.team && !r.item.teamIds.includes(f.team)) return false;
    return true;
  });
}

/** Current before superseded, then newest `effectiveFrom` first; undated items sink below dated ones. */
export function sortRows(rows: EvidenceRow[]): EvidenceRow[] {
  return [...rows].sort((a, b) => {
    const s = Number(a.superseded) - Number(b.superseded);
    if (s !== 0) return s;
    return (b.item.effectiveFrom ?? "").localeCompare(a.item.effectiveFrom ?? "");
  });
}

export const SCOPE_ORDER: EvidenceScope[] = ["company", "team", "person"];
export const SCOPE_GROUP_LABEL: Record<EvidenceScope, string> = { company: "Company-wide", team: "Teams", person: "People" };

export function groupByScope(rows: EvidenceRow[]): { scope: EvidenceScope; rows: EvidenceRow[] }[] {
  return SCOPE_ORDER.map((scope) => ({ scope, rows: sortRows(rows.filter((r) => r.scope === scope)) })).filter((g) => g.rows.length > 0);
}

/* ------------------------------------------------------------------ */
/* The projection strip: baseline → adjustments → projected            */
/* ------------------------------------------------------------------ */

export interface ProjectionTotals {
  unit: Unit;
  /** Σ projected over available team forecasts. */
  projected: number;
  /** Σ (baseline ?? projected). Only meaningful when `hasBaseline`. */
  baseline: number;
  /** Signed Σ of every team-level adjustment. */
  adjustments: number;
  /** Distinct evidence items the forecasts applied. */
  appliedItems: number;
  hasBaseline: boolean;
  hasAdjustments: boolean;
  teamsProjected: number;
  teamsTotal: number;
  /** True when any contributing forecast excludes incurred spend; the strip then says so. */
  anyRemaining: boolean;
  anyScenario: boolean;
  periodLabel?: string;
}

export function projectionTotals(teamForecasts: Forecast[], teams: Team[], fallbackUnit: Unit): ProjectionTotals {
  const available = teamForecasts.filter((f) => f.status === "available" && typeof f.projected === "number");
  const unit = available[0]?.unit ?? teamForecasts[0]?.unit ?? fallbackUnit;
  const applied = new Set<string>();
  let adjustments = 0;
  for (const f of teamForecasts) for (const a of f.adjustments ?? []) { adjustments += a.amount; applied.add(a.contextId); }
  return {
    unit,
    projected: available.reduce((s, f) => s + (f.projected as number), 0),
    baseline: available.reduce((s, f) => s + (typeof f.baseline === "number" ? f.baseline : (f.projected as number)), 0),
    adjustments,
    appliedItems: applied.size,
    hasBaseline: available.some((f) => typeof f.baseline === "number"),
    hasAdjustments: teamForecasts.some((f) => (f.adjustments?.length ?? 0) > 0),
    teamsProjected: available.length,
    teamsTotal: teams.length,
    anyRemaining: available.some((f) => f.basis === "remaining"),
    anyScenario: available.some((f) => f.kind === "scenario"),
    periodLabel: available.find((f) => f.period.label)?.period.label,
  };
}

/* ------------------------------------------------------------------ */
/* Impact by team                                                      */
/* ------------------------------------------------------------------ */

export interface TeamImpact {
  team: Team;
  /** Current (non-superseded) rows in the active scope/effect/category filters that touch this team. */
  items: number;
  /** Signed Σ of the team forecast's adjustments, in `unit`. 0 when the forecast lists none. */
  net: number;
  unit: Unit;
  hasAdjustments: boolean;
  /** The increase pushes the team's projection past its allotment. */
  overAllotment: boolean;
}

export function teamImpacts(
  teams: Team[],
  rows: EvidenceRow[],
  teamForecasts: Forecast[],
  budgets: Budget[],
  spending: SpendingRecord[],
  fallbackUnit: Unit,
): TeamImpact[] {
  return teams.map((team) => {
    const forecast = teamForecasts.find((f) => f.teamId === team.id);
    const budget = budgets.find((b) => b.teamId === team.id);
    const spent = spending.filter((r) => r.teamId === team.id).reduce((s, r) => s + r.amount, 0);
    const adjustments = forecast?.adjustments ?? [];
    const net = adjustments.reduce((s, a) => s + a.amount, 0);
    const status = teamStatus(budget, forecast, spent);
    return {
      team,
      items: rows.filter((r) => !r.superseded && r.item.teamIds.includes(team.id)).length,
      net,
      unit: forecast?.unit ?? budget?.unit ?? fallbackUnit,
      hasAdjustments: adjustments.length > 0,
      overAllotment: net > 0 && status === "likely_over",
    };
  });
}

/* ------------------------------------------------------------------ */
/* People affected                                                     */
/* ------------------------------------------------------------------ */

export interface AffectedPerson {
  person: Person;
  team?: Team;
  /** The newest current item naming this person; superseded items only count when nothing current does. */
  item: ContextItem;
  /** Further items naming the same person. */
  more: number;
}

export function peopleAffected(rows: EvidenceRow[], teams: Team[]): AffectedPerson[] {
  const byPerson = new Map<string, { person: Person; items: EvidenceRow[] }>();
  for (const r of rows) {
    for (const p of r.people) {
      const e = byPerson.get(p.id) ?? { person: p, items: [] };
      e.items.push(r);
      byPerson.set(p.id, e);
    }
  }
  return [...byPerson.values()]
    .map(({ person, items }) => {
      const sorted = sortRows(items);
      return { person, team: teams.find((t) => t.id === person.teamId), item: sorted[0].item, more: sorted.length - 1 };
    })
    .sort((a, b) => (a.team?.name ?? "").localeCompare(b.team?.name ?? "") || a.person.name.localeCompare(b.person.name));
}

/* ------------------------------------------------------------------ */
/* Macro watch                                                         */
/* ------------------------------------------------------------------ */

const DAY_MS = 86_400_000;
const toTs = (iso: string) => { const [y, m, d] = iso.split("-").map(Number); return Date.UTC(y, m - 1, d); };

export interface MacroBuckets {
  /** In effect now or starting within the window, soonest first. */
  soon: EvidenceRow[];
  /** Starts after the window. */
  later: EvidenceRow[];
  /** Ended before today, or superseded. */
  past: EvidenceRow[];
}

/** Company-scope items split around a `days`-long window from `today` (an ISO date). */
export function macroBuckets(rows: EvidenceRow[], today: string, days = 14): MacroBuckets {
  const t0 = toTs(today);
  const t1 = t0 + days * DAY_MS;
  const company = rows.filter((r) => r.scope === "company");
  const soon: EvidenceRow[] = [], later: EvidenceRow[] = [], past: EvidenceRow[] = [];
  for (const r of company) {
    const from = r.item.effectiveFrom ? toTs(r.item.effectiveFrom) : undefined;
    const to = r.item.effectiveTo ? toTs(r.item.effectiveTo) : undefined;
    if (r.superseded || (to !== undefined && to < t0)) past.push(r);
    else if (from !== undefined && from > t1) later.push(r);
    else soon.push(r);
  }
  const asc = (a: EvidenceRow, b: EvidenceRow) => (a.item.effectiveFrom ?? "").localeCompare(b.item.effectiveFrom ?? "");
  return { soon: soon.sort(asc), later: later.sort(asc), past: past.sort(asc).reverse() };
}

export const todayIso = () => new Date().toISOString().slice(0, 10);
