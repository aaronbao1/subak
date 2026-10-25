"use client";

import { useId, useMemo } from "react";
import { ChevronDown } from "lucide-react";
import type { Period, SpendingRecord, Unit } from "@/lib/contracts";
import { formatAmount } from "@/lib/format";
import { sumMoney } from "@/lib/finance-summary";
import { cn } from "@/lib/utils";
import { selectApiSpend, type ApiSpendGroup } from "./api-spend-derive";
import { ProviderLogo, providerMeta } from "./provider-brand";

const TOP_MODELS = 5;
const currency = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 0, maximumFractionDigits: 2 });
const number = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });
const percent = new Intl.NumberFormat("en-US", { style: "percent", maximumFractionDigits: 0 });
const money = (amount: number, unit: Unit) => unit === "usd" ? currency.format(amount) : `${number.format(amount)} ${unit === "credits" ? "cr" : "tokens"}`;
const providerLabel = (provider?: string) => provider ? providerMeta(provider).label : "Unknown provider";
const tokenLabel = (row: Pick<ApiSpendGroup, "tokens" | "reportedTokens">) => row.tokens !== null ? formatAmount(row.tokens, "tokens", { compact: true }) : row.reportedTokens !== null ? "Partial" : "—";

/** Recorded API charges only; tokens, seats and unpriced usage never enter the amount. */
export function ModelBreakdown({ spending, period, unit, className }: {
  spending: SpendingRecord[];
  period: Period;
  unit: Unit;
  className?: string;
}) {
  const headingId = useId();
  const result = useMemo(() => selectApiSpend({ records: spending, period, unit }), [spending, period, unit]);
  const shown = result.models.slice(0, TOP_MODELS);
  const remaining = result.models.slice(TOP_MODELS);
  const remainingTotal = sumMoney(remaining.map(row => row.amount));
  const positiveMix = result.total !== null && result.total > 0 && result.providers.every(row => row.amount >= 0);
  const signedModels = result.models.some(row => row.amount < 0);
  const maxModel = Math.max(...result.models.map(row => Math.abs(row.amount)), 0);
  const notices = [
    result.invalidAmountCount ? `${result.invalidAmountCount} charge ${result.invalidAmountCount === 1 ? "amount is" : "amounts are"} unavailable.` : "",
    result.coverage === "partial" && !result.invalidAmountCount ? "Some records are partial." : "",
    result.unpricedRecordCount ? `${result.unpricedRecordCount} unpriced usage ${result.unpricedRecordCount === 1 ? "record" : "records"} excluded.` : "",
  ].filter(Boolean);
  const noData = result.status === "unavailable_amounts"
    ? "API charge amounts are unavailable."
    : unit === "tokens"
      ? "API spend requires a financial unit."
      : "No API charges recorded for this period.";

  return (
    <section className={cn("min-w-0 rounded-xl border border-border bg-card p-5", className)} aria-labelledby={headingId}>
      <header className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div>
          <h2 id={headingId} className="text-base font-medium">API spend by model</h2>
          <p className="mt-1 text-xs text-muted-foreground">Recorded API charges · excludes seats and tool overage</p>
        </div>
        {result.total !== null && (
          <div className="shrink-0 text-right">
            <p className="num text-lg font-medium leading-6">{money(result.total, unit)}</p>
            {result.tokens !== null ? (
              <p className="num mt-0.5 text-[11px] text-muted-foreground">{formatAmount(result.tokens, "tokens")}</p>
            ) : (
              <p className="mt-0.5 text-[11px] text-muted-foreground">{result.reportedTokens !== null ? "Token coverage partial" : "Tokens unavailable"}</p>
            )}
          </div>
        )}
      </header>
      {result.status !== "available" ? (
        <p className="py-10 text-sm text-muted-foreground">{noData}</p>
      ) : (
        <>
          {positiveMix && (
            <div className="mt-4 flex h-2 overflow-hidden rounded-sm bg-muted" aria-hidden="true">
              {result.providers.map(row => (
                <span key={row.key} className="h-full first:rounded-l-sm last:rounded-r-sm" style={{ width: `${row.share! * 100}%`, background: providerMeta(row.provider ?? "").accent }} />
              ))}
            </div>
          )}
          <ul className={cn("flex flex-wrap gap-x-4 gap-y-1.5 text-[11px] text-muted-foreground", positiveMix ? "mt-2" : "mt-4")} aria-label="API spend by provider">
            {result.providers.map(row => (
              <li key={row.key} className="flex items-center gap-1.5" title={`${providerLabel(row.provider)}: ${money(row.amount, unit)}`}>
                <span className="size-1.5 shrink-0 rounded-full" style={{ background: providerMeta(row.provider ?? "").accent }} aria-hidden="true" />
                <span>{providerLabel(row.provider)}</span>
                <span className="num text-foreground/80">{positiveMix ? percent.format(row.share!) : money(row.amount, unit)}</span>
                {positiveMix && <span className="sr-only">{money(row.amount, unit)}</span>}
              </li>
            ))}
          </ul>
          <div className="mt-3">
            <ModelTable rows={shown} unit={unit} max={maxModel} signed={signedModels} />
            {remaining.length > 0 && (
              <details className="group mt-1">
                <summary className="flex cursor-pointer list-none items-center gap-2 rounded-sm py-1.5 text-xs text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring [&::-webkit-details-marker]:hidden">
                  <ChevronDown className="size-3.5 transition-transform group-open:rotate-180" aria-hidden="true" />
                  <span>{remaining.length} more {remaining.length === 1 ? "model" : "models"}</span>
                  <span className="num ml-auto">{money(remainingTotal, unit)}</span>
                </summary>
                <ModelTable rows={remaining} unit={unit} max={maxModel} signed={signedModels} />
              </details>
            )}
          </div>
        </>
      )}
      {(notices.length > 0 || result.hasRefunds) && (
        <p className="mt-3 text-[11px] leading-relaxed text-muted-foreground">{[result.hasRefunds ? "Net of credits." : "", ...notices].filter(Boolean).join(" ")}</p>
      )}
    </section>
  );
}

