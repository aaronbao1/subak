"use client";
import { useMemo, useState } from "react";
import type { SpendingRecord, Unit } from "@/lib/contracts";
import { formatAmount } from "@/lib/format";
import { cn } from "@/lib/utils";
import { modelTotals, providerTotals } from "./derive";
import { ProviderLogo, providerMeta } from "./provider-brand";
import { BarRow, CountUp, StackedBar } from "./bars";

const TOP = 5;

/** "1.2B tokens" for a tooltip; dollars and tokens are never added together. */
const tokensText = (tokens?: number) => (typeof tokens === "number" ? ` · ${formatAmount(tokens, "tokens")}` : "");

/**
 * API dollars only: a provider mix bar with chips, then the top models as a bar list (+N more).
 * Tokens move to each row's tooltip; the header keeps the total.
 */
export function ModelBreakdown({ spending, unit, className }: { spending: SpendingRecord[]; unit: Unit; className?: string }) {
  const models = useMemo(() => modelTotals(spending), [spending]);
  const providers = useMemo(() => providerTotals(spending), [spending]);
  const [expanded, setExpanded] = useState(false);
  const total = providers.reduce((s, p) => s + p.amount, 0);
  const tokens = providers.reduce((s, p) => s + (p.tokens ?? 0), 0);
  const hasTokens = providers.some((p) => typeof p.tokens === "number");
  if (total <= 0) return null;
  const top = models[0]?.amount ?? 1;
  const shown = expanded ? models : models.slice(0, TOP);
  const rest = models.length - shown.length;
  const money = (n: number) => formatAmount(n, unit, { compact: true });

  return (
    <section className={cn("min-w-0 rounded-xl border border-border bg-card p-5", className)} aria-labelledby="model-breakdown-heading">
      <header className="flex items-baseline justify-between gap-4">
        <h2 id="model-breakdown-heading" className="text-base font-medium">API spend by model</h2>
        <span className="flex items-baseline gap-3 text-xs text-muted-foreground">
          <span className="num text-foreground"><CountUp value={total} format={money} /></span>
          {hasTokens && <span className="num" title="From provider usage exports; not added to dollars">{formatAmount(tokens, "tokens")}</span>}
        </span>
      </header>

      <StackedBar
        className="mt-4"
        segments={providers.map((p) => ({
          key: p.provider, value: p.amount, color: providerMeta(p.provider).accent,
          title: `${providerMeta(p.provider).label} ${formatAmount(p.amount, unit)}${tokensText(p.tokens)}`,
        }))}
      />
      <ul className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground" aria-label="By provider">
        {providers.map((p) => (
          <li key={p.provider} className="flex items-center gap-1.5" title={`${formatAmount(p.amount, unit)}${tokensText(p.tokens)}`}>
            <span className="size-2 shrink-0 rounded-sm" style={{ background: providerMeta(p.provider).accent }} aria-hidden />
            {providerMeta(p.provider).label}
            <span className="num text-foreground/80">{Math.round((p.amount / total) * 100)}%</span>
          </li>
        ))}
      </ul>

      <ul className="mt-3" aria-label="By model">
        {shown.map((m, i) => (
          <BarRow
            key={m.model} index={i}
            label={<><ProviderLogo provider={m.provider} className="size-3.5" /><span className="truncate">{m.model}</span></>}
            value={m.amount} max={top} color={providerMeta(m.provider).accent}
            title={`${m.model} · ${formatAmount(m.amount, unit)}${tokensText(m.tokens)}`}
            valueNode={money(m.amount)}
          />
        ))}
      </ul>
      {(rest > 0 || expanded) && models.length > TOP && (
        <button
          type="button" onClick={() => setExpanded((e) => !e)}
          className="mt-1 text-xs text-muted-foreground transition-colors duration-300 hover:text-foreground"
        >
          {expanded ? "Show fewer" : `+${rest} more`}
        </button>
      )}
    </section>
  );
}
