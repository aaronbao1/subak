"use client";
import type { ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Users, FileSearch, History } from "lucide-react";
import { cn } from "@/lib/utils";
import { BrandMark } from "@/components/shell/brand-mark";

/** The four product sections, in nav order. Shared by the header tabs and the app's breadcrumb. */
export const SECTIONS = [
  { href: "/overview", label: "Overview", icon: LayoutDashboard },
  { href: "/teams", label: "Teams", icon: Users },
  { href: "/evidence", label: "Evidence", icon: FileSearch },
  { href: "/decisions", label: "Decisions", icon: History },
] as const;

export function isActive(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(`${href}/`);
}

/**
 * The one header, on the landing page and in the product: brand, the four sections as tabs with the brand
 * rule under the active one, and a right-hand slot. The landing passes "Open dashboard"; the app passes the
 * unit badge and the assistant. On narrow screens the tabs drop to a second scrolling row.
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
    <header className="sticky top-0 z-30 border-b border-border/70 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
      {/* Three columns so the tabs sit on the page's center line whatever the brand and actions measure. */}
      <div className="grid h-14 grid-cols-[1fr_auto_1fr] items-center gap-4 px-4 md:px-6">
        <Link href="/" aria-label="About Subak" className="flex min-w-0 items-center gap-2.5 justify-self-start rounded-md outline-none focus-visible:ring-4 focus-visible:ring-ring">
          <BrandMark />
          <span className="truncate text-[15px] font-medium text-foreground">Subak</span>
        </Link>

        {tabs("hidden h-14 items-center md:flex")}

        <div className="flex min-w-0 items-center gap-2 justify-self-end sm:gap-3">{actions}</div>
      </div>

      {/* Narrow screens: tabs scroll in their own row. */}
      <div className="border-t border-border/70 md:hidden">
        {tabs("flex items-center overflow-x-auto px-1")}
      </div>
    </header>
  );
}
