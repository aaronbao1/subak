"use client";
import { Fragment, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { MessageSquare } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useAppStore } from "@/lib/store";
import { AssistantDrawer } from "@/components/assistant/assistant-drawer";
import { SECTIONS, SiteHeader } from "@/components/shell/site-header";

type Crumb = { label: string; href?: string };

/** Breadcrumb derived from the route; team and person ids resolve to names from the store. */
function useCrumbs(pathname: string): Crumb[] {
  const { teams, people } = useAppStore();
  const parts = pathname.split("/").filter(Boolean);
  if (parts.length === 0) return [];
  const root = SECTIONS.find((n) => n.href === `/${parts[0]}`);
  if (!root) return [{ label: parts[0] }];
  const crumbs: Crumb[] = [{ label: root.label, href: root.href }];
  if (root.href === "/teams" && parts[1]) {
    const team = teams.find((t) => t.id === parts[1]);
    crumbs.push({ label: team?.name ?? "Team", href: `/teams/${parts[1]}` });
    if (parts[2] === "people" && parts[3]) {
      const person = people.find((p) => p.id === parts[3]);
      crumbs.push({ label: person?.name ?? "Person" });
    }
  }
  return crumbs;
}

/**
 * Product chrome: the shared site header with the unit badge and the assistant in its action slot, a slim
 * breadcrumb row only when the route is deeper than a section, the page, and the assistant drawer.
 */
export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { load, loaded, company, assistantOpen, setAssistantOpen } = useAppStore();
  useEffect(() => { if (!loaded) void load(); }, [loaded, load]);
  // Optional live mode: re-fetch everything on an interval so a streaming backend (datagen/live.py) shows up
  // without a reload. Off unless NEXT_PUBLIC_LIVE_REFRESH_MS is set (minimum 2 s).
  useEffect(() => {
    const ms = Number(process.env.NEXT_PUBLIC_LIVE_REFRESH_MS);
    if (!loaded || !Number.isFinite(ms) || ms <= 0) return;
    const id = window.setInterval(() => { void load(); }, Math.max(2000, ms));
    return () => window.clearInterval(id);
  }, [loaded, load]);
  const crumbs = useCrumbs(pathname);
  const showCrumbs = crumbs.length > 1;

  const unitLabel = company ? ({ usd: "USD", tokens: "Tokens", credits: "Credits" } as const)[company.budgetUnit] : "…";

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <SiteHeader
        actions={
          <>
            <Tooltip>
              <TooltipTrigger
                aria-label={`Unit: ${unitLabel}. Internal allocations in ${unitLabel}, not provider limits`}
                className="hidden rounded-md outline-none focus-visible:ring-2 focus-visible:ring-ring/50 sm:inline-flex"
              >
                <Badge className="num">{unitLabel}</Badge>
              </TooltipTrigger>
              <TooltipContent side="bottom">
                Internal allocations in {unitLabel}, not provider limits{company ? ` · ${company.currentPeriod.label}` : ""}
              </TooltipContent>
            </Tooltip>
            <Button
              variant={assistantOpen ? "secondary" : "brand"}
              size="lg"
              aria-pressed={assistantOpen}
              onClick={() => setAssistantOpen(!assistantOpen)}
              className="shrink-0 px-3"
            >
              <MessageSquare strokeWidth={1.5} className="size-4" /> Assistant
            </Button>
          </>
        }
      />

      {showCrumbs && (
        <nav aria-label="Breadcrumb" className="flex h-10 items-center gap-1.5 border-b border-border/70 px-4 text-sm text-muted-foreground md:px-6">
          {crumbs.map((c, i) => {
            const last = i === crumbs.length - 1;
            return (
              <Fragment key={`${c.label}-${i}`}>
                {i > 0 && <span aria-hidden className="text-muted-foreground/70">›</span>}
                {last || !c.href ? (
                  <span aria-current="page" className="truncate text-foreground">{c.label}</span>
                ) : (
                  <Link href={c.href} className="truncate transition-colors duration-300 hover:text-foreground">{c.label}</Link>
                )}
              </Fragment>
            );
          })}
        </nav>
      )}

      <main className="min-w-0 flex-1">{children}</main>

      <AssistantDrawer />
    </div>
  );
}
