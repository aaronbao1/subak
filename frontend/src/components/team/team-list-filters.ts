export type TeamSort = "spend" | "name" | "projection" | "variance";
export interface TeamFilters { query: string; sort: TeamSort }

export function parseTeamFilters(params: Pick<URLSearchParams, "get">): TeamFilters {
  const sort = params.get("sort");
  return { query: params.get("q") ?? "", sort: sort === "name" || sort === "projection" || sort === "variance" ? sort : "spend" };
}

export function teamFilterQuery(params: Pick<URLSearchParams, "toString">, filters: TeamFilters): string {
  const next = new URLSearchParams(params.toString());
  if (filters.query) next.set("q", filters.query); else next.delete("q");
  if (filters.sort !== "spend") next.set("sort", filters.sort); else next.delete("sort");
  return next.toString();
}

interface FilterableTeamRow {
  team: { name: string; lead?: string; description?: string };
  spent: number | null;
  projected: number | null;
  variance: number | null;
}

export function filterTeamRows<T extends FilterableTeamRow>(rows: T[], filters: TeamFilters): T[] {
  const query = filters.query.trim().toLocaleLowerCase();
  return rows.filter(({ team }) => !query || [team.name, team.lead, team.description].some(value => value?.toLocaleLowerCase().includes(query))).sort((a, b) => {
    const byName = a.team.name.localeCompare(b.team.name);
    if (filters.sort === "name") return byName;
    const key = filters.sort === "spend" ? "spent" : filters.sort === "projection" ? "projected" : "variance";
    const left = a[key], right = b[key];
    if (left == null) return right == null ? byName : 1;
    if (right == null) return -1;
    return right - left || byName;
  });
}
