"use client";
import { useEffect, useRef, useState } from "react";
import { ArrowUp, ChevronRight, FileText } from "lucide-react";
import type { AssistantMessage, SourceRef } from "@/lib/contracts";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useAppStore } from "@/lib/store";
import { formatAmount } from "@/lib/format";
import { cn } from "@/lib/utils";
import { fmtDate } from "@/components/team/labels";
import { ProposalCard } from "@/components/allocation/proposal-card";
import { ProposalReview } from "@/components/allocation/proposal-review";
import { SourceSheet } from "@/components/team/source-sheet";
import { Markdown } from "./markdown";

const THREAD = "main";

/**
 * Finance ↔ assistant thread. Messages render markdown, a compact work record (tool calls), source chips,
 * and an inline proposal card when the assistant prepared one. Review/apply happens in ProposalReview.
 */
export function AssistantDrawer() {
  const { assistantOpen, setAssistantOpen, threads, sendMessage, proposals, teams, budgets, company, composer: text, setComposer: setText, loaded, forecastQuestionContext, askAssistant } = useAppStore();
  const messages = threads[THREAD] ?? [];
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | undefined>();
  const [reviewId, setReviewId] = useState<string | undefined>();
  const [docId, setDocId] = useState<string | undefined>();
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Focus the composer when the drawer opens (pages prefill it through the store).
  useEffect(() => {
    if (!assistantOpen) return;
    const t = setTimeout(() => inputRef.current?.focus(), 80);
    return () => clearTimeout(t);
  }, [assistantOpen]);

  // Keep the newest message in view.
  useEffect(() => {
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages.length, sending, assistantOpen]);

  async function send(content: string) {
    const trimmed = content.trim();
    if (!trimmed || sending) return;
    setSending(true);
    setError(undefined);
    setText("");
    try {
      await sendMessage(THREAD, trimmed);
    } catch (e) {
      setError(e instanceof Error ? e.message : "The assistant did not respond.");
      setText(trimmed);
    } finally {
      setSending(false);
      // The textarea stays enabled while the reply is pending; put the cursor back once it lands.
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }

  const proposalFor = (id?: string) => (id ? proposals.find((p) => p.id === id) : undefined);
  const canSend = !sending && text.trim().length > 0;

  // Quick prompts come from the data, never from a hard-coded team or amount.
  const unit = company?.budgetUnit ?? "usd";
  const firstTeam = teams[0]?.name;
  // Roughly a tenth of the total allocation, rounded to one significant figure so it reads as a round number.
  const totalAllocated = budgets.reduce((n, b) => n + b.allocated, 0);
  const extra = roundClean(totalAllocated * 0.1);
  const quickPrompts = [
    firstTeam ? `Why is ${firstTeam} tracking over its allocation?` : "Which team is tracking over its allocation?",
    "Redistribute the existing allocation without adding funding",
    extra > 0
      ? `We have another ${formatAmount(extra, unit)} to allocate this week; how should we split it?`
      : "We have additional budget to allocate this week; how should we split it?",
  ];
  const showPrompts = messages.length <= 1 && !sending && !forecastQuestionContext;

  return (
    /* Non-modal: the dashboard stays visible and usable, so the hero updates in plain sight when a proposal is applied. */
    <Sheet open={assistantOpen} onOpenChange={setAssistantOpen} modal={false} disablePointerDismissal>
      <SheetContent side="right" overlay={false} className="w-full gap-0 sm:max-w-md">
        <SheetHeader className="h-14 justify-center gap-0 border-b border-border px-4 py-0 pr-12">
          <SheetTitle className="text-base leading-tight font-medium">Assistant</SheetTitle>
          <SheetDescription className="sr-only">Ask about spend or request a proposal. Nothing changes until you apply it.</SheetDescription>
        </SheetHeader>

        {forecastQuestionContext && <div className="space-y-2 border-b border-border bg-muted/20 px-4 py-3 text-xs"><p className="break-all text-muted-foreground">Issued run {forecastQuestionContext.run_id} · {forecastQuestionContext.scope_type} {forecastQuestionContext.scope_id}{forecastQuestionContext.driver_id && ` · driver ${forecastQuestionContext.driver_id}`}</p><button className="text-xs underline underline-offset-2" onClick={() => askAssistant(text)}>Clear forecast context</button></div>}
        <div ref={listRef} className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
          {!loaded ? (
            <p className="text-xs text-muted-foreground">Loading…</p>
          ) : (
            <ol className="space-y-5">
              {messages.map((m) => (
                <li key={m.id}>
                  <Message m={m} teams={teams} proposal={proposalFor(m.proposalId)} onReview={setReviewId} onSource={setDocId} />
                </li>
              ))}
              {sending && (
                <li className="grid grid-cols-[auto_1fr] gap-x-2.5" aria-live="polite">
                  <AvatarDot />
                  <span className="flex h-5 items-center gap-2 text-xs text-muted-foreground">
                    <span className="flex items-center gap-[3px]" aria-hidden>
                      <span className="size-1 animate-pulse rounded-full bg-current [animation-delay:-0.4s]" />
                      <span className="size-1 animate-pulse rounded-full bg-current [animation-delay:-0.2s]" />
                      <span className="size-1 animate-pulse rounded-full bg-current" />
                    </span>
                    Working…
                  </span>
                </li>
              )}
              {error && (
                <li className="grid grid-cols-[auto_1fr] gap-x-2.5">
                  <span aria-hidden className="mt-[7px] size-1.5 rounded-full bg-destructive" />
                  <p className="text-xs leading-5 text-destructive">{error}</p>
                </li>
              )}
            </ol>
          )}
        </div>

        <div className="border-t border-border px-4 pt-3 pb-3">
          {/* The chip row keeps its height when empty so the composer never jumps. */}
          <div className="mb-3 min-h-7">
            {showPrompts && (
              <ul className="flex flex-wrap gap-1.5" aria-label="Suggested prompts">
                {quickPrompts.map((q) => (
                  <li key={q} className="shrink-0">
                    <button
                      type="button"
                      onClick={() => send(q)}
                      className="h-7 rounded-md border border-border bg-popover px-2.5 text-xs whitespace-nowrap text-muted-foreground transition-colors duration-300 outline-none hover:border-border-strong hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      {q}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <form
            className="flex items-end gap-1 rounded-xl border border-border-strong bg-popover p-1 transition-colors duration-300 focus-within:border-muted-foreground focus-within:ring-4 focus-within:ring-ring"
            onSubmit={(e) => { e.preventDefault(); void send(text); }}
          >
            <Textarea
              ref={inputRef}
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void send(text); }
              }}
              placeholder="Ask about spend, or request a proposal"
              aria-label="Message the assistant"
              className="min-h-8 max-h-40 flex-1 resize-none rounded-none border-0 bg-transparent px-2 py-1.5 text-sm focus:border-transparent focus-visible:border-transparent focus-visible:ring-0"
            />
            <Button type="submit" size="icon-sm" disabled={!canSend} aria-label="Send">
              <ArrowUp className="size-4" strokeWidth={1.5} />
            </Button>
          </form>
        </div>

        {/* Nested inside the drawer so Esc closes only the topmost dialog. */}
        <ProposalReview proposalId={reviewId} onClose={() => setReviewId(undefined)} />
        <SourceSheet documentId={docId} onClose={() => setDocId(undefined)} />
      </SheetContent>
    </Sheet>
  );
}

/** Round to one significant figure: 23,400 becomes 20,000. */
function roundClean(n: number) {
  if (n <= 0) return 0;
  const pow = 10 ** Math.floor(Math.log10(n));
  return Math.round(n / pow) * pow;
}

function AvatarDot() {
  return <span aria-hidden className="mt-[7px] flex size-1.5 rounded-full bg-muted-foreground" />;
}

function Stamp({ iso, className }: { iso: string; className?: string }) {
  return (
    <time className={cn("num block text-xs text-muted-foreground", className)} dateTime={iso}>
      {new Date(iso).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}
    </time>
  );
}

function Message({ m, teams, proposal, onReview, onSource }: {
  m: AssistantMessage;
  teams: ReturnType<typeof useAppStore.getState>["teams"];
  proposal?: ReturnType<typeof useAppStore.getState>["proposals"][number];
  onReview: (id: string) => void;
  onSource: (documentId: string) => void;
}) {
  if (m.role === "user") {
    return (
      <div className="flex flex-col items-end gap-1">
        <div className="max-w-[85%] rounded-xl bg-popover px-3 py-2 text-sm leading-relaxed text-foreground">
          <Markdown>{m.content}</Markdown>
        </div>
        <Stamp iso={m.createdAt} className="pr-1" />
      </div>
    );
  }

  const hasMeta = Boolean(m.toolCalls?.length || m.citations?.length);
  return (
    <div className="grid grid-cols-[auto_1fr] gap-x-2.5">
      <AvatarDot />
      <div className="min-w-0 space-y-2.5">
        <Markdown>{m.content}</Markdown>
        {hasMeta && (
          <div className="space-y-1.5">
            {m.toolCalls && m.toolCalls.length > 0 && <WorkRecord calls={m.toolCalls} />}
            {m.citations && m.citations.length > 0 && <Sources citations={m.citations} onSource={onSource} />}
          </div>
        )}
        {proposal && <ProposalCard proposal={proposal} teams={teams} onReview={onReview} className="w-full" />}
        <Stamp iso={m.createdAt} />
      </div>
    </div>
  );
}

const humanize = (name: string) => name.replace(/_/g, " ");

/** What the assistant did, collapsed to one line ("3 steps") until opened. */
function WorkRecord({ calls }: { calls: NonNullable<AssistantMessage["toolCalls"]> }) {
  return (
    <details className="group text-xs">
      <summary className="inline-flex cursor-pointer list-none items-center gap-1 rounded-sm text-xs text-muted-foreground transition-colors duration-300 select-none hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring [&::-webkit-details-marker]:hidden">
        <ChevronRight className="size-4 transition-transform group-open:rotate-90" aria-hidden strokeWidth={1.5} />
        <span className="num">{calls.length}</span> {calls.length === 1 ? "step" : "steps"}
      </summary>
      <ol className="mt-2 space-y-2.5 border-l border-border pl-3">
        {calls.map((c, i) => (
          <li key={i}>
            <div className="eyebrow">{humanize(c.name)}</div>
            <div className="mt-0.5 text-xs leading-snug text-foreground/80">{c.summary}</div>
          </li>
        ))}
      </ol>
    </details>
  );
}

function Sources({ citations, onSource }: { citations: SourceRef[]; onSource: (documentId: string) => void }) {
  // De-duplicate by document so the same plan is not listed three times.
  const seen = new Set<string>();
  const unique = citations.filter((c) => (seen.has(c.documentId) ? false : (seen.add(c.documentId), true)));
  return (
    <ul className="flex flex-wrap items-center gap-x-3 gap-y-1" aria-label="Sources">
      {unique.map((c) => (
        <li key={c.documentId} className="min-w-0 max-w-full">
          <button
            type="button"
            onClick={() => onSource(c.documentId)}
            title={[c.title, c.date && fmtDate(c.date), c.excerpt && `“${c.excerpt}”`].filter(Boolean).join(" · ")}
            className="inline-flex max-w-[220px] items-center gap-1 rounded-sm text-xs text-muted-foreground transition-colors duration-300 outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
          >
            <FileText aria-hidden className="size-3 shrink-0" strokeWidth={1.5} />
            <span className="truncate underline decoration-border underline-offset-4">{c.title}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}
