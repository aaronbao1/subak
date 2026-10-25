"use client";

import { useEffect, useMemo, useState } from "react";
import { FileText, Search } from "lucide-react";
import type { CompanyDocument, Team } from "@/lib/contracts";
import { getDataClient } from "@/lib/data";
import { displayCopy, displaySourceText } from "@/lib/display-copy";
import { SourceSheet } from "@/components/team/source-sheet";
import { deriveSourceLibrary, sourceDocumentDate, sourceTeamName } from "./source-library-derive";

export interface SourceLibraryProps {
  teams: Team[];
  search: string;
  onSearch: (query: string) => void;
  teamId?: string;
  onTeamChange: (id?: string) => void;
}

const PAGE_SIZE = 12;
interface LoadState { documents?: CompanyDocument[]; loading: boolean; failed: boolean }

export function SourceLibrary({ teams, search, onSearch, teamId, onTeamChange }: SourceLibraryProps) {
  const [state, setState] = useState<LoadState>({ loading: true, failed: false });
  const [attempt, setAttempt] = useState(0);
  const [documentId, setDocumentId] = useState<string>();
  const [page, setPage] = useState({ key: "", limit: PAGE_SIZE });
  const filterKey = JSON.stringify([search, teamId]);
  const limit = page.key === filterKey ? page.limit : PAGE_SIZE;
  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const documents = await getDataClient().getDocuments();
        if (active) setState({ documents, loading: false, failed: false });
      } catch {
        if (active) setState(previous => ({ ...previous, loading: false, failed: true }));
      }
    })();
    return () => { active = false; };
  }, [attempt]);
  const data = useMemo(() => deriveSourceLibrary(state.documents ?? [], teams, search, teamId), [state.documents, teams, search, teamId]);
  const reload = () => {
    setState(previous => ({ ...previous, loading: true, failed: false }));
    setAttempt(previous => previous + 1);
  };

  return <section className="space-y-3" aria-label="Source library" aria-busy={state.loading}>
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex min-w-48 flex-1 items-center gap-2 rounded-md border border-border bg-background px-3">
          <Search className="size-4 shrink-0 text-muted-foreground" aria-hidden />
          <input aria-label="Search source documents" placeholder="Search documents, sources or teams" value={search} onChange={event => onSearch(event.target.value)} className="h-9 min-w-0 w-full bg-transparent text-sm outline-none" />
        </label>
        <select aria-label="Filter source documents by team" value={teamId ?? ""} onChange={event => onTeamChange(event.target.value || undefined)} className="h-9 max-w-full rounded-md border border-border bg-background px-3 text-sm">
          <option value="">All teams</option>
          {data.teamOptions.map(team => <option key={team.id} value={team.id}>{displaySourceText(team.name, "Unnamed team")}</option>)}
        </select>
        <button type="button" onClick={reload} disabled={state.loading} className="h-9 rounded-md border border-border px-3 text-xs hover:bg-muted disabled:opacity-50">{state.loading ? "Loading…" : state.failed ? "Retry" : "Refresh"}</button>
      </div>
      <p className="mt-3 text-xs text-muted-foreground" aria-live="polite">{state.documents === undefined ? state.failed ? "Document count unavailable." : "Loading source documents…" : `${data.filtered.length} of ${data.total} ${data.total === 1 ? "document" : "documents"}`}</p>
    </div>
    {state.failed && <p role="alert" className="rounded-lg border border-border bg-card px-4 py-3 text-sm">{state.documents === undefined ? "Source documents could not be loaded. Retry to try again." : "Source documents could not be refreshed. Showing the last loaded documents."}</p>}
    {state.documents !== undefined && data.filtered.length === 0 && <p className="rounded-xl border border-border bg-card p-5 text-sm text-muted-foreground">{data.total === 0 ? "No source documents have been received." : "No documents match this search and team filter."}</p>}
    {data.filtered.length > 0 && <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-card">
      {data.filtered.slice(0, limit).map(document => <li key={document.id}>
        <button type="button" onClick={() => setDocumentId(document.id)} className="flex w-full gap-3 px-4 py-4 text-left transition-colors hover:bg-muted/50 focus-visible:outline-2 focus-visible:outline-ring">
          <FileText className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
          <span className="min-w-0 flex-1">
            <span className="flex flex-wrap items-center gap-2"><span className="text-sm font-medium">{displaySourceText(document.title, "Untitled document")}</span>{document.supersededBy && <span className="rounded border border-border px-1.5 py-0.5 text-[10px] text-muted-foreground">Superseded</span>}</span>
            <span className="mt-1 block text-xs text-muted-foreground">{sourceDocumentDate(document.date)} · {displayCopy(document.origin, "Origin not specified")}</span>
            <span className="mt-2 flex flex-wrap gap-1.5">{document.teamIds?.length ? document.teamIds.map(id => <span key={id} className="rounded border border-border px-1.5 py-0.5 text-[11px] text-muted-foreground">{displaySourceText(sourceTeamName(id, teams))}</span>) : <span className="text-[11px] text-muted-foreground">No team specified</span>}</span>
          </span>
        </button>
      </li>)}
    </ul>}
    {data.filtered.length > limit && <button type="button" onClick={() => setPage({ key: filterKey, limit: limit + PAGE_SIZE })} className="w-full rounded-lg border border-border bg-card py-3 text-sm hover:bg-muted">Show {Math.min(PAGE_SIZE, data.filtered.length - limit)} more documents <span className="text-muted-foreground">({data.filtered.length - limit} remaining)</span></button>}
    <SourceSheet documentId={documentId} onClose={() => setDocumentId(undefined)} />
  </section>;
}
