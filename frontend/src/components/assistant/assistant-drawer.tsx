"use client";
import { useEffect, useRef, useState } from "react";
import { ArrowUp, ArrowUpRight, ChevronDown, CircleHelp, SlidersHorizontal, TrendingUp } from "lucide-react";
import type { AssistantMessage, ConversationContext } from "@/lib/contracts";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useAppStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import { fmtDate } from "@/components/team/labels";
import { ProposalReview } from "@/components/allocation/proposal-review";
import { SourceSheet } from "@/components/team/source-sheet";
import { Markdown } from "./markdown";
import { AssistantResponse } from "./assistant-response";
import { cleanAssistantPresentation, formatAssistantAmount } from "./assistant-answer-model";

const THREAD = "main";

/**
 * Finance ↔ assistant thread. Messages render markdown, a compact work record (tool calls), source chips,
 * and an inline proposal card when the assistant prepared one. Review/apply happens in ProposalReview.
 */
export function AssistantDrawer() {
  const { assistantOpen, setAssistantOpen, threads, sendMessage, proposals, teams, people, company, composer: text, setComposer: setText, loaded, loadState, forecastQuestionContext, conversationContext, composerFocus, clearAssistantContext, setAssistantIntent, reconcileMessage, optionalErrors, retryOptional, requests, requestState, proposalActions } = useAppStore();
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
  }, [assistantOpen, composerFocus]);

  // Keep the newest message in view.
  useEffect(() => {
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages.length, sending, assistantOpen]);

  async function send(content: string, intent?: ConversationContext["intent"]) {
    const trimmed = content.trim();
    if (!trimmed || sending || !loaded) return;
    setSending(true);
    setError(undefined);
    if (intent) setAssistantIntent(intent);
    try {
      await sendMessage(THREAD, trimmed);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Droid Assistant did not respond.");
      // The sent message stays in the thread; a newer composer draft remains untouched.
    } finally {
      setSending(false);
      // The textarea stays enabled while the reply is pending; put the cursor back once it lands.
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }

  const proposalFor = (id?: string) => (id ? proposals.find((p) => p.id === id) : undefined);
  const canSend = loaded && !sending && text.trim().length > 0;

  const quickPrompts: { label: string; content: string; intent: ConversationContext["intent"] }[] = [
    { label: "Analyze spend", content: "What changed our spending outlook?", intent: "explain" },
    { label: "Try a scenario", content: "Help me choose a planned change to preview as a scenario.", intent: "scenario" },
    { label: "Redistribute", content: "Redistribute the existing allocation without adding funding", intent: "allocation" },
  ];
  const showPrompts = !sending && !text.trim();
  const selectedProposal = proposals.find(p => p.id === conversationContext?.selected_proposal_id);
  const scopeName = forecastQuestionContext?.scope_type === "team"
    ? teams.find(t => t.id === forecastQuestionContext.scope_id)?.name ?? "Selected team"
    : forecastQuestionContext?.scope_type === "person"
      ? people.find(p => p.id === forecastQuestionContext.scope_id)?.name ?? "Selected person"
      : conversationContext?.scope_type === "team"
        ? teams.find(t => t.id === conversationContext.scope_id)?.name ?? "Selected team" : company?.name ?? "Company";
  const period = selectedProposal?.period ?? company?.currentPeriod;
  const periodLabel = period?.label ?? (period ? `${fmtDate(period.start)}–${fmtDate(period.end)}` : undefined);

  const openRequests = requests.filter(request => ["submitted", "pending_review", "needs_revision", "partially_funded"].includes(request.status)
    && request.periodStart === period?.start
    && new Date(Date.parse(`${request.periodEndExclusive}T00:00:00Z`)-86_400_000).toISOString().slice(0,10) === period?.end);
  async function checkStatus(message: AssistantMessage) {
    if (!message.clientMessageId) return;
    try {
      await reconcileMessage(THREAD,message.clientMessageId);
      if (!useAppStore.getState().threads[THREAD]?.some(item=>item.delivery === "unknown")) setError(undefined);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Status could not be checked. Try again."); }
  }
  return (
    <Sheet open={assistantOpen} onOpenChange={setAssistantOpen} modal={false} disablePointerDismissal>
      <SheetContent side="right" overlay={false} className="w-full gap-0 sm:max-w-[480px]">
        <SheetHeader className="flex-row items-center gap-3 border-b border-border px-5 py-4 pr-12">
          <span aria-hidden className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-foreground text-sm font-semibold text-background">D</span>
          <div className="min-w-0"><SheetTitle className="text-base leading-tight font-medium tracking-tight">Droid Assistant</SheetTitle><SheetDescription className="mt-1 text-xs">Your finance workspace</SheetDescription></div>
        </SheetHeader>
        <div className="border-b border-border px-5 py-3">
          <div className="flex items-center gap-2 text-xs"><span className="font-medium">{scopeName}</span><span className="text-muted-foreground">{periodLabel}</span>{((conversationContext && Object.keys(conversationContext).length>0)||forecastQuestionContext) && <button type="button" className="ml-auto text-[11px] text-muted-foreground underline underline-offset-4 hover:text-foreground" onClick={clearAssistantContext}>Clear context</button>}</div>
          {(selectedProposal||forecastQuestionContext) && <div className="mt-2 flex flex-wrap gap-1.5 text-[10px] text-muted-foreground">{selectedProposal && <span className="rounded-full bg-muted px-2 py-1">Selected budget draft{selectedProposal.version ? ` · v${selectedProposal.version}` : ""}</span>}{forecastQuestionContext && <span className="rounded-full bg-muted px-2 py-1">Pinned forecast</span>}</div>}
          {requestState === "error" && <p role="status" className="mt-2 text-[11px] text-warning">Team request context is unavailable. <a href="/requests" className="underline underline-offset-4">Open requests</a></p>}
          {openRequests.length>0 && <details className="group/context mt-2.5"><summary className="flex cursor-pointer list-none items-center gap-1.5 text-[11px] text-muted-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring [&::-webkit-details-marker]:hidden"><span className="size-1.5 rounded-full bg-foreground/50" aria-hidden/>{openRequests.length} open team {openRequests.length===1 ? "request" : "requests"}<ChevronDown className="ml-auto size-3 transition-transform group-open/context:rotate-180" aria-hidden/></summary><ul className="mt-2 space-y-1.5">{openRequests.map(request=><li key={request.id}><a href={`/requests?request=${encodeURIComponent(request.id)}`} className="flex items-center justify-between gap-3 rounded-lg bg-muted/50 px-3 py-2 text-xs hover:bg-muted"><span className="min-w-0"><span className="block truncate font-medium">{request.title}</span><span className="text-[10px] text-muted-foreground">{teams.find(team=>team.id===request.teamId)?.name ?? "Team"}</span></span><span className="shrink-0 text-[11px] tabular-nums">{request.remainingRequestedAmount===null ? "Amount needed" : `${formatAssistantAmount(request.remainingRequestedAmount,"usd")} requested`}</span><ArrowUpRight aria-hidden className="size-3 shrink-0 text-muted-foreground"/></a></li>)}</ul>{requestState==="stale" && <p className="mt-2 text-[11px] text-warning">Request updates are temporarily unavailable.</p>}</details>}
        </div>
        {optionalErrors.assistant && <div className="border-b border-border px-5 py-2 text-xs text-muted-foreground" role="status">Earlier messages are unavailable. <button type="button" className="underline" onClick={()=>void retryOptional()}>Try again</button></div>}
        <div ref={listRef} className="min-h-0 flex-1 overflow-y-auto bg-muted/20 px-4 py-4">
          {!loaded ? <p role="status" className="px-1 text-xs text-muted-foreground">{loadState==="error" ? "Spending data could not be loaded. Retry from the dashboard." : "Loading your workspace…"}</p> : <>
            {messages.length===0 && <div className="px-2 pt-8 pb-6"><p className="text-xl font-medium tracking-tight">What needs a closer look?</p><p className="mt-2 text-sm text-muted-foreground">Explore spending, preview a change, or prepare an allocation.</p></div>}
            <ol className="space-y-4" aria-label="Droid Assistant conversation">
              {messages.map(message=><li key={message.id}>{message.role==="user" ? <UserMessage message={message} onCheckStatus={()=>void checkStatus(message)}/> : <><AssistantResponse message={message} proposal={proposalFor(message.proposalId)} proposalAction={message.proposalId ? proposalActions[message.proposalId] : undefined} teams={teams} onReview={setReviewId} onSource={setDocId} onDraftChange={draft=>useAppStore.getState().updateActionDraft(message.threadId,message.id,draft)}/><Stamp iso={message.createdAt} className="mt-1.5 px-1"/></>}</li>)}
              {sending && <li className="flex items-center gap-2 px-2 py-2 text-xs text-muted-foreground" role="status"><span className="size-1.5 animate-pulse rounded-full bg-current" aria-hidden/>Droid is working…</li>}
              {error && <li role="alert" className="rounded-xl border border-destructive/20 bg-card p-3 text-xs leading-relaxed text-destructive">{cleanAssistantPresentation(error)}</li>}
            </ol>
          </>}
        </div>
        <div className="border-t border-border bg-card px-4 pt-3 pb-4">
          {showPrompts && <ul className="mb-3 grid grid-cols-3 gap-2" aria-label="Suggested prompts">{quickPrompts.map((prompt,index)=>{const Icon=[TrendingUp,CircleHelp,SlidersHorizontal][index];return <li key={prompt.label}><button type="button" disabled={!loaded} onClick={()=>void send(prompt.content,prompt.intent)} className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-border px-2 py-2 text-[11px] font-medium transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-40"><Icon className="size-3.5 text-muted-foreground" aria-hidden/>{prompt.label}</button></li>})}</ul>}
          <form className="flex items-end gap-2 rounded-2xl border border-border-strong bg-background p-2 transition-shadow focus-within:ring-2 focus-within:ring-ring" onSubmit={event=>{event.preventDefault();void send(text)}}>
            <Textarea ref={inputRef} value={text} onChange={event=>setText(event.target.value)} onKeyDown={event=>{if(event.key==="Enter"&&!event.shiftKey&&!event.nativeEvent.isComposing){event.preventDefault();void send(text)}}} placeholder="Ask Droid Assistant…" aria-label="Message Droid Assistant" className="min-h-10 max-h-40 flex-1 resize-none rounded-none border-0 bg-transparent px-2 py-2 text-sm focus:border-transparent focus-visible:border-transparent focus-visible:ring-0"/>
            <Button type="submit" size="icon-sm" disabled={!canSend} aria-label="Send message" className="mb-0.5 rounded-xl"><ArrowUp className="size-4" strokeWidth={1.5}/></Button>
          </form>
          <p className="mt-2 text-center text-[10px] text-muted-foreground">Budget changes require your review and approval.</p>
        </div>
        <ProposalReview proposalId={reviewId} onClose={()=>setReviewId(undefined)}/>
        <SourceSheet documentId={docId} onClose={()=>setDocId(undefined)}/>
      </SheetContent>
    </Sheet>
  );
}
function Stamp({iso,className}:{iso:string;className?:string}) {return <time className={cn("block text-[10px] text-muted-foreground tabular-nums",className)} dateTime={iso}>{new Date(iso).toLocaleTimeString("en-US",{hour:"numeric",minute:"2-digit"})}</time>}
function UserMessage({message,onCheckStatus}:{message:AssistantMessage;onCheckStatus:()=>void}) {
  return <div className="flex flex-col items-end gap-1.5"><div className="max-w-[90%] rounded-2xl rounded-br-md bg-muted px-3.5 py-2.5"><Markdown>{message.content}</Markdown></div>
    {message.delivery==="sending" && <p role="status" className="text-[11px] text-muted-foreground">Sending…</p>}
    {message.delivery==="unknown" && <p role="status" className="max-w-[90%] text-[11px] leading-relaxed text-warning">Reply not confirmed. <button type="button" onClick={onCheckStatus} className="underline underline-offset-4">Check status</button></p>}
    {message.delivery==="failed" && <p role="status" className="text-[11px] text-destructive">Request was not accepted.</p>}
    <Stamp iso={message.createdAt} className="pr-1"/>
  </div>;
}
