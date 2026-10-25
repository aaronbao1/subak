import type { CSSProperties } from "react";

/*
 * The landing page shares the app's dark palette (globals.css) so "Open dashboard" does not flip the theme.
 * The one difference: the brand accent is remapped to ink for this subtree, so the page carries no color
 * other than the chart series inside the product mocks. The filled CTA, the brand mark, selection and focus
 * all read these tokens, so no landing component names the accent directly.
 */
const inkAccent = {
  "--brand": "var(--primary)",
  "--brand-hover": "oklch(1 0 0)",
  "--brand-foreground": "var(--primary-foreground)",
  "--brand-soft": "oklch(1 0 0 / 8%)",
  "--ring": "oklch(1 0 0 / 40%)",
} as CSSProperties;

export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  return (
    <div style={inkAccent} className="flex min-h-screen flex-col overflow-x-clip bg-background text-foreground">
      {children}
    </div>
  );
}
