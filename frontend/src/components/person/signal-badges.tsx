import { ArrowDownRight, ArrowUpRight, Building2, Minus } from "lucide-react";
import type { ContextItem, Integration, SignalKind } from "@/lib/contracts";
import { cn } from "@/lib/utils";

export const INTEGRATION_LABEL: Record<Integration, string> = {
  slack: "Slack",
  asana: "Asana",
  monday: "Monday",
  email: "Email",
  document: "Document",
  gmail: "Gmail",
  notion: "Notion",
  google_docs: "Google Docs",
  linear: "Linear",
  pdf: "PDF",
};

/** Calm, distinguishable dots per connector. Not brand colors. */
const INTEGRATION_DOT: Record<Integration, string> = {
  slack: "bg-[oklch(0.70_0.12_330)]",
  asana: "bg-[oklch(0.70_0.13_20)]",
  monday: "bg-[oklch(0.70_0.12_255)]",
  email: "bg-foreground/50",
  document: "bg-foreground/35",
  gmail: "bg-[oklch(0.70_0.17_25)]",
  notion: "bg-foreground/70",
  google_docs: "bg-[oklch(0.70_0.14_255)]",
  linear: "bg-[oklch(0.70_0.13_282)]",
  pdf: "bg-[oklch(0.68_0.16_22)]",
};

export const SIGNAL_LABEL: Record<SignalKind, string> = {
  project_deferred: "Project pushed back",
  project_accelerated: "Deadline pulled in",
  model_change: "Switching models",
  tool_change: "Switching tools",
  out_of_office: "Out of office",
  onboarding: "Ramping up",
  steady: "No change",
  pricing_change: "Pricing change",
  policy_change: "Policy change",
  project_paused: "Project paused",
};

const EFFECT_ICON = { increase: ArrowUpRight, decrease: ArrowDownRight, neutral: Minus, unknown: Minus } as const;

export function IntegrationChip({ integration, className }: { integration: Integration; className?: string }) {
  return (
    <span
      title={`Source: ${INTEGRATION_LABEL[integration]}`}
      className={cn("inline-flex h-6 items-center gap-1.5 rounded-md border border-border bg-popover px-2 text-xs font-medium whitespace-nowrap text-muted-foreground", className)}
    >
      <span aria-hidden className={cn("size-1.5 rounded-full", INTEGRATION_DOT[integration])} />
      {INTEGRATION_LABEL[integration]}
    </span>
  );
}

/** One chip summarising a person signal: what it is, which way it moves spend, where it came from. */
export function SignalChip({ item, className }: { item: ContextItem; className?: string }) {
  const Icon = EFFECT_ICON[item.expectedEffect];
  const via = item.sources[0]?.integration;
  const label = item.signal ? SIGNAL_LABEL[item.signal] : item.title;
  return (
    <span
      title={item.summary}
      className={cn(
        "inline-flex h-6 max-w-full items-center gap-1.5 rounded-md border border-border bg-popover px-2 text-xs font-medium whitespace-nowrap text-foreground/80",
        item.supersededBy && "border-dashed text-muted-foreground line-through decoration-muted-foreground",
        className,
      )}
    >
      <Icon aria-hidden strokeWidth={1.5} className={cn("size-3 shrink-0", item.expectedEffect === "increase" && "text-warning", item.expectedEffect === "decrease" && "text-muted-foreground")} />
      <span className="truncate">{label}</span>
      {via && <span aria-hidden className={cn("size-1.5 shrink-0 rounded-full", INTEGRATION_DOT[via])} title={INTEGRATION_LABEL[via]} />}
    </span>
  );
}

export function CompanyWideChip({ className }: { className?: string }) {
  return (
    <span title="Applies to the whole company, not one person or team" className={cn("inline-flex h-6 items-center gap-1.5 rounded-md border border-border bg-popover px-2 text-xs font-medium whitespace-nowrap text-foreground/80", className)}>
      <Building2 className="size-3 text-muted-foreground" aria-hidden strokeWidth={1.5} /> Company-wide
    </span>
  );
}
