"use client";
import { useMemo } from "react";
import type { SpendingRecord, Unit } from "@/lib/contracts";
import { formatAmount } from "@/lib/format";
import { riseDelay } from "@/components/shared/motion";
import { cn } from "@/lib/utils";
import { modelTotals, providerTotals } from "./derive";
import { ProviderLogo, providerMeta } from "./provider-brand";

/**
 * Compact section: API spend split by provider (one bar) and by model (a short table with tokens).
 * Only API rows carry a model; seats and tool overage are shown in the cost components above.
 * Dollars stay the headline; tokens are the secondary column because a cheap model can burn many of them.
 */
export function ModelBreakdown({ spending, unit, className }: { spending: SpendingRecord[]; unit: Unit; className?: string }) {
  const models = useMemo(() => modelTotals(spending), [spending]);
  const providers = useMemo(() => providerTotals(spending), [spending]);
  const total = providers.reduce((s, p) => s + p.amount, 0);
  const tokens = providers.reduce((s, p) => s + (p.tokens ?? 0), 0);
  const hasTokens = providers.some((p) => typeof p.tokens === "number");
  if (total <= 0) return null;
  const top = models[0]?.amount ?? 1;

  return (
    <section className={cn("rounded-xl border border-border bg-card", className)} aria-labelledby="model-breakdown-heading">
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-2 px-5 pt-5">
        <div>
          <h2 id="model-breakdown-heading" className="text-base font-medium">API spend by model</h2>
          <p className="mt-1 text-xs text-muted-foreground">Which models the API dollars went to this period{hasTokens ? ", with the tokens they bought" : ""}. Seats and tool overage are not included.</p>
        </div>
        <div className="flex items-baseline gap-4 text-xs text-muted-foreground">
          <span>API <span className="num text-foreground">{formatAmount(total, unit)}</span></span>
          {hasTokens && <span>Tokens <span className="num text-foreground">{formatAmount(tokens, "tokens", { compact: true })}</span></span>}
        </div>
      </div>

      <div className="grid gap-6 px-5 py-5 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        {/* By provider: one stacked bar, then a legend row per provider. */}
        <div className="min-w-0 space-y-3">
          <div className="eyebrow">By provider</div>
          <div className="flex h-2 w-full gap-0.5 overflow-hidden rounded-sm" aria-hidden>
            {providers.map((p, i) => (
              <div key={p.provider} className="animate-grow-x h-full rounded-[1px]" style={{ ...riseDelay(i), width: `${(p.amount / total) * 100}%`, background: providerMeta(p.provider).accent }} />
            ))}
          </div>
          <ul className="divide-y divide-border text-xs">
            {providers.map((p) => (
              <li key={p.provider} className="flex items-center justify-between gap-3 py-2">
                <span className="flex min-w-0 items-center gap-2">
                  <ProviderLogo provider={p.provider} />
                  <span className="truncate">{providerMeta(p.provider).label}</span>
                </span>
                <span className="flex items-baseline gap-3">
                  {typeof p.tokens === "number" && <span className="num text-muted-foreground">{formatAmount(p.tokens, "tokens", { compact: true })}</span>}
                  <span className="num w-16 text-right">{formatAmount(p.amount, unit, { compact: true })}</span>
                  <span className="num w-9 text-right text-muted-foreground">{Math.round((p.amount / total) * 100)}%</span>
                </span>
              </li>
            ))}
          </ul>
        </div>

        {/* By model: name, tokens, dollars, and a bar against the largest model. */}
        <div className="min-w-0 space-y-3">
          <div className="eyebrow">By model</div>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-[11px] text-muted-foreground">
                <th scope="col" className="pb-1.5 font-normal">Model</th>
                {hasTokens && <th scope="col" className="pb-1.5 text-right font-normal">Tokens</th>}
                <th scope="col" className="pb-1.5 text-right font-normal">Spend</th>
                <th scope="col" className="hidden w-28 pb-1.5 pl-3 font-normal sm:table-cell"><span className="sr-only">Share of API spend</span></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {models.map((m, i) => {
                const meta = providerMeta(m.provider);
                return (
                  <tr key={m.model}>
                    <td className="py-2 pr-3">
                      <span className="flex min-w-0 items-center gap-2">
                        <ProviderLogo provider={m.provider} className="size-3.5" />
                        <span className="truncate">{m.model}</span>
                      </span>
                    </td>
                    {hasTokens && <td className="num py-2 text-right text-muted-foreground">{typeof m.tokens === "number" ? formatAmount(m.tokens, "tokens", { compact: true }) : "—"}</td>}
                    <td className="num py-2 text-right">{formatAmount(m.amount, unit, { compact: true })}</td>
                    <td className="hidden py-2 pl-3 sm:table-cell">
                      <div className="h-1.5 w-full overflow-hidden rounded-sm bg-muted" aria-hidden>
                        <div className="animate-grow-x h-full rounded-[1px]" style={{ ...riseDelay(i), width: `${(m.amount / top) * 100}%`, background: meta.accent }} />
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {hasTokens && <p className="text-[11px] text-muted-foreground">Tokens come from the provider usage exports; dollars from the cost reports. Neither is added to the other.</p>}
        </div>
      </div>
    </section>
  );
}
