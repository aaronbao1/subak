"use client";
import ReactMarkdown from "react-markdown";
import { cn } from "@/lib/utils";

/** Restrained markdown for assistant messages. Emphasis is weight 500 or an ink shift, never bold. */
export function Markdown({ children, className }: { children: string; className?: string }) {
  return (
    <div className={cn(
      "text-sm leading-relaxed",
      "[&_p]:mb-2 [&_p:last-child]:mb-0",
      "[&_ul]:mb-2 [&_ul]:list-disc [&_ul]:pl-4 [&_ol]:mb-2 [&_ol]:list-decimal [&_ol]:pl-4 [&_li]:mb-0.5 [&_li]:marker:text-muted-foreground",
      "[&_strong]:font-medium [&_strong]:text-foreground",
      "[&_h1]:mb-1 [&_h1]:text-base [&_h1]:font-medium [&_h2]:mt-3 [&_h2]:mb-1 [&_h2]:text-sm [&_h2]:font-medium [&_h3]:mt-2 [&_h3]:mb-1 [&_h3]:font-medium",
      "[&_blockquote]:border-l [&_blockquote]:border-border-strong [&_blockquote]:pl-3 [&_blockquote]:text-muted-foreground",
      "[&_code]:rounded-sm [&_code]:bg-popover [&_code]:px-1 [&_code]:font-mono [&_code]:text-xs",
      "[&_a]:underline [&_a]:underline-offset-4 [&_a]:decoration-border-strong hover:[&_a]:decoration-foreground",
      "[&_table]:w-full [&_table]:text-xs [&_th]:border-b [&_th]:border-border-strong [&_th]:pb-1 [&_th]:text-left [&_th]:font-medium [&_th]:text-muted-foreground [&_td]:border-b [&_td]:border-border [&_td]:py-1 [&_td]:tabular-nums",
      "[&_hr]:my-3 [&_hr]:border-border",
      className,
    )}>
      <ReactMarkdown>{children}</ReactMarkdown>
    </div>
  );
}
