"use client";
import { displayCopy, displayReference, displaySourceText } from "@/lib/display-copy";
import { ArrowUpRight, ChevronRight } from "lucide-react";
import type { BudgetRequest, BudgetRequestStatus } from "@/lib/contracts/budget-requests";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";

interface Props {
  request?: BudgetRequest;
  teamName?: string;
  error?: string;
  onClose: () => void;
  onPrepare: (request: BudgetRequest) => void;
  onCreateBudgetRequest?: (request: BudgetRequest) => void;
  onReviewProposal?: (proposalId: string) => void;
}

const STATUS: Record<BudgetRequestStatus, string> = {
  submitted: "Requested",
  pending_review: "Drafted",
  needs_revision: "Needs revision",
  partially_funded: "Partially funded",
  approved_applied: "Approved and applied",
  rejected: "Rejected",
};

function value(amount: string | null | undefined): number | null {
  if (amount == null || amount.trim() === "") return null;
  const parsed = Number(amount);
  return Number.isFinite(parsed) ? parsed : null;
}

function money(amount: string | null | undefined, missing = "—"): string {
  const parsed = value(amount);
  return parsed === null ? missing : new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(parsed);
}

function submittedDate(date: string): string {
  const parsed = new Date(date);
  return Number.isNaN(parsed.getTime()) ? date : new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" }).format(parsed);
}

