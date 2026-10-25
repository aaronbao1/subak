"use client";
import { ArrowUpRight, ChevronDown, FileText } from "lucide-react";
import type { ReactNode } from "react";
import type { AllocationProposal, AssistantMessage, ProposalActionState, Team } from "@/lib/contracts";
import type { ActionDraft } from "@/lib/planning-drafts";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { ActionDraftCard } from "./action-draft-card";
import { buildAssistantAnswer, cleanAssistantPresentation, formatAssistantAmount } from "./assistant-answer-model";
import { Markdown } from "./markdown";

export function AssistantResponse({ message, proposal, proposalAction, teams, onReview, onSource, onDraftChange }: {
  message: AssistantMessage;
  proposal?: AllocationProposal;
  proposalAction?: ProposalActionState;
  teams: Team[];
  onReview: (id: string) => void;
  onSource: (id: string) => void;
  onDraftChange: (draft: ActionDraft) => void;
}) {
  const answer = buildAssistantAnswer({ message, proposal, proposalAction, teams });
  const sources = [...new Map((message.citations ?? []).map(source => [source.documentId, source])).values()];
  const allocation = answer.allocation;
  const changed = allocation?.lines.filter(line => line.before !== line.after) ?? [];
  const reference = message.proposalId ?? (message.actionDraft?.kind === "allocation" ? message.actionDraft.proposalId : undefined);
  const matchingProposal = proposal?.id === reference ? proposal : undefined;
  const action = reference && (!proposalAction?.receipt || proposalAction.receipt.proposalId === reference) ? proposalAction : undefined;
  const confirmed = !!action?.receipt || action?.mutation === "confirmed";
  const needsStatus = !confirmed && action && ["pending", "unknown"].includes(action.mutation);
  const applied = action?.receipt ? action.receipt.action === "applied" : confirmed ? action?.action === "apply" : matchingProposal?.status === "applied";
  const reviewable = matchingProposal?.status === "proposed" && !confirmed && !needsStatus;
  const actionLabel = needsStatus ? "Check status" : confirmed || ["applied", "rejected"].includes(matchingProposal?.status ?? "") ? "View decision" : reviewable ? "Review proposal" : "View proposal";
  return <article aria-label="Droid Assistant response" className="overflow-hidden rounded-2xl border border-border bg-card shadow-[0_2px_10px_-8px_rgba(0,0,0,0.15)]">
    <header className="px-4 pt-4 pb-3">
      <div className="mb-2 flex items-center gap-2"><span className="text-[10px] font-semibold tracking-[0.15em] text-muted-foreground uppercase">Droid</span><span className={cn("rounded-full px-2 py-0.5 text-[10px] font-medium",answer.statusTone === "warning" ? "bg-warning/10 text-warning" : answer.statusTone === "danger" ? "bg-destructive/10 text-destructive" : answer.statusTone === "success" ? "bg-success/10 text-success" : "bg-muted text-muted-foreground")}>{answer.status}</span></div>
      <h3 className="text-base leading-snug font-medium tracking-tight">{answer.headline}</h3>
      {answer.summary && <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">{answer.summary}</p>}
    </header>
    {allocation && <div className="mx-4 mb-3 overflow-hidden rounded-xl bg-muted/40">
      <div className="flex items-center justify-between gap-3 border-b border-border/70 px-3 py-2"><span className="text-[11px] text-muted-foreground">Company allocation</span><span className="text-[11px] text-muted-foreground">{allocation.period.label ?? `${allocation.period.start} – ${allocation.period.end}`}</span></div>
      <dl className="grid grid-cols-2 gap-3 px-3 py-3"><div><dt className="text-[11px] text-muted-foreground">{applied ? "Approved total" : "Proposed total"}</dt><dd className="mt-1 text-xl font-medium tracking-tight tabular-nums">{formatAssistantAmount(allocation.after,allocation.unit)}</dd></div><div><dt className="text-[11px] text-muted-foreground">Company change</dt><dd className="mt-1 text-xl font-medium tracking-tight tabular-nums">{formatAssistantAmount(allocation.delta,allocation.unit)}</dd></div></dl>
      {changed.slice(0,3).map(line=><div key={line.teamId} className="flex items-center justify-between gap-3 border-t border-border/70 px-3 py-2 text-xs"><span>{line.teamName}</span><span className="tabular-nums"><span className="text-muted-foreground">{formatAssistantAmount(line.before,allocation.unit)}</span><span aria-hidden className="mx-1.5 text-muted-foreground">→</span><span>{formatAssistantAmount(line.after,allocation.unit)}</span></span></div>)}
      {changed.length>3 && <div className="border-t border-border/70 px-3 py-2 text-[11px] text-muted-foreground">{changed.length-3} more team changes in proposal review</div>}
    </div>}
    {answer.preview && <div data-answer-preview className="relative mx-4 mb-3 max-h-32 overflow-hidden"><Markdown>{answer.preview}</Markdown><div aria-hidden className="pointer-events-none absolute inset-x-0 bottom-0 h-3 bg-gradient-to-t from-card to-transparent"/></div>}
    {answer.bodyMode === "inline" && answer.body && <div className="px-4 pb-3"><Markdown>{answer.body}</Markdown></div>}
    {answer.notice && <p role={needsStatus ? "status" : undefined} className={cn("px-4 pb-3 text-xs leading-relaxed",needsStatus ? "text-warning" : "text-muted-foreground")}>{answer.notice}</p>}
    {reference && <div className="flex items-center justify-between gap-3 px-4 pb-4"><span className="text-[11px] text-muted-foreground">{needsStatus ? "Check the original action" : reviewable ? "Review before applying" : "Proposal details and history"}</span><Button size="sm" onClick={()=>onReview(reference)}>{actionLabel}<ArrowUpRight className="size-3.5" aria-hidden /></Button></div>}
    {message.actionDraft && <ResponseDetail label={message.actionDraft.kind === "scenario" ? "Edit & preview scenario" : "Edit budget transfer"}><ActionDraftCard draft={message.actionDraft} onReview={onReview} onChange={onDraftChange}/></ResponseDetail>}
    {answer.bodyMode === "details" && answer.body && <ResponseDetail label={answer.preview ? "Read full answer" : "Explanation"} hint={answer.preview ? "Includes assumptions" : "Full answer & assumptions"}><Markdown>{answer.body}</Markdown></ResponseDetail>}
    {sources.length>0 && <ResponseDetail label="Sources" hint={String(sources.length)}><ul className="space-y-2">{sources.map(source=><li key={source.documentId}><button type="button" onClick={()=>onSource(source.documentId)} className="flex w-full items-start gap-2 rounded-lg border border-border px-3 py-2 text-left text-xs transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"><FileText aria-hidden className="mt-0.5 size-3.5 shrink-0 text-muted-foreground"/><span><span className="font-medium">{cleanAssistantPresentation(source.title)}</span>{source.excerpt && <span className="mt-1 block leading-relaxed text-muted-foreground">{source.excerpt}</span>}</span><ArrowUpRight className="ml-auto size-3.5 shrink-0 text-muted-foreground" aria-hidden/></button></li>)}</ul></ResponseDetail>}
    {!!message.toolCalls?.length && <ResponseDetail label="Work steps" hint={String(message.toolCalls.length)}><ol className="space-y-3 border-l border-border pl-3">{message.toolCalls.map((call,index)=><li key={index}><p className="text-[10px] font-medium tracking-wide text-muted-foreground uppercase">Step {index+1}</p><p className="mt-1 text-xs leading-relaxed">{cleanAssistantPresentation(call.summary)}</p></li>)}</ol></ResponseDetail>}
  </article>;
}
function ResponseDetail({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return <details className="group/response border-t border-border"><summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-3 text-xs font-medium outline-none hover:bg-muted/30 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring [&::-webkit-details-marker]:hidden"><span>{label}</span>{hint && <span className="font-normal text-muted-foreground">{hint}</span>}<ChevronDown className="ml-auto size-3.5 text-muted-foreground transition-transform group-open/response:rotate-180" aria-hidden/></summary><div className="px-4 pt-1 pb-4">{children}</div></details>;
}
