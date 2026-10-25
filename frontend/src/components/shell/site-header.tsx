"use client";
import type { ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Users, FileSearch, History, Activity, Inbox, CalendarDays } from "lucide-react";
import { cn } from "@/lib/utils";
import { BrandMark } from "@/components/shell/brand-mark";

/** The product sections, in nav order. Shared by the header tabs and the app's breadcrumb. */
export const SECTIONS = [
  { href: "/overview", label: "Overview", icon: LayoutDashboard },
  { href: "/teams", label: "Teams", icon: Users },
  { href: "/usage", label: "Usage", icon: Activity },
  { href: "/requests", label: "Requests", icon: Inbox },
  { href: "/planning", label: "Planning", icon: CalendarDays },
  { href: "/evidence", label: "Evidence", icon: FileSearch },
  { href: "/decisions", label: "Decisions", icon: History },
] as const;

export function isActive(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(`${href}/`);
}

/**
 * The one header, on the landing page and in the product: brand, the product sections as tabs with the brand
 * rule under the active one, and a right-hand slot. The landing passes "Open dashboard"; the app passes the unit
 * badge and the assistant. The tabs share the top row from lg (1024px) up, with icons from xl; below lg they
 * drop to a second scrolling row.
 */
export function SiteHeader({ actions }: { actions?: ReactNode }) {
  const pathname = usePathname();

  const tabs = (className: string) => (
    <nav className={cn("col-start-2", className)} aria-label="Primary">
      {SECTIONS.map(({ href, label, icon: Icon }) => {
        const active = isActive(pathname, href);
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "group relative flex h-14 shrink-0 items-center gap-2 px-2.5 text-sm whitespace-nowrap text-muted-foreground transition-colors duration-300 xl:px-3",
              "hover:text-foreground focus-visible:ring-4 focus-visible:ring-ring focus-visible:outline-none",
              active && "text-foreground",
            )}
          >
            {/* Icons only once the row has room for seven labelled tabs. */}
            <Icon strokeWidth={1.5} className={cn("hidden size-4 shrink-0 text-muted-foreground transition-colors duration-300 group-hover:text-foreground xl:block", active && "text-foreground")} />
            {label}
            {/* Active rule in the budgeted accent, sitting on the header's bottom border. */}
            <span aria-hidden className={cn("absolute inset-x-2.5 -bottom-px h-0.5 rounded-full bg-brand opacity-0 transition-opacity duration-300 xl:inset-x-3", active && "opacity-100")} />
          </Link>
        );
      })}
    </nav>
  );

  return (
    <header className="sticky top-0 z-30 border-b border-border/70 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
      {/* One row from lg up: three columns so the tabs sit on the page's center line whatever the brand and actions measure. */}
      <div className="grid h-14 grid-cols-[1fr_auto] items-center gap-4 px-4 md:px-6 lg:grid-cols-[1fr_auto_1fr]">
        <Link href="/" aria-label="About Subak" className="flex min-w-0 items-center gap-2.5 justify-self-start rounded-md outline-none focus-visible:ring-4 focus-visible:ring-ring">
          <BrandMark />
          <span className="truncate text-[15px] font-medium text-foreground">Subak</span>
        </Link>

        {tabs("hidden h-14 items-center lg:flex")}

        <div className="flex min-w-0 items-center gap-2 justify-self-end sm:gap-3">{actions}</div>
      </div>

      {/* Below lg the tabs scroll in their own row under the brand. */}
      <div className="border-t border-border/70 lg:hidden">
        {tabs("flex items-center overflow-x-auto px-1")}
      </div>
    </header>
  );
}
