import { cn } from "@/lib/utils";

/**
 * Landing-page buttons are plain links styled here so the marketing page stays dependency-free of the app's Button.
 * Mirrors DESIGN.md: brand = the one accent-filled CTA per viewport, secondary = ink fill, ghost = popover + 1px border.
 * Sizes: nav h-9 / page h-10 / hero h-[42px].
 */
export function cta(
  variant: "brand" | "secondary" | "ghost",
  size: "nav" | "page" | "hero" = "page",
  className?: string,
) {
  return cn(
    "inline-flex shrink-0 items-center justify-center gap-2 rounded-md text-sm font-medium leading-none whitespace-nowrap",
    "transition-colors duration-300 ease-in-out outline-none select-none",
    "focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:ring-offset-2 focus-visible:ring-offset-background",
    size === "nav" ? "h-9 px-3" : size === "hero" ? "h-[42px] px-4" : "h-10 px-4",
    variant === "brand" && "bg-brand text-brand-foreground hover:bg-brand-hover",
    variant === "secondary" && "bg-primary text-primary-foreground hover:bg-primary/85",
    variant === "ghost" && "border border-border bg-popover text-foreground hover:border-border-strong",
    className,
  );
}

/** Marketing container, shared by every landing section. */
export const container = "mx-auto w-full max-w-[1440px] px-4 md:px-8 lg:px-12 xl:px-16";