/** Request evidence and budget assessment; preparing a review never applies a change. */
export function RequestReview({ request, teamName, error, onClose, onPrepare, onCreateBudgetRequest, onReviewProposal }: Props) {
  const assessment = request?.assessment;
  const forecastAvailable = assessment?.forecastStatus === "available" && value(assessment.forecastAmount) !== null;
  const coverageWarnings: string[] = [];
  if (assessment) {
    if (/incomplete.*coverage|subtotal/i.test(assessment.qualification)) coverageWarnings.push("Recorded spend has incomplete coverage.");
    if (/stale/i.test(assessment.qualification)) coverageWarnings.push("Forecast is stale; update it before using headroom.");
    else if (!forecastAvailable) coverageWarnings.push("Matching forecast unavailable.");
    if (assessment.teamAllocation === null || assessment.envelopeTotal === null) coverageWarnings.push("Budget unavailable for this period.");
    if (/outside the supported monetary range/i.test(assessment.qualification)) coverageWarnings.push("Requested allocation exceeds the supported amount.");
  }
  const requestedAmount = request ? value(request.requestedAmount) : null;
  const remainingAmount = request ? value(request.remainingRequestedAmount) : null;
  const canPrepare = !!request && ["submitted", "needs_revision", "partially_funded"].includes(request.status)
    && requestedAmount !== null && requestedAmount > 0 && remainingAmount !== null && remainingAmount > 0;
  const canCreateRequest = !!request && !!onCreateBudgetRequest
    && ["submitted", "needs_revision", "partially_funded"].includes(request.status)
    && (request.requestedAmount == null || request.remainingRequestedAmount == null);
  if (requestedAmount !== null && remainingAmount === null) coverageWarnings.push("Funding attribution needs review.");
  const latestProposalId = request?.linkedProposalIds.at(-1);
  const draftReady = request?.status === "pending_review" && !!latestProposalId;
  const showFunding = !!request && (request.status === "partially_funded" || request.status === "approved_applied" || (value(request.approvedAmount) ?? 0) > 0);
  const sourceReferences = request ? [...new Set([request.source.reference, request.sourceRef].filter((reference): reference is string => !!reference))] : [];
  const status = request && requestedAmount === null ? "Update" : request?.status === "pending_review" && request.linkedProposalIds.length === 0 ? "Awaiting review" : request ? STATUS[request.status] : "Requested";

  return (
    <Sheet open={!!request} onOpenChange={open => { if (!open) onClose(); }}>
      <SheetContent side="right" className="w-full gap-0 overflow-y-auto sm:max-w-[520px]">
        <SheetHeader className="gap-1.5 border-b border-border px-5 py-5 pr-12">
          <SheetTitle className="text-xl leading-snug">{displaySourceText(request?.title, "Request review")}</SheetTitle>
          <SheetDescription className="text-xs">{displaySourceText(teamName, "Team request")}{request?.projectName ? ` · ${displaySourceText(request.projectName)}` : request?.requestKind === "initiative" ? " · Initiative" : ""}{request?.period.label ? ` · ${displayCopy(request.period.label)}` : ""}</SheetDescription>
        </SheetHeader>
        {request && assessment && <div className="space-y-5 px-5 py-5">
          {error && <p role="alert" className="rounded-lg border border-warning/30 bg-warning/5 px-4 py-3 text-sm text-foreground">{displayCopy(error, "The request could not be completed.")}</p>}
          <section aria-label="Requested funding" className="rounded-lg border border-border p-4">
            <div className="flex items-start justify-between gap-3"><h3 className="text-xs text-muted-foreground">Requested amount</h3><span className="rounded-md border border-border px-2 py-1 text-xs font-medium">{status}</span></div>
            <p className="mt-2 text-3xl font-medium tabular-nums">{money(request.requestedAmount, "Not specified")}</p>
            <p className="mt-2 text-xs text-muted-foreground">{value(request.requestedAmount) === null ? "No funding amount specified. This update remains planning context." : "Additional team allocation requested"}</p>
            {showFunding && <dl className="mt-4 grid grid-cols-2 gap-4 border-t border-border pt-4">
              <Metric label="Approved amount" amount={request.approvedAmount} />
              <Metric label="Still requested" amount={request.remainingRequestedAmount} missing="Not specified" />
            </dl>}
          </section>

          <section aria-labelledby="request-assessment-heading" className="space-y-3">
            <div className="flex flex-wrap items-baseline justify-between gap-2"><h3 id="request-assessment-heading" className="text-sm font-medium">Budget position</h3><span className="text-xs text-muted-foreground">{displayCopy(request.period.label)}</span></div>
            <dl className="grid grid-cols-2 gap-x-5 gap-y-4 rounded-lg border border-border p-4">
              <Metric label="Current allocation" amount={assessment.teamAllocation} />
              <Metric label="Recorded spend" amount={assessment.recordedSpend} />
              <Metric label="Expected spend" amount={forecastAvailable ? assessment.forecastAmount : null} missing="Unavailable" />
              <Metric label="Forecast headroom" amount={forecastAvailable ? assessment.projectedHeadroom : null} missing="Unavailable" />
            </dl>
            <p className="text-[11px] text-muted-foreground">Funding request is separate from expected spend.</p>
            {coverageWarnings.length > 0 && <p className="text-xs leading-relaxed text-warning">{coverageWarnings.join(" ")}</p>}
          </section>

          {request.linkedProposalIds.length > 0 && <section aria-label="Related allocation reviews" className="space-y-2 border-t border-border pt-4">
            <h3 className="text-sm font-medium">Related allocation review</h3>
            <div className="flex flex-wrap gap-2">{draftReady && onReviewProposal && <Button type="button" onClick={() => onReviewProposal(latestProposalId!)}>Review draft</Button>}{request.linkedProposalIds.filter(proposalId => !draftReady || !onReviewProposal || proposalId !== latestProposalId).map((proposalId, index) => onReviewProposal
              ? <Button key={proposalId} type="button" variant="outline" size="sm" onClick={() => onReviewProposal(proposalId)}>Open review{request.linkedProposalIds.length > 1 ? ` ${index + 1}` : ""}<ArrowUpRight aria-hidden className="size-3.5" /></Button>
              : <span key={proposalId} className="text-xs text-muted-foreground">Allocation review {index + 1}</span>)}</div>
          </section>}

          {canCreateRequest && <div className="space-y-2"><Button type="button" variant="outline" onClick={() => onCreateBudgetRequest!(request)}>{requestedAmount === null ? "Create budget request" : "Create separate funding request"}</Button><p className="text-xs text-muted-foreground">Create a separate request with an explicit amount, keeping this update as a source.</p></div>}

          {canPrepare && <div className="space-y-2"><Button type="button" variant={request.linkedProposalIds.length ? "outline" : "default"} onClick={() => onPrepare(request)}>Prepare allocation review</Button><p className="text-xs text-muted-foreground">Finance reviews the allocation draft before budgets change.</p></div>}

          <details className="group border-t border-border pt-4 text-xs">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-2 font-medium outline-none focus-visible:ring-2 focus-visible:ring-ring [&::-webkit-details-marker]:hidden">Source and assessment details <ChevronRight aria-hidden className="size-4 text-muted-foreground transition-transform group-open:rotate-90" /></summary>
            <div className="mt-4 space-y-4">
              <section className="space-y-2"><h3 className="font-medium">Submitted request</h3><p className="whitespace-pre-wrap break-words leading-relaxed text-muted-foreground">{displaySourceText(request.narrative, "No request description available.")}</p></section>
              <dl className="space-y-4">
                <Detail label="Assessment qualification" value={displayCopy(assessment.qualification, "Unavailable")} />
                <Detail label="Submitted by" value={`${displaySourceText(request.source.submittedBy === "finance-demo" ? "Finance" : request.source.submittedBy, "Finance")} · ${submittedDate(request.source.submittedAt)}`} />
                {sourceReferences.length > 0 && <Detail label="Source reference" value={sourceReferences.map(reference => displaySourceText(displayReference(reference, "Saved source"))).join(" · ")} />}
                {!!request.evidenceRefs?.length && <Detail label="Related evidence" value={request.evidenceRefs.map(reference => `${displayCopy(reference.kind.replaceAll("_", " "))}: ${displayReference(reference.id, "Saved evidence")}${reference.version != null ? ` · version ${reference.version}` : ""}${reference.note ? ` · ${displaySourceText(reference.note)}` : ""}`).join("\n")} />}
                <Detail label="Assessed at" value={assessment.assessedAt} />
                <Detail label="Budget version" value={assessment.budgetVersion == null ? "Unavailable" : String(assessment.budgetVersion)} />
                <Detail label="Company budget" value={money(assessment.envelopeTotal)} />
                <Detail label="Forecast used" value={assessment.forecastRunId ? displayReference(assessment.forecastRunId, "Saved forecast") : "No matching forecast"} />
                <Detail label="Forecast treatment" value="The requested allocation is not included in expected spend." />
                <Detail label="Request record" value={displayReference(request.id, "Saved request")} />
                {request.decisionIds.length > 0 && <Detail label="Recorded decisions" value={request.decisionIds.map(id => displayReference(id, "Saved decision")).join(", ")} />}
              </dl>
            </div>
          </details>
        </div>}
      </SheetContent>
    </Sheet>
  );
}

function Metric({ label, amount, missing }: { label: string; amount: string | null | undefined; missing?: string }) {
  return <div className="min-w-0"><dt className="text-xs text-muted-foreground">{label}</dt><dd className="mt-1 text-base font-medium tabular-nums">{money(amount, missing)}</dd></div>;
}

function Detail({ label, value }: { label: string; value: string }) {
  return <div><dt className="text-muted-foreground">{label}</dt><dd className="mt-1 whitespace-pre-wrap break-words leading-relaxed">{displaySourceText(value, "Unavailable")}</dd></div>;
}
