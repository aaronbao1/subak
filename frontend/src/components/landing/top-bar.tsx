import Link from "next/link";
import { BrandMark } from "@/components/shell/brand-mark";
import { container, cta } from "./cta";

const LINKS = [
  { label: "Overview", href: "/overview" },
  { label: "Teams", href: "/teams" },
  { label: "Evidence", href: "/evidence" },
  { label: "Decisions", href: "/decisions" },
] as const;

/**
 * Fixed 56px marketing header. Wordmark left, section links in the middle at lg, actions right.
 * The nav primary is the ink-filled secondary so the hero's brand CTA stays the only accent-filled element in view.
 */
export function TopBar() {
  return (
    <header className="fixed inset-x-0 top-0 z-50 h-14 border-b border-border/70 bg-background/85 backdrop-blur-md">
      <div className={`${container} flex h-full items-center justify-between gap-4`}>
        <Link href="/" className="flex items-center gap-2.5 rounded-md outline-none focus-visible:ring-3 focus-visible:ring-ring/50">
          <BrandMark />
          <span className="text-[15px] font-medium">Subak</span>
        </Link>

        <nav aria-label="Sections" className="hidden items-center gap-x-6 lg:flex">
          {LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className="text-sm text-muted-foreground transition-colors duration-300 hover:text-foreground"
            >
              {l.label}
            </Link>
          ))}
        </nav>

        <div className="flex items-center">
          <Link href="/overview" className={cta("secondary", "nav")}>
            Open dashboard
          </Link>
        </div>
      </div>
    </header>
  );
}
