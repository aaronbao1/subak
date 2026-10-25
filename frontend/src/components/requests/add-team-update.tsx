"use client";
import { displayCopy, displaySourceText } from "@/lib/display-copy";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import type { BudgetRequest, BudgetRequestInput } from "@/lib/contracts/budget-requests";
import { useAppStore } from "@/lib/store";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { teamUpdateInput } from "./request-form";
import { requestSubmission } from "./request-session";

const inputClass = "h-10 w-full rounded-md border border-border bg-background px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring";
export function AddTeamUpdate({ open, onClose, onSaved, initialUpdate }: { open: boolean; onClose: () => void; onSaved: (request: BudgetRequest) => void; initialUpdate?: BudgetRequest }) {
  const { company, teams, ingestTeamUpdate } = useAppStore();
  const [kind, setKind] = useState<BudgetRequestInput["requestKind"]>(initialUpdate?.requestKind ?? "team");
  const [form, setForm] = useState({ teamId: initialUpdate?.teamId ?? "", title: initialUpdate?.title ?? "", projectName: initialUpdate?.projectName ?? "", summary: initialUpdate?.narrative ?? "", amount: "", start: initialUpdate?.periodStart ?? company?.currentPeriod.start ?? "", end: initialUpdate ? new Date(Date.parse(`${initialUpdate.periodEndExclusive}T00:00:00Z`) - 86_400_000).toISOString().slice(0, 10) : company?.currentPeriod.end ?? "" });
  const submission = useSyncExternalStore(requestSubmission.subscribe, requestSubmission.getSnapshot, () => undefined);
  const busy = submission?.status === "saving";
  const uncertain = submission?.status === "unknown";
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const [error, setError] = useState<string>();
  const visibleForm = submission ? { teamId: submission.input.teamId, title: submission.input.title, projectName: submission.input.projectName ?? "", summary: submission.input.narrative, amount: submission.input.requestedAmount ?? "", start: submission.input.periodStart, end: new Date(Date.parse(`${submission.input.periodEndExclusive}T00:00:00Z`) - 86_400_000).toISOString().slice(0, 10) } : form;
  const visibleKind = submission?.input.requestKind ?? kind;
  const eligibleTeams = teams.filter(team => team.id !== "unattributed");
  const change = (field: keyof typeof form, value: string) => { setForm(current => ({ ...current, [field]: value })); setError(undefined); };
  async function submit() {
    if (requestSubmission.getSnapshot()?.status === "saving") return;
    let input: BudgetRequestInput;
    try {
      const retry = requestSubmission.retry();
      if (retry) input = retry;
      else {
        input = teamUpdateInput(form, eligibleTeams.map(team => team.id), kind, crypto.randomUUID(), initialUpdate);
        if (!requestSubmission.begin(input)) return;
      }
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Check the update details."); return; }
    setError(undefined);
    try {
      const saved = await ingestTeamUpdate(input);
      requestSubmission.resolve(input.clientRequestId);
      if (mounted.current) onSaved(saved);
    } catch (cause) {
      const definite = !!(cause && typeof cause === "object" && "definiteFailure" in cause && cause.definiteFailure === true);
      if (definite) requestSubmission.resolve(input.clientRequestId);
      else requestSubmission.unknown(input.clientRequestId);
      if (mounted.current) setError(definite ? cause instanceof Error ? cause.message : "The update could not be saved." : undefined);
    }
  }
  return <Sheet open={open} onOpenChange={value => { if (!value && !busy) onClose(); }}><SheetContent side="right" className="w-full gap-0 overflow-y-auto sm:max-w-xl"><SheetHeader className="border-b border-border px-5 py-5 pr-12"><SheetTitle>{uncertain ? "Recover team update" : initialUpdate ? "Create budget request" : "Add team update"}</SheetTitle><SheetDescription>{initialUpdate ? "State the requested amount for this update. The original source is preserved." : "Capture a request and assess it against the budget."}</SheetDescription></SheetHeader><form onSubmit={event => { event.preventDefault(); void submit(); }} className="space-y-5 p-5">
    <fieldset disabled={busy || !!uncertain} className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2"><label className="space-y-1.5 text-xs font-medium">Team<select aria-label="Requesting team" value={visibleForm.teamId} onChange={event => change("teamId", event.target.value)} className={inputClass}><option value="">Choose team</option>{eligibleTeams.map(team => <option key={team.id} value={team.id}>{displaySourceText(team.name, "Team")}</option>)}</select></label><label className="space-y-1.5 text-xs font-medium">Update type<select aria-label="Update type" value={visibleKind} onChange={event => { setKind(event.target.value as BudgetRequestInput["requestKind"]); setError(undefined); }} className={inputClass}><option value="team">Team request</option><option value="project">New project</option><option value="initiative">Initiative</option></select></label></div>
      <label className="block space-y-1.5 text-xs font-medium">Title<Input aria-label="Update title" placeholder="Evaluation workload expansion" value={visibleForm.title} onChange={event => change("title", event.target.value)} /></label>
      {visibleKind !== "team" && <label className="block space-y-1.5 text-xs font-medium">Project or initiative name <span className="font-normal text-muted-foreground">(optional)</span><Input aria-label="Project or initiative name" value={visibleForm.projectName} onChange={event => change("projectName", event.target.value)} /></label>}
      <label className="block space-y-1.5 text-xs font-medium">What is changing?<Textarea aria-label="Team update summary" placeholder="Describe the plan, why the team needs it, and the expected timing." className="min-h-28" value={visibleForm.summary} onChange={event => change("summary", event.target.value)} /></label>
      <label className="block space-y-1.5 text-xs font-medium">Requested increase (USD) {!initialUpdate && <span className="font-normal text-muted-foreground">(optional)</span>}<Input aria-label="Requested additional dollars" inputMode="decimal" placeholder={initialUpdate ? "Enter the requested increase" : "Leave blank if not specified"} value={visibleForm.amount} onChange={event => change("amount", event.target.value)} /><span className="block text-[11px] font-normal text-muted-foreground">Enter the additional amount requested. The description is not used to guess an amount.</span></label>
      <div className="grid grid-cols-2 gap-3"><label className="space-y-1.5 text-xs font-medium">Period starts<Input type="date" aria-label="Request period start" value={visibleForm.start} onChange={event => change("start", event.target.value)} /></label><label className="space-y-1.5 text-xs font-medium">Period ends<Input type="date" aria-label="Request period end" value={visibleForm.end} min={visibleForm.start} onChange={event => change("end", event.target.value)} /></label></div>
    </fieldset>
    {uncertain && <p role="status" className="rounded-md border border-warning/30 p-3 text-sm">Save confirmation is unavailable. Retry this same update to recover its saved result.</p>}
    {error && <p role="alert" className="rounded-md border border-warning/30 p-3 text-sm text-warning">{displayCopy(error, "The update could not be saved.")}</p>}
    <div className="flex flex-wrap items-center gap-3"><Button type="submit" disabled={busy || !uncertain && eligibleTeams.length === 0}>{busy ? "Saving and assessing…" : uncertain ? "Retry saved update" : initialUpdate ? "Create and assess request" : "Save and assess"}</Button><Button type="button" variant="ghost" onClick={onClose} disabled={busy}>Cancel</Button></div>
    <p className="text-xs text-muted-foreground">A request does not change the forecast or allocation. Finance reviews any budget proposal separately.</p>
  </form></SheetContent></Sheet>;
}
