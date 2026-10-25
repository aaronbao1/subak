"use client";
import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import { History } from "lucide-react";
import type { CompanyDocument } from "@/lib/contracts";
import { getDataClient } from "@/lib/data";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { fmtDate } from "./labels";

interface Props {
  documentId?: string;
  onClose: () => void;
}

const KIND_LABEL: Record<CompanyDocument["kind"], string> = {
  plan: "Plan",
  project_doc: "Project document",
  research_note: "Research note",
  correspondence: "Correspondence",
};

type Loaded =
  | { id: string; status: "missing" }
  | { id: string; status: "ready"; doc: CompanyDocument; newer?: CompanyDocument };

type LoadState = Loaded | { status: "loading" };

/** Full source document in a side sheet, rendered from markdown with origin, date and supersession notice. */
export function SourceSheet({ documentId, onClose }: Props) {
  const [loaded, setLoaded] = useState<Loaded | undefined>();

  useEffect(() => {
    if (!documentId) return;
    let cancelled = false;
    (async () => {
      const client = getDataClient();
      const doc = await client.getDocument(documentId);
      if (cancelled) return;
      if (!doc) { setLoaded({ id: documentId, status: "missing" }); return; }
      const newer = doc.supersededBy ? await client.getDocument(doc.supersededBy) : undefined;
      if (cancelled) return;
      setLoaded({ id: documentId, status: "ready", doc, newer });
    })();
    return () => { cancelled = true; };
  }, [documentId]);

  // Loading is derived: the stored result belongs to a different (or no) document id.
  const state: LoadState = loaded && loaded.id === documentId ? loaded : { status: "loading" };

  return (
    <Sheet open={!!documentId} onOpenChange={(open) => { if (!open) onClose(); }}>
      <SheetContent side="right" className="w-full sm:max-w-lg">
        {state.status === "loading" && (
          <>
            <SheetHeader>
              <SheetTitle>Loading source…</SheetTitle>
              <SheetDescription>Fetching the document.</SheetDescription>
            </SheetHeader>
            <div className="space-y-2 px-4">
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-5/6" />
            </div>
          </>
        )}

        {state.status === "missing" && (
          <SheetHeader>
            <SheetTitle>Source not found</SheetTitle>
            <SheetDescription>No document with id <code className="rounded bg-muted px-1">{documentId}</code> is available.</SheetDescription>
          </SheetHeader>
        )}

        {state.status === "ready" && (
          <>
            <SheetHeader className="pr-12">
              <SheetTitle>{state.doc.title}</SheetTitle>
              <SheetDescription className="flex flex-wrap items-center gap-x-2 gap-y-1">
                <Badge variant="outline" className="font-normal">{KIND_LABEL[state.doc.kind]}</Badge>
                <span>{fmtDate(state.doc.date, { year: true })}</span>
                <span aria-hidden>·</span>
                <span>{state.doc.origin}</span>
              </SheetDescription>
            </SheetHeader>
            <ScrollArea className="min-h-0 flex-1 px-4 pb-4">
              {state.doc.supersededBy && (
                <Alert className="mb-4">
                  <History />
                  <AlertTitle>Superseded document</AlertTitle>
                  <AlertDescription>
                    This document has been replaced by{" "}
                    <span className="font-medium text-foreground">{state.newer?.title ?? state.doc.supersededBy}</span>
                    {state.newer?.date && <> ({fmtDate(state.newer.date, { year: true })})</>}. It is kept for traceability and is not current.
                  </AlertDescription>
                </Alert>
              )}
              <div className="text-sm leading-relaxed [&_h1]:mb-2 [&_h1]:text-base [&_h1]:font-semibold [&_h2]:mt-4 [&_h2]:mb-1.5 [&_h2]:text-sm [&_h2]:font-semibold [&_h3]:mt-3 [&_h3]:mb-1 [&_h3]:font-medium [&_p]:mb-3 [&_ul]:mb-3 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:mb-3 [&_ol]:list-decimal [&_ol]:pl-5 [&_li]:mb-0.5 [&_strong]:font-semibold [&_blockquote]:border-l-2 [&_blockquote]:pl-3 [&_blockquote]:text-muted-foreground [&_code]:rounded [&_code]:bg-muted [&_code]:px-1 [&_code]:text-xs [&_a]:underline [&_a]:underline-offset-2 [&_table]:w-full [&_table]:text-xs [&_th]:text-left [&_th]:font-medium [&_td]:py-0.5 [&_hr]:my-3">
                <ReactMarkdown>{state.doc.body}</ReactMarkdown>
              </div>
            </ScrollArea>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
