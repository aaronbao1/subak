"use client";
import { useState } from "react";
import type { BudgetRequest } from "@/lib/contracts/budget-requests";
import { useAppStore } from "@/lib/store";
import { getDataClient } from "@/lib/data";
import { AllocationWorkbench } from "@/components/allocation/allocation-workbench";
import { ProposalReview } from "@/components/allocation/proposal-review";
import { AddTeamUpdate } from "./add-team-update";
import { RequestReview } from "./request-review";

export function RequestDialogs({ request, onCloseRequest, adding, onCloseAdd, onSaved }: { request?: BudgetRequest; onCloseRequest: () => void; adding: boolean; onCloseAdd: () => void; onSaved: (request: BudgetRequest) => void }) {
  const { company, teams, loadRequests } = useAppStore();
  const [formVersion, setFormVersion] = useState(0);
  const [createFrom, setCreateFrom] = useState<BudgetRequest>();
  const [creatingFrom, setCreatingFrom] = useState(false);
  const [allocationRequest, setAllocationRequest] = useState<BudgetRequest>();
  const [proposalId, setProposalId] = useState<string>();
  const [error, setError] = useState<string>();
  async function reviewProposal(id: string) {
    setError(undefined);
    try {
      if (!useAppStore.getState().proposals.some(proposal => proposal.id === id)) {
        const proposal = await getDataClient().getProposal(id);
        if (!proposal) throw new Error("The related draft could not be found.");
        useAppStore.setState(state => ({ proposals: [...state.proposals.filter(item => item.id !== id), proposal] }));
      }
      onCloseRequest();
      setProposalId(id);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "The draft could not be loaded."); }
  }
  const period = allocationRequest ? { start: allocationRequest.periodStart, end: new Date(Date.parse(`${allocationRequest.periodEndExclusive}T00:00:00Z`) - 86_400_000).toISOString().slice(0, 10), label: allocationRequest.period.label } : undefined;
  return <>
    <RequestReview error={error} request={request} teamName={teams.find(team => team.id === request?.teamId)?.name} onClose={() => { setError(undefined); onCloseRequest(); }} onPrepare={item => { onCloseRequest(); setAllocationRequest(item); }} onReviewProposal={id => void reviewProposal(id)} onCreateBudgetRequest={item => { onCloseRequest(); setCreateFrom(item); setCreatingFrom(true); }} />
    <AddTeamUpdate key={`new-${company?.id}-${company?.currentPeriod.start}-${formVersion}`} open={adding} onClose={onCloseAdd} onSaved={item => { onCloseAdd(); setFormVersion(version => version + 1); onSaved(item); }} />
    {createFrom && <AddTeamUpdate key={`source-${createFrom.id}`} initialUpdate={createFrom} open={creatingFrom} onClose={() => setCreatingFrom(false)} onSaved={item => { setCreatingFrom(false); setCreateFrom(undefined); onSaved(item); }} />}
    <AllocationWorkbench open={!!allocationRequest} onOpenChange={open => { if (!open) { setAllocationRequest(undefined); void loadRequests(); } }} initialRequest={allocationRequest && period ? { id: allocationRequest.id, teamId: allocationRequest.teamId, amount: allocationRequest.remainingRequestedAmount, period, unit: "usd", title: allocationRequest.title } : undefined} />
    <ProposalReview proposalId={proposalId} onClose={() => { setProposalId(undefined); void loadRequests(); }} />
  </>;
}
