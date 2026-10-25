import type { CompanyDocument, Team } from "@/lib/contracts";

export interface SourceTeamOption { id: string; name: string }

/** Missing directory entries retain their reference without inventing a team name. */
export function sourceTeamName(id: string, teams: Team[]): string {
  return teams.find(team => team.id === id)?.name || `Unknown team (${id})`;
}

export function deriveSourceLibrary(documents: CompanyDocument[], teams: Team[], search: string, teamId?: string) {
  const options = new Map<string, SourceTeamOption>(teams.map(team => [team.id, { id: team.id, name: team.name }]));
  for (const document of documents) for (const id of document.teamIds ?? []) {
    if (!options.has(id)) options.set(id, { id, name: sourceTeamName(id, teams) });
  }
  if (teamId && !options.has(teamId)) options.set(teamId, { id: teamId, name: sourceTeamName(teamId, teams) });
  const words = search.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
  const filtered = documents.filter(document => {
    if (teamId && !document.teamIds?.includes(teamId)) return false;
    const text = [document.title, document.body, document.origin, ...(document.teamIds ?? []).flatMap(id => [id, sourceTeamName(id, teams)])].join(" ").toLocaleLowerCase();
    return words.every(word => text.includes(word));
  }).sort((a, b) => {
    const aDate = Date.parse(a.date), bDate = Date.parse(b.date);
    return (Number.isFinite(bDate) ? bDate : 0) - (Number.isFinite(aDate) ? aDate : 0) || a.id.localeCompare(b.id);
  });
  return { total: documents.length, filtered, teamOptions: [...options.values()].sort((a, b) => a.name.localeCompare(b.name)) };
}

export function sourceDocumentDate(date: string): string {
  const value = new Date(date);
  return Number.isFinite(value.getTime()) ? new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" }).format(value) : "Date unavailable";
}
