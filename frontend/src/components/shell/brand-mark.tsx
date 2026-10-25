import { cn } from "@/lib/utils";

/** Compact brand mark: a four-cell grid, echoing an allocation across teams. Shared by the app shell and the landing page. */
export function BrandMark({ className }: { className?: string }) {
  return (
    <span
      aria-hidden
      className={cn(
        "grid size-6 shrink-0 grid-cols-2 gap-[3px] rounded-md border border-border bg-card p-[5px]",
        className,
      )}
    >
      <span className="rounded-[1px] bg-foreground" />
      <span className="rounded-[1px] bg-foreground/40" />
      <span className="rounded-[1px] bg-foreground/40" />
      <span className="rounded-[1px] bg-ring" />
    </span>
  );
}
