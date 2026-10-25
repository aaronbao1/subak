"use client";
import { displayCopy, displaySourceText } from "@/lib/display-copy";
import { useEffect, useState, useSyncExternalStore } from "react";
import { ArrowRight, Check, RefreshCw } from "lucide-react";
import type { AllocationProposal, AssistantMessage, Period, Unit } from "@/lib/contracts";
import { useAppStore } from "@/lib/store";
import { getDataClient } from "@/lib/data";
import { checkPreparedAllocation, prepareAllocationRequest, type AllocationRequest } from "@/lib/allocation-workbench";
import { allocationStateRows, checkAllocationTargets, currentAllocationBase, prepareAllocationTargets, type AllocationTargetsPreview } from "@/lib/allocation-targets";
import { allocationSession, type AllocationOperation } from "@/lib/allocation-session";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { ProposalReview } from "./proposal-review";

const money = (amount: number) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: amount % 1 ? 2 : 0, maximumFractionDigits: 2 }).format(amount);
const selectClass = "h-10 w-full rounded-md border border-border bg-background px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring";
const THREAD = "main";
export interface AllocationRequestPreset { id: string; teamId: string; amount: string | null; period: Period; unit: Unit; title?: string }
interface WorkbenchProps { open: boolean; onOpenChange: (open: boolean) => void; initialTeamId?: string; initialRequest?: AllocationRequestPreset }
type Snapshot = { preview: AllocationRequest | AllocationTargetsPreview; fingerprint: string; contextKey: string; requestId?: string };

