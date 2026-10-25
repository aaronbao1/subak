import type { ComponentProps } from "react";
import { cn } from "@/lib/utils";

/**
 * Model providers, drawn as small inline marks with one accent each so a spend split by provider reads at a
 * glance: Anthropic clay, OpenAI neutral, Google blue. Unknown providers fall back to a neutral dot.
 */
export interface ProviderMeta {
  label: string;
  accent: string;
}

export const PROVIDER_META: Record<string, ProviderMeta> = {
  anthropic: { label: "Anthropic", accent: "oklch(0.72 0.12 45)" },
  openai: { label: "OpenAI", accent: "oklch(0.82 0.01 250)" },
  google: { label: "Google", accent: "oklch(0.70 0.14 258)" },
};

export function providerMeta(provider: string): ProviderMeta {
  return PROVIDER_META[provider] ?? { label: provider, accent: "var(--chart-other)" };
}

type SvgProps = ComponentProps<"svg">;
const base = (p: SvgProps) => ({ viewBox: "0 0 24 24", "aria-hidden": true, ...p });

function AnthropicMark(p: SvgProps) {
  return (
    <svg {...base(p)}>
      <rect x="2" y="2" width="20" height="20" rx="5" fill="#D97757" />
      <path d="M7.2 17L11 7h2l3.8 10h-2.1l-.9-2.5h-3.6L9.3 17H7.2zm3.6-4.2h2.4L12 9.5l-1.2 3.3z" fill="#1A1A1A" />
    </svg>
  );
}

function OpenAIMark(p: SvgProps) {
  return (
    <svg {...base(p)} fill="none" stroke="#FFFFFF" strokeWidth="1.6" strokeLinejoin="round">
      <circle cx="12" cy="12" r="9.5" />
      <path d="M12 6.5l4.8 2.75v5.5L12 17.5l-4.8-2.75v-5.5L12 6.5z" />
      <path d="M12 6.5v5.5M7.2 14.75L12 12l4.8 2.75" />
    </svg>
  );
}

function GeminiMark(p: SvgProps) {
  return (
    <svg {...base(p)}>
      <defs>
        <linearGradient id="gemini-mark-gradient" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#4E8EFA" />
          <stop offset="1" stopColor="#9168C0" />
        </linearGradient>
      </defs>
      <path d="M12 1.5C12.5 7.3 16.7 11.5 22.5 12 16.7 12.5 12.5 16.7 12 22.5 11.5 16.7 7.3 12.5 1.5 12 7.3 11.5 11.5 7.3 12 1.5z" fill="url(#gemini-mark-gradient)" />
    </svg>
  );
}

const MARKS: Record<string, (p: SvgProps) => React.JSX.Element> = {
  anthropic: AnthropicMark,
  openai: OpenAIMark,
  google: GeminiMark,
};

export function ProviderLogo({ provider, className }: { provider: string; className?: string }) {
  const Mark = MARKS[provider];
  if (!Mark) return <span aria-hidden className={cn("inline-block size-4 shrink-0 rounded-full", className)} style={{ background: providerMeta(provider).accent }} />;
  return <Mark className={cn("size-4 shrink-0", className)} />;
}
