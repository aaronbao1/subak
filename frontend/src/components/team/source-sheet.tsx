"use client";
import { displayCopy, displayReference, displaySourceText } from "@/lib/display-copy";
import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import { History } from "lucide-react";
import type { CompanyDocument } from "@/lib/contracts";
import { getDataClient } from "@/lib/data";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { fmtDate, KIND_LABEL } from "./labels";
import { SourceBadge } from "@/components/context/source-brand";

interface Props {
  documentId?: string;
  onClose: () => void;
}

type Loaded =
  | { id: string; status: "missing" | "error" }
  | { id: string; status: "ready"; doc: CompanyDocument; newer?: CompanyDocument };

type LoadState = Loaded | { status: "loading" };

const MARKDOWN =
  "text-sm leading-relaxed text-foreground/80 " +
  "[&_h1]:mb-2 [&_h1]:text-base [&_h1]:font-medium [&_h1]:text-foreground " +
  "[&_h2]:mt-5 [&_h2]:mb-1.5 [&_h2]:text-sm [&_h2]:font-medium [&_h2]:text-foreground " +
  "[&_h3]:mt-4 [&_h3]:mb-1 [&_h3]:text-sm [&_h3]:font-medium [&_h3]:text-foreground " +
  "[&_p]:mb-3 [&_ul]:mb-3 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:mb-3 [&_ol]:list-decimal [&_ol]:pl-5 [&_li]:mb-1 [&_li]:marker:text-muted-foreground " +
  "[&_strong]:font-medium [&_strong]:text-foreground " +
  "[&_blockquote]:my-3 [&_blockquote]:border-l [&_blockquote]:border-border-strong [&_blockquote]:pl-3 [&_blockquote]:text-muted-foreground " +
  "[&_code]:rounded-sm [&_code]:bg-popover [&_code]:px-1 [&_code]:py-0.5 [&_code]:font-mono [&_code]:text-[12px] [&_code]:text-foreground " +
  "[&_pre]:mb-3 [&_pre]:overflow-x-auto [&_pre]:rounded-md [&_pre]:border [&_pre]:border-border [&_pre]:bg-popover [&_pre]:p-3 [&_pre_code]:bg-transparent [&_pre_code]:p-0 " +
  "[&_a]:text-foreground [&_a]:underline [&_a]:underline-offset-4 [&_a]:decoration-border-strong hover:[&_a]:decoration-foreground " +
  "[&_table]:mb-3 [&_table]:w-full [&_table]:text-xs [&_th]:border-b [&_th]:border-border-strong [&_th]:pb-1 [&_th]:text-left [&_th]:font-medium [&_th]:text-muted-foreground [&_td]:border-b [&_td]:border-border [&_td]:py-1 [&_td]:align-top [&_td]:tabular-nums " +
  "[&_hr]:my-4 [&_hr]:border-border";

/** Full source document in a side sheet, rendered from markdown with origin, date and supersession notice. */
export function SourceSheet({ documentId, onClose }: Props) {
  const [loaded, setLoaded] = useState<Loaded | undefined>();
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!documentId) return;
    let cancelled = false;
    (async () => {
      try {
        const client = getDataClient();
        const doc = await client.getDocument(documentId);
        if (cancelled) return;
        if (!doc) { setLoaded({ id: documentId, status: "missing" }); return; }
        // A failed linked-version lookup must not hide the received source itself.
        const newer = doc.supersededBy ? await client.getDocument(doc.supersededBy).catch(() => undefined) : undefined;
        if (cancelled) return;
        setLoaded({ id: documentId, status: "ready", doc, newer });
      } catch {
        if (!cancelled) setLoaded({ id: documentId, status: "error" });
      }
    })();
    return () => { cancelled = true; };
  }, [documentId, attempt]);

  // Loading is derived: the stored result belongs to a different (or no) document id.
  const state: LoadState = loaded && loaded.id === documentId ? loaded : { status: "loading" };

  return (
    <Sheet open={!!documentId} onOpenChange={(open) => { if (!open) onClose(); }}>
      <SheetContent side="right" className="w-full gap-0 sm:max-w-lg">
        {state.status === "loading" && (
          <>
            <SheetHeader className="border-b border-border pr-12">
              <SheetTitle>Loading source…</SheetTitle>
              <SheetDescription className="text-xs">Fetching the document.</SheetDescription>
            </SheetHeader>
            <div className="space-y-2.5 px-4 pt-4">
              <Skeleton className="h-3.5 w-3/4" />
              <Skeleton className="h-3.5 w-full" />
              <Skeleton className="h-3.5 w-5/6" />
              <Skeleton className="mt-4 h-3.5 w-2/3" />
              <Skeleton className="h-3.5 w-full" />
            </div>
          </>
        )}

        {state.status === "error" && <>
          <SheetHeader className="pr-12">
            <SheetTitle>Source could not be loaded</SheetTitle>
            <SheetDescription className="text-xs">The source is temporarily unavailable. Try again.</SheetDescription>
          </SheetHeader>
          <div className="px-4 pt-3"><button type="button" onClick={() => { setLoaded(undefined); setAttempt(value => value + 1); }} className="rounded-md border border-border px-3 py-2 text-sm hover:bg-muted">Retry source</button></div>
        </>}

        {state.status === "missing" && (
          <SheetHeader className="pr-12">
            <SheetTitle>Source not found</SheetTitle>
            <SheetDescription className="text-xs">The requested document is unavailable. Reference: <code className="rounded-sm bg-popover px-1 font-mono text-xs">{displayReference(documentId, "Saved document")}</code>.</SheetDescription>
          </SheetHeader>
        )}

        {state.status === "ready" && (
          <>
            <SheetHeader className="gap-1 border-b border-border pr-12">
              <div className="flex items-center gap-2">
                <SourceBadge integration={state.doc.integration ?? "document"} size="xs" />
                <span aria-hidden className="text-muted-foreground/60">·</span>
                <div className="eyebrow">{KIND_LABEL[state.doc.kind]}</div>
              </div>
              <SheetTitle className="leading-snug">{displaySourceText(state.doc.title, "Source document")}</SheetTitle>
              <SheetDescription className="flex flex-wrap items-center gap-x-1.5 text-xs">
                <span className="num">{fmtDate(state.doc.date, { year: true })}</span>
                <span aria-hidden>·</span>
                <span>{displayCopy(state.doc.origin, "Saved source")}</span>
              </SheetDescription>
            </SheetHeader>
            <ScrollArea className="min-h-0 flex-1">
              <div className="px-4 py-4">
                {state.doc.supersededBy && (
                  <div className="mb-4 flex gap-2.5 rounded-md border border-dashed border-border-strong bg-popover px-3 py-2.5 text-xs text-muted-foreground" role="note">
                    <History className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden strokeWidth={1.5} />
                    <div>
                      <div className="font-medium text-foreground/80">Superseded document</div>
                      <p className="mt-0.5">
                        Replaced by <span className="text-foreground/80">{state.newer ? displaySourceText(state.newer.title, "Updated document") : displayReference(state.doc.supersededBy, "Updated document")}</span>
                        {state.newer?.date && <> (<span className="num">{fmtDate(state.newer.date, { year: true })}</span>)</>}. Kept for traceability; not current.
                      </p>
                    </div>
                  </div>
                )}
                <div className={MARKDOWN}>
                  <ReactMarkdown>{displaySourceText(state.doc.body, "Document content is unavailable.")}</ReactMarkdown>
                </div>
              </div>
            </ScrollArea>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