function ModelTable({ rows, unit, max, signed }: { rows: ApiSpendGroup[]; unit: Unit; max: number; signed: boolean }) {
  return (
    <table className="w-full table-fixed text-xs">
      <thead>
        <tr className="text-left text-[11px] text-muted-foreground">
          <th scope="col" className="pb-1 font-normal">Model</th>
          <th scope="col" className="w-16 pb-1 text-right font-normal">Tokens</th>
          <th scope="col" className="w-24 pb-1 text-right font-normal">Spend</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-border/70">
        {rows.map(row => {
          const model = row.model ?? "Unknown model";
          const provider = providerLabel(row.provider);
          const width = max ? Math.abs(row.amount) / max * (signed ? 50 : 100) : 0;
          const tokensTitle = row.tokens !== null ? formatAmount(row.tokens, "tokens") : row.reportedTokens !== null
            ? `${formatAmount(row.reportedTokens, "tokens")} reported; ${row.missingTokenCount} ${row.missingTokenCount === 1 ? "record lacks" : "records lack"} token counts.`
            : "Token counts unavailable.";
          return (
            <tr key={row.key}>
              <td className="relative py-1.5 pr-5" title={`${model} · ${provider}`}>
                <span className="flex min-w-0 items-center gap-2">
                  <ProviderLogo provider={row.provider ?? ""} className="size-3.5" />
                  <span className="truncate">{model}<span className="sr-only"> · {provider}</span></span>
                </span>
                <div className="absolute right-5 bottom-0.5 left-5.5 h-0.5 overflow-hidden rounded-full bg-muted" aria-hidden="true">
                  {signed && <span className="absolute left-1/2 h-full w-px bg-border" />}
                  <span className="absolute h-full rounded-full" style={{ width: `${width}%`, left: signed ? `${row.amount < 0 ? 50 - width : 50}%` : "0%", background: providerMeta(row.provider ?? "").accent }} />
                </div>
              </td>
              <td className="num py-1.5 text-right text-muted-foreground" title={tokensTitle}>{tokenLabel(row)}<span className="sr-only">{row.tokens === null ? ` ${tokensTitle}` : ""}</span></td>
              <td className="num py-1.5 text-right">{money(row.amount, unit)}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
