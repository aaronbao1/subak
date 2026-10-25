"use client";
import { Fragment, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Users, FileSearch, History, MessageSquare, CalendarDays, Activity, Building2, ChevronRight, RefreshCw, Inbox } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAppStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import { AssistantDrawer } from "@/components/assistant/assistant-drawer";
import { BrandMark } from "@/components/shell/brand-mark";

const nav = [
  { href: "/overview", label: "Overview", icon: LayoutDashboard },
  { href: "/teams", label: "Teams", icon: Users },
  { href: "/requests", label: "Team requests", icon: Inbox },
  { href: "/usage", label: "Usage activity", icon: Activity },
  { href: "/planning", label: "Planning", icon: CalendarDays },
  { href: "/evidence", label: "Evidence", icon: FileSearch },
  { href: "/decisions", label: "Decisions", icon: History },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { load, loaded, company, teams, people, assistantOpen, setAssistantOpen, loadState, loadError, budgetSync } = useAppStore();
  useEffect(() => { if (!loaded && (!loadState || loadState === "idle")) void load(); }, [loaded, loadState, load]);
  useEffect(() => {
    const ms = Number(process.env.NEXT_PUBLIC_LIVE_REFRESH_MS);
    if (!loaded || !Number.isFinite(ms) || ms <= 0) return;
    const id = window.setInterval(() => { void load(); }, Math.max(2000, ms));
    return () => window.clearInterval(id);
  }, [loaded, load]);
  const parts = pathname.split("/").filter(Boolean);
  const section = nav.find(n => n.href === `/${parts[0]}`);
  const crumbs: { label: string; href?: string }[] = [{ label: section?.label ?? "Workspace", href: section?.href }];
  if (parts[0] === "teams" && parts[1]) {
    crumbs.push({ label: teams.find(t => t.id === parts[1])?.name ?? "Team", href: `/teams/${parts[1]}` });
    if (parts[2] === "people" && parts[3]) crumbs.push({ label: people.find(p => p.id === parts[3])?.name ?? "Person" });
  }
  const unit = company ? ({ usd: "USD", tokens: "Tokens", credits: "Credits" } as const)[company.budgetUnit] : "USD";
  const links = (mobile = false) => nav.map(({ href, label, icon: Icon }) => {
    const active = pathname === href || pathname.startsWith(`${href}/`);
    return <Link key={href} href={href} aria-current={active ? "page" : undefined}
      className={cn("flex shrink-0 items-center gap-2.5 rounded-md border border-transparent text-sm transition-colors hover:bg-sidebar-accent hover:text-foreground", mobile ? "h-10 px-3" : "h-10 px-3", active ? "border-border-strong bg-sidebar-accent font-medium text-foreground" : "text-muted-foreground")}>
      <Icon className={cn("size-4 shrink-0", active && "text-brand")} strokeWidth={1.6} />
      <span className="whitespace-nowrap">{label}</span>
    </Link>;
  });

  return <div className="min-h-screen bg-background lg:pl-56">
    <a href="#main-content" className="fixed left-4 top-3 z-50 -translate-y-20 rounded-md bg-primary px-4 py-2 text-primary-foreground focus:translate-y-0">Skip to content</a>
    <aside className="fixed inset-y-0 left-0 z-40 hidden w-56 flex-col border-r border-sidebar-border bg-sidebar lg:flex">
      <Link href="/" className="flex h-16 items-center gap-3 border-b border-sidebar-border px-5" aria-label="Subak home">
        <BrandMark /><span className="text-lg font-medium tracking-tight">Subak</span>
      </Link>
      <div className="mx-3 my-5 flex items-center gap-2.5 rounded-lg border border-border px-3 py-3">
        <span className="flex size-8 shrink-0 items-center justify-center rounded-md border border-border bg-card"><Building2 className="size-4 text-muted-foreground" strokeWidth={1.5} /></span>
        <div className="min-w-0 truncate text-sm font-medium">{company?.name ?? "Your company"}</div>
      </div>
      <nav aria-label="Primary" className="flex flex-col gap-1 px-3">{links()}</nav>
      <div className="mt-auto p-3">
        <div className="flex items-center gap-2.5 border-t border-border px-2 pt-4 pb-2"><span className="flex size-7 items-center justify-center rounded-full bg-secondary text-[10px] font-medium">FP</span><span className="text-xs font-medium">Finance team</span></div>
      </div>
    </aside>

    <header className="sticky top-0 z-30 border-b border-border bg-background/95 backdrop-blur">
      <div className="flex h-16 items-center gap-3 px-4 sm:px-6 lg:px-8">
        <Link href="/" aria-label="Subak home" className="shrink-0 lg:hidden"><BrandMark /></Link>
        <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-2 text-sm">
          {crumbs.map((crumb, i) => <Fragment key={`${crumb.label}-${i}`}>
            {i > 0 && <ChevronRight aria-hidden className="size-3 shrink-0 text-muted-foreground" />}
            {i === crumbs.length - 1 ? <span aria-current="page" className="truncate">{crumb.label}</span> : <Link className="truncate text-muted-foreground hover:text-foreground" href={crumb.href ?? "/overview"}>{crumb.label}</Link>}
          </Fragment>)}
        </nav>
        <div className="ml-auto flex shrink-0 items-center gap-3">
          <span className="hidden text-xs text-muted-foreground sm:inline">{unit}</span>
          <Button variant={assistantOpen ? "secondary" : "outline"} aria-label="Droid Assistant" aria-pressed={assistantOpen} onClick={() => setAssistantOpen(!assistantOpen)} className="px-3"><MessageSquare className="size-4" strokeWidth={1.5} /><span className="hidden sm:inline">Droid Assistant</span></Button>
        </div>
      </div>
      <nav aria-label="Primary mobile" className="flex gap-1 overflow-x-auto border-t border-border px-3 py-1 lg:hidden">{links(true)}</nav>
    </header>

    {(loadState === "error" || loadState === "stale") && <div role="alert" className="mx-4 mt-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-warning/30 bg-warning/5 px-4 py-3 text-sm sm:mx-6 lg:mx-8"><span>{loaded ? "Showing your last loaded data. " : "Unable to load this workspace. "}{loadError}</span><Button variant="outline" size="sm" onClick={() => void load()}><RefreshCw className="size-3.5" />Retry</Button></div>}
    {budgetSync === "stale" && <div role="status" className="mx-4 mt-4 rounded-lg border border-warning/30 px-4 py-3 text-sm sm:mx-6 lg:mx-8">Your change was saved. Budget totals are waiting to refresh.</div>}
    <main id="main-content" tabIndex={-1} className="min-w-0 outline-none">{children}</main>
    <AssistantDrawer />
  </div>;
}
