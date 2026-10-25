"use client";
import { Fragment, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { MessageSquare, ChevronRight, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAppStore } from "@/lib/store";
import { AssistantDrawer } from "@/components/assistant/assistant-drawer";
import { SECTIONS, SiteHeader } from "@/components/shell/site-header";

type Crumb = { label: string; href?: string };

/** Breadcrumb derived from the route; team and person ids resolve to names from the store. */
function useCrumbs(pathname: string): Crumb[] {
  const { teams, people } = useAppStore();
  const parts = pathname.split("/").filter(Boolean);
  const section = SECTIONS.find((n) => n.href === `/${parts[0]}`);
  const crumbs: Crumb[] = [{ label: section?.label ?? "Workspace", href: section?.href }];
  if (parts[0] === "teams" && parts[1]) {
    crumbs.push({ label: teams.find((t) => t.id === parts[1])?.name ?? "Team", href: `/teams/${parts[1]}` });
    if (parts[2] === "people" && parts[3]) crumbs.push({ label: people.find((p) => p.id === parts[3])?.name ?? "Person" });
  }
  return crumbs;
}

/**
 * Product chrome: the same top header as the landing page (brand, section tabs on the center line, actions),
 * with the unit and the assistant in the action slot. A slim breadcrumb row appears only when the route is
 * deeper than a section. Load and sync notices sit above the page.
 */
export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { load, loaded, company, assistantOpen, setAssistantOpen, loadState, loadError, budgetSync } = useAppStore();
  useEffect(() => { if (!loaded && (!loadState || loadState === "idle")) void load(); }, [loaded, loadState, load]);
  // Optional live mode: re-fetch on an interval so a streaming backend shows up without a reload.
  useEffect(() => {
    const ms = Number(process.env.NEXT_PUBLIC_LIVE_REFRESH_MS);
    if (!loaded || !Number.isFinite(ms) || ms <= 0) return;
    const id = window.setInterval(() => { void load(); }, Math.max(2000, ms));
    return () => window.clearInterval(id);
  }, [loaded, load]);
  const crumbs = useCrumbs(pathname);
  const showCrumbs = crumbs.length > 1;
  const unit = company ? ({ usd: "USD", tokens: "Tokens", credits: "Credits" } as const)[company.budgetUnit] : "USD";

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <a href="#main-content" className="fixed top-3 left-4 z-50 -translate-y-20 rounded-md bg-primary px-4 py-2 text-primary-foreground focus:translate-y-0">
        Skip to content
      </a>

      <SiteHeader
        actions={
          <>
            <span className="hidden text-xs text-muted-foreground sm:inline" title={company ? `${company.name} · internal allocations in ${unit}` : undefined}>
              {unit}
            </span>
            <Button
              variant={assistantOpen ? "secondary" : "outline"}
              aria-label="Droid Assistant"
              aria-pressed={assistantOpen}
              onClick={() => setAssistantOpen(!assistantOpen)}
              className="px-3"
            >
              <MessageSquare className="size-4" strokeWidth={1.5} />
              <span className="hidden sm:inline">Droid Assistant</span>
            </Button>
          </>
        }
      />

      {showCrumbs && (
        <nav aria-label="Breadcrumb" className="flex h-10 items-center gap-2 border-b border-border/70 px-4 text-sm sm:px-6 lg:px-8">
          {crumbs.map((crumb, i) => (
            <Fragment key={`${crumb.label}-${i}`}>
              {i > 0 && <ChevronRight aria-hidden className="size-3 shrink-0 text-muted-foreground" />}
              {i === crumbs.length - 1 ? (
                <span aria-current="page" className="truncate">{crumb.label}</span>
              ) : (
                <Link className="truncate text-muted-foreground transition-colors hover:text-foreground" href={crumb.href ?? "/overview"}>
                  {crumb.label}
                </Link>
              )}
            </Fragment>
          ))}
        </nav>
      )}

      {(loadState === "error" || loadState === "stale") && (
        <div role="alert" className="mx-4 mt-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-warning/30 bg-warning/5 px-4 py-3 text-sm sm:mx-6 lg:mx-8">
          <span>{loaded ? "Showing your last loaded data. " : "Unable to load this workspace. "}{loadError}</span>
          <Button variant="outline" size="sm" onClick={() => void load()}><RefreshCw className="size-3.5" />Retry</Button>
        </div>
      )}
      {budgetSync === "stale" && (
        <div role="status" className="mx-4 mt-4 rounded-lg border border-warning/30 px-4 py-3 text-sm sm:mx-6 lg:mx-8">
          Your change was saved. Budget totals are waiting to refresh.
        </div>
      )}

      <main id="main-content" tabIndex={-1} className="min-w-0 flex-1 outline-none">{children}</main>
      <AssistantDrawer />
    </div>
  );
}
