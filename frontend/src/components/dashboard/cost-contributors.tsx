"use client";

import { useId, useMemo } from "react";
import { ChevronDown } from "lucide-react";
import type { Period, Provenance, SpendingRecord, Unit } from "@/lib/contracts";
import { selectCostContributors, type CostContributor } from "@/lib/cost-contributors";
import { cn } from "@/lib/utils";
import { ProvenanceBadge } from "@/components/team/labels";
import { ProviderLogo, providerMeta } from "./provider-brand";

const currency = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2, minimumFractionDigits: 0 });
const number = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });
const percent = new Intl.NumberFormat("en-US", { style: "percent", maximumFractionDigits: 1 });
const amountLabel = (amount: number, unit: Unit) => unit === "usd" ? currency.format(amount) : `${number.format(amount)} cr`;

/** A focused, additive breakdown of recorded financial amounts; source detail is disclosed per row. */
export function CostContributors({ records, period, teamId, personId, compact = false }: {
  records: SpendingRecord[];
  period: Period;
  teamId?: string;
  personId?: string;
  compact?: boolean;
}) {
  const headingId = useId();
  const result = useMemo(() => selectCostContributors({ records, period, teamId, personId }), [records, period, teamId, personId]);
  const rows = result.other ? [...result.contributors, result.other] : result.contributors;
  const emptyMessage = result.status === "mixed_units"
    ? "Recorded amounts use different units, so a combined ranking is unavailable."
    : result.status === "no_financial_records"
      ? "Usage is recorded, but there are no eligible financial charges for this period."
      : result.status === "unavailable_amounts"
        ? "Recorded charges are missing usable amounts."
        : "No recorded spending for this period and scope.";
  const coverage = result.invalidAmountCount > 0
    ? "Some charge amounts are unavailable; shares cover the amounts shown."
    : result.coverage === "partial"
      ? "Some recorded spending is partial."
      : "Full source coverage is unverified.";

  return (
    <section aria-labelledby={headingId} className={cn("min-w-0 rounded-xl border border-border bg-card", compact ? "p-4" : "p-5")}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id={headingId} className="text-sm font-medium">Where the money went</h2>
          <p className="mt-1 text-xs text-muted-foreground">Recorded spend by provider and model</p>
        </div>
        {result.total !== null && result.unit && <p className="num text-sm font-medium">{amountLabel(result.total, result.unit)}</p>}
      </div>
      {result.status !== "available" || !result.unit ? (
        <p className="py-6 text-sm text-muted-foreground">{emptyMessage}</p>
      ) : (
        <>
          <div className="mt-4 flex justify-between gap-3 text-[11px] text-muted-foreground" aria-hidden="true">
            <span>Contributor</span>
            <span>Amount · share</span>
          </div>
          <ul className="mt-1 divide-y divide-border">
            {rows.map(row => <ContributorRow key={row.key} row={row} unit={result.unit!} />)}
          </ul>
          <p className="mt-3 text-[11px] leading-relaxed text-muted-foreground">{coverage} Included and unpriced usage are excluded.</p>
        </>
      )}
    </section>
  );
}

function ContributorRow({ row, unit }: { row: CostContributor; unit: Unit }) {
  const isOther = row.key === "other";
  const provider = row.provider ? providerMeta(row.provider).label : "Unattributed provider";
  const title = isOther ? "Other" : row.model || provider;
  const subtitle = isOther ? `${row.groupCount} remaining contributors` : row.model ? provider : "Provider charges";
  const provenances = Object.keys(row.byProvenance) as Provenance[];
  return (
    <li>
      <details className="group">
        <summary className="flex cursor-pointer list-none items-center gap-3 rounded-sm py-3 outline-none focus-visible:ring-2 focus-visible:ring-ring [&::-webkit-details-marker]:hidden">
          {row.provider && <ProviderLogo provider={row.provider} className="size-4 shrink-0" />}
          <span className="min-w-0 flex-1">
            <span className="block break-words text-sm font-medium">{title}</span>
            <span className="mt-0.5 block text-[11px] text-muted-foreground">{subtitle}</span>
            <span className="mt-1.5 flex flex-wrap gap-1">
              {provenances.map(provenance => <ProvenanceBadge key={provenance} provenance={provenance} />)}
            </span>
          </span>
          <span className="shrink-0 text-right">
            <span className="num block text-sm">{amountLabel(row.amount, unit)}</span>
            <span className="num mt-0.5 block text-xs text-muted-foreground">{row.share === null ? "Share unavailable" : percent.format(row.share)}</span>
          </span>
          <ChevronDown aria-hidden="true" className="size-3.5 shrink-0 text-muted-foreground transition-transform group-open:rotate-180" />
        </summary>
        <div className="mb-3 space-y-3 rounded-lg bg-muted/40 p-3 text-xs">
          <dl className="space-y-2">
            {provenances.map(provenance => (
              <div key={provenance} className="flex flex-wrap items-center justify-between gap-2">
                <dt><ProvenanceBadge provenance={provenance} /></dt>
                <dd className="num">{amountLabel(row.byProvenance[provenance]!, unit)}</dd>
              </div>
            ))}
          </dl>
          <p className="text-muted-foreground">Based on {number.format(row.recordCount)} financial {row.recordCount === 1 ? "record" : "records"} in the selected period.</p>
          {row.sources.length > 0 && (
            <div>
              <p className="font-medium">Sources</p>
              <ul className="mt-1 space-y-1 break-words text-muted-foreground">
                {row.sources.slice(0, 3).map(source => <li key={source}>{source}</li>)}
              </ul>
              {row.sources.length > 3 && (
                <details className="mt-2">
                  <summary className="cursor-pointer rounded-sm text-muted-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring">{row.sources.length - 3} more sources</summary>
                  <ul className="mt-2 space-y-1 break-words text-muted-foreground">
                    {row.sources.slice(3).map(source => <li key={source}>{source}</li>)}
                  </ul>
                </details>
              )}
            </div>
          )}
        </div>
      </details>
    </li>
  );
}
