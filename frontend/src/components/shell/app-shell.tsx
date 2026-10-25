"use client";
import { Fragment, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Users, History, MessageSquare, ArrowUpLeft, Info } from "lucide-react";
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

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { load, loaded, company, assistantOpen, setAssistantOpen } = useAppStore();
  useEffect(() => { if (!loaded) void load(); }, [loaded, load]);
  const crumbs = useCrumbs(pathname);

  const unitLabel = company ? ({ usd: "USD", tokens: "Tokens", credits: "Credits" } as const)[company.budgetUnit] : "…";

  return (
    <div className="flex min-h-screen bg-background">
      {/* Sidebar (desktop) */}
      <aside className="hidden w-60 shrink-0 flex-col border-r border-border bg-background md:flex">
        <div className="flex h-14 items-center gap-2.5 border-b border-border px-4">
          <Link href="/" aria-label="About AI Spend Planner" className="rounded-md outline-none focus-visible:ring-4 focus-visible:ring-ring"><BrandMark /></Link>
          <div className="min-w-0 leading-tight">
            <div className="truncate text-[15px] font-medium text-foreground">AI Spend Planner</div>
            <div className="truncate text-xs text-muted-foreground">{company?.name ?? "Loading…"}</div>
          </div>
        </div>

        <nav className="flex-1 px-2" aria-label="Primary">
          <div className="eyebrow mt-6 mb-2 px-3">Workspace</div>
          <div className="space-y-px">
            {nav.map(({ href, label, icon: Icon }) => {
              const active = isActive(pathname, href);
              return (
                <Link
                  key={href}
                  href={href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "group flex h-9 items-center gap-2.5 rounded-md px-3 text-sm text-muted-foreground transition-colors duration-300",
                    "hover:bg-popover hover:text-foreground focus-visible:ring-4 focus-visible:ring-ring focus-visible:outline-none",
                    active && "bg-popover text-foreground shadow-[inset_2px_0_0_var(--brand)]",
                  )}
                >
                  <Icon strokeWidth={1.5} className={cn("size-4 shrink-0 text-muted-foreground transition-colors duration-300 group-hover:text-foreground", active && "text-foreground")} />
                  {label}
                </Link>
              );
            })}
          </div>
        </nav>

        <div className="space-y-3 border-t border-border p-4">
          <div className="flex items-center justify-between gap-2">
            <span className="num truncate text-xs text-muted-foreground">{company?.currentPeriod.label ?? "—"}</span>
            {company?.isDemo && <Badge className="h-5 px-1.5 text-[11px]">Demo</Badge>}
          </div>
          <Link
            href="/"
            className="flex h-7 items-center gap-1.5 rounded-md text-xs text-muted-foreground transition-colors duration-300 hover:text-foreground"
          >
            <ArrowUpLeft aria-hidden strokeWidth={1.5} className="size-3.5" /> About AI Spend Planner
          </Link>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Header */}
        <header className="flex h-14 shrink-0 items-center justify-between gap-4 border-b border-border px-4 md:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <Link href="/" aria-label="About AI Spend Planner" className="rounded-md outline-none focus-visible:ring-4 focus-visible:ring-ring md:hidden"><BrandMark /></Link>
            <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-1.5 text-sm text-muted-foreground">
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
        </header>

        {/* Mobile nav */}
        <nav className="flex items-center gap-1 overflow-x-auto border-b border-border px-2 py-1.5 md:hidden" aria-label="Primary">
          {nav.map(({ href, label, icon: Icon }) => {
            const active = isActive(pathname, href);
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex h-9 shrink-0 items-center gap-2 rounded-md px-3 text-sm whitespace-nowrap text-muted-foreground transition-colors duration-300 hover:bg-popover hover:text-foreground",
                  active && "bg-popover text-foreground shadow-[inset_2px_0_0_var(--brand)]",
                )}
              >
                <Icon strokeWidth={1.5} className="size-4" /> {label}
              </Link>
            );
          })}
          {company?.isDemo && <Badge className="ml-auto h-5 shrink-0 px-1.5 text-[11px]">Demo</Badge>}
        </nav>

        <main className="flex-1 overflow-auto">{children}</main>
      </div>

      <AssistantDrawer />
    </div>
  );
}
