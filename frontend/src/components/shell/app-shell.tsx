"use client";
import { Fragment, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Users, FileSearch, History, MessageSquare, Info } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useAppStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import { AssistantDrawer } from "@/components/assistant/assistant-drawer";
import { BrandMark } from "@/components/shell/brand-mark";

const nav = [
  { href: "/overview", label: "Overview", icon: LayoutDashboard },
  { href: "/teams", label: "Teams", icon: Users },
  { href: "/evidence", label: "Evidence", icon: FileSearch },
  { href: "/decisions", label: "Decisions", icon: History },
];

function isActive(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(`${href}/`);
}

type Crumb = { label: string; href?: string };

/** Breadcrumb derived from the route; team and person ids resolve to names from the store. */
function useCrumbs(pathname: string): Crumb[] {
  const { teams, people } = useAppStore();
  const parts = pathname.split("/").filter(Boolean);
  if (parts.length === 0) return [];
  const root = nav.find((n) => n.href === `/${parts[0]}`);
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
 * Product chrome as one top bar: brand, the four sections as tabs with the brand rule under the active one,
 * then the period, the unit and the assistant. A second slim row carries the breadcrumb only
 * when the route is deeper than a section, so the overview keeps its full height.
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

  const tabs = (className: string) => (
    <nav className={className} aria-label="Primary">
      {nav.map(({ href, label, icon: Icon }) => {
        const active = isActive(pathname, href);
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "group relative flex h-14 shrink-0 items-center gap-2 px-3 text-sm whitespace-nowrap text-muted-foreground transition-colors duration-300",
              "hover:text-foreground focus-visible:ring-4 focus-visible:ring-ring focus-visible:outline-none",
              active && "text-foreground",
            )}
          >
            <Icon strokeWidth={1.5} className={cn("size-4 shrink-0 text-muted-foreground transition-colors duration-300 group-hover:text-foreground", active && "text-foreground")} />
            {label}
            {/* Active rule in the budgeted accent, sitting on the header's bottom border. */}
            <span aria-hidden className={cn("absolute inset-x-3 -bottom-px h-0.5 rounded-full bg-brand opacity-0 transition-opacity duration-300", active && "opacity-100")} />
          </Link>
        );
      })}
    </nav>
  );

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <header className="sticky top-0 z-30 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
        <div className="flex h-14 items-center gap-4 px-4 md:gap-6 md:px-6">
          <Link href="/" aria-label="About AI Spend Planner" className="flex min-w-0 shrink-0 items-center gap-2.5 rounded-md outline-none focus-visible:ring-4 focus-visible:ring-ring">
            <BrandMark />
            <span className="hidden min-w-0 leading-tight lg:block">
              <span className="block truncate text-[15px] font-medium text-foreground">AI Spend Planner</span>
              <span className="block truncate text-xs text-muted-foreground">{company?.name ?? "Loading…"}</span>
            </span>
          </Link>

          {tabs("hidden h-14 items-center md:flex")}

          <div className="ml-auto flex min-w-0 items-center gap-2 sm:gap-3">
            <span className="num hidden truncate text-xs text-muted-foreground xl:inline">{company?.currentPeriod.label ?? "—"}</span>
            <div className="hidden items-center gap-1 sm:flex">
              <Badge className="num">{unitLabel}</Badge>
              <Tooltip>
                <TooltipTrigger
                  aria-label="About these amounts"
                  className="inline-flex size-6 items-center justify-center rounded-md text-muted-foreground transition-colors duration-300 outline-none hover:text-foreground focus-visible:ring-4 focus-visible:ring-ring"
                >
                  <Info strokeWidth={1.5} className="size-4" />
                </TooltipTrigger>
                <TooltipContent side="bottom">
                  Internal allocations in {unitLabel} — planning records, not provider limits or purchases.
                </TooltipContent>
              </Tooltip>
            </div>
            <Button
              variant={assistantOpen ? "secondary" : "brand"}
              size="lg"
              aria-pressed={assistantOpen}
              onClick={() => setAssistantOpen(!assistantOpen)}
              className="shrink-0 px-3"
            >
              <MessageSquare strokeWidth={1.5} className="size-4" /> Assistant
            </Button>
          </div>
        </div>

        {/* Narrow screens: tabs scroll in their own row. */}
        <div className="border-t border-border md:hidden">
          {tabs("flex items-center overflow-x-auto px-1")}
        </div>
      </header>

      {showCrumbs && (
        <nav aria-label="Breadcrumb" className="flex h-10 items-center gap-1.5 border-b border-border px-4 text-sm text-muted-foreground md:px-6">
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
