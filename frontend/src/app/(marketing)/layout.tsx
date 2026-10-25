/*
 * The landing page shares the app's dark palette (globals.css) so "Open dashboard" does not flip the theme.
 * Landing components use bg-background / text-foreground / border-border and inherit it directly.
 */
export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col overflow-x-clip bg-background text-foreground">
      {children}
    </div>
  );
}