/** Request/receipt state lives outside this resettable editor and survives route navigation. */
export function AllocationWorkbench(props: WorkbenchProps) {
  return <WorkbenchBody key={props.initialRequest ? `${props.initialRequest.id}:${props.initialRequest.amount}` : props.initialTeamId ?? "company"} {...props}/>;
}
function WorkbenchBody({ open, onOpenChange, initialTeamId, initialRequest }: WorkbenchProps) {
  const { company, teams, budgets, allocationState, allocationStateStatus, requests, proposals, decisions, proposalActions, sendMessage, reconcileMessage } = useAppStore();
  const { operation } = useSyncExternalStore(allocationSession.subscribe, allocationSession.getSnapshot, allocationSession.getSnapshot);
  const [mode, setMode] = useState<"targets" | "transfer" | "addition">(initialRequest ? "transfer" : "targets");
  const [sourceTeamId, setSourceTeamId] = useState("");
  const [targetTeamId, setTargetTeamId] = useState(initialRequest?.teamId ?? initialTeamId ?? "");
  const [amount, setAmount] = useState(initialRequest?.amount ?? "");
  const [targetEdits, setTargetEdits] = useState<Record<string,string>>({});
  const [error, setError] = useState<string>();
  const [reviewId, setReviewId] = useState<string>();
  const [checking, setChecking] = useState(false);
  const contextKey=initialRequest?`${initialRequest.id}:${initialRequest.amount}`:initialTeamId??"company";
  useEffect(()=>{
    if(!open)return;
    const prior=allocationSession.getSnapshot().operation;
    const unresolved=Object.values(useAppStore.getState().proposalActions).some(action=>action.mutation==="pending"||action.mutation==="unknown");
    if(prior&&(prior.request as Snapshot).contextKey!==contextKey)allocationSession.clear(unresolved);
  },[open,contextKey]);
  const period = company?.currentPeriod;
  const unit = company?.budgetUnit ?? "usd";
  const baselineBudgets=allocationStateStatus==="ready"?(allocationStateRows(allocationState,period,unit)??budgets):budgets;
  const rows = baselineBudgets.filter(b => b.unit === unit && b.period.start === period?.start && b.period.end === period?.end);
  const availableTeams = teams.filter(team => rows.some(b => b.teamId === team.id));
  const periodEnd=period?new Date(`${period.end}T00:00:00Z`):undefined;
  if(periodEnd)periodEnd.setUTCDate(periodEnd.getUTCDate()+1);
  const periodEndExclusive=periodEnd?.toISOString().slice(0,10);
  const currentRequests=requests.filter(request=>request.periodStart===period?.start&&request.unit==="USD"&&request.status!=="rejected"&&request.status!=="approved_applied"&&request.periodEndExclusive===periodEndExclusive);
  const targets = Object.fromEntries(rows.map(row => [row.teamId, targetEdits[row.teamId] ?? row.allocated.toFixed(2)]));
  const fingerprint = JSON.stringify({mode,sourceTeamId,targetTeamId,amount,targets,requestId:initialRequest?.id});
  const busy = operation?.status === "preparing" || checking;
  const uncertain = operation?.status === "unknown";
  const preparedProposal = proposals.find(p => p.id === operation?.proposalId);
  const action = preparedProposal ? proposalActions[preparedProposal.id] : undefined;
  const receipt = action?.receipt ?? decisions.find(decision => decision.proposalId === preparedProposal?.id);
  const unsettledProposalId=Object.entries(proposalActions).find(([,item])=>item.mutation==="pending"||item.mutation==="unknown")?.[0];
  const decisionPending = !!unsettledProposalId;
  const terminal = !!receipt || preparedProposal && ["applied", "rejected", "revised", "failed"].includes(preparedProposal.status);
  const operationSnapshot = operation?.request as Snapshot | undefined;
  const unchanged = operation?.status === "prepared" && operationSnapshot?.fingerprint === fingerprint;
  let preview: AllocationRequest | AllocationTargetsPreview | undefined;
  let validation: string | undefined;
  try {
    if (period) preview = mode === "targets" ? prepareAllocationTargets(targets, {teams,budgets:baselineBudgets,period,unit}) : prepareAllocationRequest({mode,sourceTeamId,targetTeamId,amount,period,unit},{teams,budgets:baselineBudgets});
  } catch (e) { validation = e instanceof Error ? e.message : "Check the requested allocations."; }

  async function showPrepared(op: AllocationOperation, proposalId: string) {
    allocationSession.update(op.id, {proposalId});
    let proposal = useAppStore.getState().proposals.find(p => p.id === proposalId);
    if (!proposal) proposal = await getDataClient().getProposal(proposalId);
    if (!proposal) throw new Error("The draft was saved, but its details could not load. Check its status before preparing another.");
    const found = proposal;
    useAppStore.setState(state => ({proposals:[...state.proposals.filter(p => p.id !== found.id),found]}));
    const saved = op.request as Snapshot;
    const match = op.kind === "targets" ? checkAllocationTargets(saved.preview as AllocationTargetsPreview,proposal) : checkPreparedAllocation(saved.preview as AllocationRequest,proposal);
    allocationSession.update(op.id,{status:"prepared",error:undefined,...match});
    if(saved.requestId)void useAppStore.getState().loadRequests();
    if (match.matches) setReviewId(proposalId);
  }
  async function showMessage(op:AllocationOperation,messages:AssistantMessage[]) {
    const proposalId = [...messages].reverse().find(message=>message.role==="assistant"&&message.proposalId)?.proposalId;
    if (!proposalId) {
      const reply=[...messages].reverse().find(message=>message.role==="assistant");
      allocationSession.update(op.id,{status:"failed",error:reply?.content??"A draft could not be prepared. Check the amounts and teams."});return;
    }
    await showPrepared(op,proposalId);
  }
  async function prepare() {
    if (!period || busy || uncertain || decisionPending) return;
    setError(undefined);
    if (!preview) {setError(validation);return;}
    if (initialRequest && (initialRequest.period.start !== period.start || initialRequest.period.end !== period.end || initialRequest.unit !== unit)) {setError("This request belongs to a different planning period or unit. Open its matching budget before drafting.");return;}
    if (initialRequest && !initialRequest.amount) {setError("Add an explicit requested amount to this request before preparing an allocation.");return;}
    let requestBaseVersion: number | undefined;
    if(initialRequest) { try {requestBaseVersion=currentAllocationBase(baselineBudgets,period,unit).baseVersion;} catch(e) {setError(e instanceof Error?e.message:"Refresh current allocations.");return;} }
    const op:AllocationOperation = {id:crypto.randomUUID(),kind:initialRequest?"request":mode==="targets"?"targets":"message",status:"preparing",request:{preview,fingerprint,contextKey,requestId:initialRequest?.id} satisfies Snapshot};
    if (!allocationSession.begin(op,decisionPending)) return;
    try {
      if (op.kind==="targets") {
        const receipt=await getDataClient().prepareAllocationProposal((preview as AllocationTargetsPreview).input,op.id);
        await showPrepared(op,receipt.proposalId);
      } else if (initialRequest) {
        const receipt=await getDataClient().prepareBudgetRequestDraft(initialRequest.id,{baseVersion:requestBaseVersion!,actionType:mode==="addition"?"addition":"transfer",...(mode==="transfer"?{sourceTeamId}:{})},op.id);
        await showPrepared(op,receipt.proposalId);
      } else {
        const beforeIds=new Set((useAppStore.getState().threads[THREAD]??[]).map(message=>message.id));
        const previous=preparedProposal?.status==="proposed"?preparedProposal:undefined;
        const response=sendMessage(THREAD,(preview as AllocationRequest).content,{conversationContext:{intent:"allocation",...(previous?{selected_proposal_id:previous.id,selected_proposal_version:previous.version}:{})}});
        const clientMessageId=useAppStore.getState().threads[THREAD]?.find(message=>!beforeIds.has(message.id)&&message.role==="user")?.clientMessageId;
        allocationSession.update(op.id,{clientMessageId});
        await showMessage(op,await response);
      }
    } catch(e) {
      const current=allocationSession.getSnapshot().operation;
      const pending=useAppStore.getState().threads[THREAD]?.find(message=>message.clientMessageId===current?.clientMessageId&&message.role==="user");
      const definite=!!e&&typeof e==="object"&&"definiteFailure" in e&&e.definiteFailure===true || op.kind==="message"&&pending?.delivery==="failed";
      allocationSession.update(op.id,{status:definite?"failed":"unknown",error:definite?(e instanceof Error?e.message:"The draft was refused."):"The draft request may have been saved. Check its status before preparing another."});
    }
  }
  async function checkStatus() {
    if (!operation || busy) return;
    setChecking(true);setError(undefined);
    try {
      if (operation.proposalId) await showPrepared(operation,operation.proposalId);
      else if (operation.kind==="message"&&operation.clientMessageId) {
        await reconcileMessage(THREAD,operation.clientMessageId);
        const result=await getDataClient().reconcileMessage(THREAD,operation.clientMessageId);
        if(result.status==="completed"&&result.messages) await showMessage(operation,result.messages);
        else setError("No completed draft is confirmed yet. The original request has not been repeated.");
      } else {
        const receipt=await getDataClient().reconcileAllocationProposal(operation.id);
        if(receipt) await showPrepared(operation,receipt.proposalId);
        else setError("No saved draft is confirmed yet. Check again; the original request has not been repeated.");
      }
    } catch {setError("Draft status is unavailable. The original request has not been repeated.");}
    finally {setChecking(false);}
  }
  function startNew() {
    if(!allocationSession.clear(decisionPending))return;
    setTargetEdits({});setAmount(initialRequest?.amount??"");setSourceTeamId("");setError(undefined);
  }
  const currentTotal=rows.reduce((sum,row)=>sum+row.allocated,0);
  const targetValues=Object.values(targets).map(value=>Number(value.replaceAll(",","")));
  const requestedTotal=targetValues.every(Number.isFinite)?targetValues.reduce((sum,value)=>sum+value,0):undefined;
  return <Sheet open={open} onOpenChange={onOpenChange}>
    <SheetContent side="right" className="w-full gap-0 overflow-y-auto sm:max-w-xl">
      <SheetHeader className="border-b border-border px-5 py-5 pr-12"><SheetTitle>{initialRequest?"Fund team request":"Adjust allocations"}</SheetTitle><SheetDescription>{displayCopy(period?.label,"Current planning period")} · USD · Prepare a draft, then review it.</SheetDescription></SheetHeader>
      <div className="space-y-5 px-5 py-5">
        {initialRequest&&<div className="rounded-lg border border-border bg-muted/20 p-3"><p className="text-sm font-medium">{displaySourceText(initialRequest.title,"Team budget request")}</p><p className="mt-1 text-xs text-muted-foreground">{displaySourceText(teams.find(t=>t.id===initialRequest.teamId)?.name,"Team")} · {initialRequest.amount?`${money(Number(initialRequest.amount))} remaining requested`:"Requested amount not specified"}</p></div>}
        <fieldset disabled={busy||uncertain||decisionPending||!!terminal} className="space-y-5">
          <div className={`grid gap-1 rounded-lg bg-muted/50 p-1 ${initialRequest?"grid-cols-2":"grid-cols-3"}`} role="group" aria-label="Budget change type">
            {!initialRequest&&<Button type="button" variant={mode==="targets"?"secondary":"ghost"} aria-pressed={mode==="targets"} onClick={()=>setMode("targets")}>Team budgets</Button>}
            <Button type="button" variant={mode==="transfer"?"secondary":"ghost"} aria-pressed={mode==="transfer"} onClick={()=>setMode("transfer")}>Redistribute</Button>
            <Button type="button" variant={mode==="addition"?"secondary":"ghost"} aria-pressed={mode==="addition"} onClick={()=>setMode("addition")}>Add funding</Button>
          </div>
          {mode==="targets"?<>
            <div className="rounded-lg border border-border px-4 py-3"><p className="text-xs text-muted-foreground">Company budget</p><p className="mt-1 flex items-center gap-3 text-xl font-semibold tabular-nums">{money(currentTotal)}<ArrowRight className="size-4 text-muted-foreground"/>{requestedTotal===undefined?"—":money(requestedTotal)}</p><p className="mt-2 text-xs text-muted-foreground">Move budget between teams, or raise team budgets to add funding.</p></div>
            <div className="divide-y divide-border rounded-lg border border-border">{availableTeams.map(team=><label key={team.id} className="flex items-center justify-between gap-4 px-4 py-3"><span className="min-w-0 text-sm"><span className="font-medium">{displaySourceText(team.name,"Team")}</span><span className="mt-0.5 block text-xs text-muted-foreground">Current {money(rows.find(row=>row.teamId===team.id)!.allocated)}</span>{currentRequests.filter(request=>request.teamId===team.id).map(request=><span key={request.id} className="mt-1 block text-xs text-brand">{request.remainingRequestedAmount?`${money(Number(request.remainingRequestedAmount))} requested`:request.requestedAmount===null?"Project update":"Request needs review"}</span>)}</span><Input aria-label={`${displaySourceText(team.name,"Team")} team budget in dollars`} inputMode="decimal" value={targets[team.id]} onChange={e=>{setTargetEdits({...targetEdits,[team.id]:e.target.value});setError(undefined);}} className="w-36 text-right tabular-nums"/></label>)}</div>
            {currentRequests.length>0&&<p className="text-xs text-muted-foreground">Team requests are shown separately from forecast spending. Fund a request from its review to track its outcome.</p>}
          </>:<>
            <p className="text-xs text-muted-foreground">{mode==="transfer"?"Move an exact amount between team allocations. The company budget stays the same.":initialRequest?"Add funding for the remaining requested amount.":"The draft will recommend how to split added funding."}</p>
            <div className={mode==="transfer"?"grid grid-cols-2 gap-3":""}>
              {mode==="transfer"&&<label className="block space-y-1.5 text-xs font-medium">From<select aria-label="Transfer from team" value={sourceTeamId} onChange={e=>setSourceTeamId(e.target.value)} className={selectClass}><option value="">Choose team</option>{availableTeams.map(team=><option key={team.id} value={team.id}>{displaySourceText(team.name,"Team")}</option>)}</select></label>}
              <label className="block space-y-1.5 text-xs font-medium">{mode==="transfer"?"To":initialRequest?"Team":"Prioritize team"}<select disabled={!!initialRequest} aria-label={mode==="transfer"?"Transfer to team":"Prioritize team"} value={targetTeamId} onChange={e=>setTargetTeamId(e.target.value)} className={selectClass}><option value="">Choose team</option>{availableTeams.map(team=><option key={team.id} value={team.id}>{displaySourceText(team.name,"Team")}</option>)}</select></label>
            </div>
            <label className="block space-y-1.5 text-xs font-medium">Amount (USD)<Input disabled={!!initialRequest} aria-label="Allocation amount in dollars" inputMode="decimal" placeholder="5,000" value={amount} onChange={e=>setAmount(e.target.value)} className="h-11 text-lg tabular-nums"/></label>
          </>}
        </fieldset>
        {preview&&mode!=="targets"&&<section aria-label="Requested budget change" className="rounded-lg border border-border bg-muted/20 p-4"><h3 className="text-xs font-medium">Requested change</h3><div className="mt-3 flex justify-between gap-3 text-xs"><span className="text-muted-foreground">Company allocation</span><span className="tabular-nums">{money(preview.companyBefore)} → {money(preview.companyAfter)}</span></div>{preview.changes.map(change=><div key={change.teamId} className="mt-3 flex justify-between gap-3 text-xs"><span className="text-muted-foreground">{displaySourceText(teams.find(t=>t.id===change.teamId)?.name,"Team")}</span><span className="tabular-nums">{money(change.before)} → {money(change.after)}</span></div>)}</section>}
        {decisionPending&&<div className="rounded-md border border-warning/30 p-3 text-sm"><p>An allocation decision is awaiting confirmation.</p><Button type="button" size="sm" variant="outline" className="mt-2" onClick={()=>setReviewId(unsettledProposalId)}>Check decision</Button></div>}
        {(error||operation?.error)&&<p role="alert" className="rounded-md border border-warning/30 p-3 text-sm text-warning">{displayCopy(error??operation?.error,"The allocation draft could not be prepared.")}</p>}
        {preparedProposal&&operation?.status==="prepared"&&<PreparedDraft proposal={preparedProposal} matches={operation.matches??false} reason={operation.reason} onReview={()=>setReviewId(preparedProposal.id)}/>}
        {uncertain?<Button type="button" onClick={()=>void checkStatus()} disabled={busy}><RefreshCw className="size-4"/>{checking?"Checking…":"Check draft status"}</Button>:terminal?<Button type="button" variant="outline" disabled={decisionPending} onClick={startNew}>Start new adjustment</Button>:<Button type="button" onClick={()=>void prepare()} disabled={busy||decisionPending||!period||!availableTeams.length||unchanged}>{busy?"Preparing draft…":operation?.status==="prepared"?(mode==="targets"||initialRequest?"Prepare another draft":"Prepare revised draft"):"Prepare for review"}</Button>}
        {!terminal&&<p className="text-xs text-muted-foreground">Nothing changes until you review and apply the proposal.</p>}
      </div>
      <ProposalReview proposalId={reviewId} onClose={()=>setReviewId(undefined)}/>
    </SheetContent>
  </Sheet>;
}
function PreparedDraft({proposal,matches,reason,onReview}:{proposal:AllocationProposal;matches:boolean;reason?:string;onReview:()=>void}) {
  const {teams,decisions,proposalActions}=useAppStore();
  const action=proposalActions[proposal.id];
  const receipt=action?.receipt??decisions.find(decision=>decision.proposalId===proposal.id);
  const status=receipt?.action??proposal.status;
  const pending=action?.mutation==="pending"||action?.mutation==="unknown";
  const title:Record<AllocationProposal["status"],string>={proposed:"Draft ready for review",pending:"Decision awaiting confirmation",applied:"Allocation applied",rejected:"Draft rejected",revised:"Replaced by a newer draft",stale:"Draft needs a fresh review",failed:"Allocation was not applied"};
  return <section className="space-y-3 rounded-lg border border-border p-4" aria-label="Prepared allocation draft"><p className="flex items-center gap-2 text-sm font-medium"><Check className="size-4 text-brand"/>{pending&&!receipt?"Decision awaiting confirmation":title[status]}</p>{!matches&&status==="proposed"&&!pending&&<p className="text-xs text-warning">{displayCopy(reason,"The prepared draft needs review.")}</p>}<dl className="space-y-2">{proposal.lines.filter(line=>line.before!==line.after).map(line=><div key={line.teamId} className="flex justify-between gap-3 text-xs"><dt>{displaySourceText(teams.find(team=>team.id===line.teamId)?.name,"Team")}</dt><dd className="tabular-nums">{money(line.before)} → {money(line.after)}</dd></div>)}</dl><Button type="button" variant="outline" size="sm" onClick={onReview}>{status==="proposed"&&!pending?"Review draft":status==="applied"?"View confirmation":"View details"}</Button></section>;
}
