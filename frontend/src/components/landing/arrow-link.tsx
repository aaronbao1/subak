import Link from "next/link";
import type { ComponentProps } from "react";
import { cn } from "@/lib/utils";

/**
 * Text link with a drawn arrow, for "see it" links under feature copy.
 * At rest: the label and a 6px arrowhead on one shared hairline. On hover the shaft draws left to right
 * through the head (pathLength 1, dash offset 1 -> 0), then the whole arrow eases 2px to the right.
 * Reduced motion zeroes both transitions via the global rule.
 */
export function ArrowLink({ className, children, ...props }: ComponentProps<typeof Link>) {
  return (
    <Link
      {...props}
      className={cn(
        "group inline-flex items-center gap-1.5 border-b border-border-strong pb-px text-sm text-foreground",
        "transition-colors duration-300 hover:border-foreground",
        className,
      )}
    >
      <span>{children}</span>
      <svg
        aria-hidden
        viewBox="0 0 12 8"
        width="12"
        height="8"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.1"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="shrink-0 text-muted-foreground transition-[transform,color] duration-300 delay-150 group-hover:translate-x-0.5 group-hover:text-foreground"
      >
        {/* Shaft: hidden at rest, draws toward the head on hover. */}
        <path
          d="M1 4h9"
          pathLength={1}
          className="[stroke-dasharray:1] [stroke-dashoffset:1] transition-[stroke-dashoffset] duration-300 ease-out group-hover:[stroke-dashoffset:0]"
        />
        {/* Head */}
        <path d="M7.5 1.5 10 4 7.5 6.5" />
      </svg>
    </Link>
  );
}
