import type { ComponentProps } from "react";
import { FileText, Mail } from "lucide-react";
import type { ContextItem, Integration, SourceRef } from "@/lib/contracts";
import { cn } from "@/lib/utils";

/**
 * Where a piece of evidence came from, drawn the way finance would recognise it: the app's own mark,
 * one accent hue per app for rules and avatars, and the medium (message, task or document) that decides
 * how a quote is laid out. Logos are simplified inline marks so nothing is fetched.
 */
export type SourceMedium = "message" | "task" | "document";

export interface SourceMeta {
  label: string;
  /** Accent used for the card rule, avatar and quote wash. Tuned for the dark surface. */
  accent: string;
  medium: SourceMedium;
  /** What a locator means for this app, e.g. a channel, a task status or a section. */
  noun: string;
}

export const SOURCE_META: Record<Integration, SourceMeta> = {
  slack: { label: "Slack", accent: "oklch(0.74 0.14 335)", medium: "message", noun: "channel" },
  gmail: { label: "Gmail", accent: "oklch(0.70 0.17 25)", medium: "message", noun: "thread" },
  email: { label: "Email", accent: "oklch(0.72 0.10 250)", medium: "message", noun: "thread" },
  asana: { label: "Asana", accent: "oklch(0.73 0.15 20)", medium: "task", noun: "task" },
  linear: { label: "Linear", accent: "oklch(0.70 0.13 282)", medium: "task", noun: "issue" },
  monday: { label: "monday.com", accent: "oklch(0.74 0.14 160)", medium: "task", noun: "board" },
  notion: { label: "Notion", accent: "oklch(0.88 0 0)", medium: "document", noun: "page" },
  google_docs: { label: "Google Docs", accent: "oklch(0.70 0.14 255)", medium: "document", noun: "doc" },
  pdf: { label: "PDF", accent: "oklch(0.68 0.16 22)", medium: "document", noun: "page" },
  document: { label: "Document", accent: "oklch(0.78 0 0)", medium: "document", noun: "section" },
};

/** The integration a context item is primarily sourced from: the first source that names one. */
export function primarySource(item: Pick<ContextItem, "sources">): Integration {
  return item.sources.find((s) => s.integration)?.integration ?? "document";
}

export function sourceOf(ref: Pick<SourceRef, "integration">): Integration {
  return ref.integration ?? "document";
}

/** Transparent wash of an accent for quote blocks. */
export const wash = (accent: string, pct = 7) => `color-mix(in oklch, ${accent} ${pct}%, transparent)`;

export function initials(name: string) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]?.toUpperCase() ?? "").join("");
}

/* ------------------------------------------------------------------ */
/* Marks                                                               */
/* ------------------------------------------------------------------ */

type SvgProps = ComponentProps<"svg">;
const base = (props: SvgProps) => ({ viewBox: "0 0 24 24", "aria-hidden": true, ...props });

function SlackMark(p: SvgProps) {
  return (
    <svg {...base(p)}>
      <rect x="6.5" y="1" width="5" height="11" rx="2.5" fill="#36C5F0" />
      <rect x="12" y="6.5" width="11" height="5" rx="2.5" fill="#2EB67D" />
      <rect x="12.5" y="12" width="5" height="11" rx="2.5" fill="#ECB22E" />
      <rect x="1" y="12.5" width="11" height="5" rx="2.5" fill="#E01E5A" />
    </svg>
  );
}

function AsanaMark(p: SvgProps) {
  return (
    <svg {...base(p)}>
      <circle cx="12" cy="7.5" r="4.4" fill="#F06A6A" />
      <circle cx="6.3" cy="16.8" r="4.4" fill="#F06A6A" />
      <circle cx="17.7" cy="16.8" r="4.4" fill="#F06A6A" />
    </svg>
  );
}

function MondayMark(p: SvgProps) {
  return (
    <svg {...base(p)}>
      <rect x="1.5" y="9" width="13" height="4.6" rx="2.3" fill="#FF3D57" transform="rotate(-40 8 11.3)" />
      <rect x="8" y="9" width="13" height="4.6" rx="2.3" fill="#FFCB00" transform="rotate(-40 14.5 11.3)" />
      <circle cx="19.6" cy="17.2" r="2.6" fill="#00CA72" />
    </svg>
  );
}

function GmailMark(p: SvgProps) {
  return (
    <svg {...base(p)} fill="none" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 7v11" stroke="#4285F4" />
      <path d="M21 7v11" stroke="#34A853" />
      <path d="M3 7l9 6.5L21 7" stroke="#EA4335" />
      <path d="M3 18h2.5M18.5 18H21" stroke="#FBBC04" />
    </svg>
  );
}

