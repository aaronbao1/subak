"use client";
import { useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Users, History, MessageSquare } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useAppStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import { AssistantDrawer } from "@/components/assistant/assistant-drawer";

const nav = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/teams", label: "Teams", icon: Users },
  { href: "/decisions", label: "Decisions", icon: History },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { load, loaded, company, assistantOpen, setAssistantOpen } = useAppStore();
  useEffect(() => { if (!loaded) void load(); }, [loaded, load]);

  return (
    <div className="flex min-h-screen">
      <aside className="w-56 shrink-0 border-r bg-sidebar text-sidebar-foreground flex flex-col">
        <div className="px-4 py-4 border-b">
          <div className="font-semibold tracking-tight">AI Spend Planner</div>
          <div className="text-xs text-muted-foreground mt-0.5 flex items-center gap-1.5">
            {company?.name ?? "Loading…"}
            {company?.isDemo && <Badge variant="outline" className="text-[10px] px-1 py-0">demo</Badge>}
          </div>
        </div>
        <nav className="flex-1 p-2 space-y-0.5">
          {nav.map(({ href, label, icon: Icon }) => {
            const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <Link key={href} href={href}
                className={cn("flex items-center gap-2 rounded-md px-3 py-2 text-sm hover:bg-sidebar-accent",
                  active && "bg-sidebar-accent font-medium")}>
                <Icon className="size-4" /> {label}
              </Link>
            );
          })}
        </nav>
        <div className="p-2 border-t text-xs text-muted-foreground px-4 py-3">
          {company?.currentPeriod.label}
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-14 border-b flex items-center justify-between px-6">
          <div className="text-sm text-muted-foreground">Internal budgets in <span className="font-medium text-foreground">credits</span>. Planning numbers, not provider limits.</div>
          <Button variant={assistantOpen ? "secondary" : "default"} size="sm" onClick={() => setAssistantOpen(!assistantOpen)}>
            <MessageSquare className="size-4" /> Assistant
          </Button>
        </header>
        <main className="flex-1 p-6 overflow-auto">{children}</main>
      </div>

      <AssistantDrawer />
    </div>
  );
}