function NotionMark(p: SvgProps) {
  return (
    <svg {...base(p)}>
      <rect x="2.5" y="2.5" width="19" height="19" rx="3.5" fill="#FFFFFF" />
      <path d="M8.2 17V7.6l7.6 9.4V7.2" fill="none" stroke="#111111" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function GoogleDocsMark(p: SvgProps) {
  return (
    <svg {...base(p)}>
      <path d="M6 2h8l5 5v13a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z" fill="#4285F4" />
      <path d="M14 2v5h5" fill="#A1C2FA" />
      <path d="M8 12h8M8 15h8M8 18h5" stroke="#FFFFFF" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

function LinearMark(p: SvgProps) {
  return (
    <svg {...base(p)}>
      <circle cx="12" cy="12" r="10" fill="#5E6AD2" />
      <path d="M3.2 14.6l6.2 6.2M2.6 10.2l11.2 11.2M4.6 6.3l13.1 13.1M8 3.4l12.6 12.6" stroke="#FFFFFF" strokeWidth="1.7" strokeLinecap="round" />
    </svg>
  );
}

function PdfMark(p: SvgProps) {
  return (
    <svg {...base(p)}>
      <path d="M6 2h8l5 5v13a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z" fill="#E5484D" />
      <path d="M14 2v5h5" fill="#F7A6A8" />
      <text x="12" y="18" textAnchor="middle" fontSize="6.2" fontFamily="ui-monospace, monospace" fontWeight="600" fill="#FFFFFF">PDF</text>
    </svg>
  );
}

const MARKS: Record<Integration, (p: SvgProps) => React.JSX.Element> = {
  slack: SlackMark,
  asana: AsanaMark,
  monday: MondayMark,
  gmail: GmailMark,
  notion: NotionMark,
  google_docs: GoogleDocsMark,
  linear: LinearMark,
  pdf: PdfMark,
  email: (p) => <Mail {...(p as ComponentProps<typeof Mail>)} strokeWidth={1.75} style={{ color: SOURCE_META.email.accent }} />,
  document: (p) => <FileText {...(p as ComponentProps<typeof FileText>)} strokeWidth={1.75} className={cn("text-muted-foreground", p.className)} />,
};

export function SourceLogo({ integration, className }: { integration: Integration; className?: string }) {
  const Mark = MARKS[integration];
  return <Mark className={cn("size-4 shrink-0", className)} />;
}

/** Logo plus app name and, when known, the channel, task state or section the quote is from. */
export function SourceBadge({ integration, locator, className, size = "sm" }: { integration: Integration; locator?: string; className?: string; size?: "sm" | "xs" }) {
  const meta = SOURCE_META[integration];
  return (
    <span className={cn("inline-flex min-w-0 items-center gap-1.5", size === "xs" ? "text-[11px]" : "text-xs", className)}>
      <SourceLogo integration={integration} className={size === "xs" ? "size-3.5" : "size-4"} />
      <span className="font-medium text-foreground/90">{meta.label}</span>
      {locator && (
        <>
          <span aria-hidden className="text-muted-foreground/60">·</span>
          <span className="truncate text-muted-foreground">{locator}</span>
        </>
      )}
    </span>
  );
}

/** Round initials avatar in the source accent, for message-style quotes. */
export function Avatar({ name, accent, className }: { name: string; accent: string; className?: string }) {
  return (
    <span
      aria-hidden
      className={cn("flex size-7 shrink-0 items-center justify-center rounded-full font-mono text-[10px] font-medium", className)}
      style={{ background: wash(accent, 22), color: accent }}
    >
      {initials(name) || "?"}
    </span>
  );
}

/** The distinct integrations an item came from, as a row of small logos (max 3), with the names on hover. */
export function SourceLogos({ sources, className, max = 3 }: { sources: Pick<SourceRef, "integration">[]; className?: string; max?: number }) {
  const list = Array.from(new Set(sources.map(sourceOf)));
  if (list.length === 0) return null;
  const names = list.map((i) => SOURCE_META[i].label).join(", ");
  return (
    <span className={cn("inline-flex shrink-0 items-center gap-1", className)} title={`From ${names}`} aria-label={`From ${names}`}>
      {list.slice(0, max).map((i) => <SourceLogo key={i} integration={i} className="size-3.5" />)}
      {list.length > max && <span className="text-[10px] text-muted-foreground">+{list.length - max}</span>}
    </span>
  );
}
