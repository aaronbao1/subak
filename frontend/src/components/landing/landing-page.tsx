import Link from "next/link";
import { ArrowLeftRight, FileSearch, Receipt } from "lucide-react";
import { BrandMark } from "@/components/shell/brand-mark";
import { TopBar } from "./top-bar";
import { FeatureSection } from "./feature-section";
import { KineticDots } from "./kinetic-dots";
import { HeroMock, ReceiptMock, TeamListMock } from "./mocks";
import { container, cta } from "./cta";

/* The hero line is repeated verbatim in the closing band. 5 words, two declaratives, sentence case. */
const HEADLINE = "See the spend. Decide faster.";

const FEATURES = [
  {
    id: "how-it-works",
    eyebrow: "Company view",
    heading: "One number for the company",
    body: "Spent, projected and allotted on one bar.",
    href: "/overview",
    mediaSrc: "/media/overview.mp4",
    mediaAlt: "Overview: company spend against total allocation",
    mediaSide: "right",
    placeholder: <HeroMock compact />,
  },
  {
    id: "team-breakdown",
    eyebrow: "Team detail",
    heading: "Click a team, see the breakdown",
    body: "Open a team to see its costs and its people.",
    href: "/teams",
    mediaSrc: "/media/team-breakdown.mp4",
    mediaAlt: "Team breakdown: cost components, provenance, people",
    mediaSide: "left",
    placeholder: <TeamListMock />,
  },
  {
    id: "decisions",
    eyebrow: "Decisions",
    heading: "Reallocate with receipts",
    body: "Review a proposal, apply it, keep the receipt.",
    href: "/decisions",
    mediaSrc: "/media/reallocate.mp4",
    mediaAlt: "Reallocate: proposal review, apply, and the decision log",
    mediaSide: "right",
    placeholder: <ReceiptMock />,
  },
] as const;

/* The three product rules, as one quiet row. The mocks above show each in context. */
const RULES = [
  { icon: ArrowLeftRight, label: "Add budget is never redistribute" },
  { icon: FileSearch, label: "Provenance on every amount" },
  { icon: Receipt, label: "A receipt for every decision" },
] as const;

const FOOTER_LINKS = [
  { label: "Overview", href: "/overview" },
  { label: "Teams", href: "/teams" },
  { label: "Decisions", href: "/decisions" },
] as const;

export function LandingPage() {
  return (
    <>
      <TopBar />
      <main className="flex-1">
        {/* Hero, on a dot grid that leans toward the pointer and fades out before the first feature. */}
        <section className="relative">
          <KineticDots className="absolute inset-0 size-full" />
          <div className={`${container} relative pt-32 pb-12 text-center md:pt-40 md:pb-20`}>
          <p className="eyebrow">AI spend planning for finance</p>
          <h1 className="mx-auto mt-4 max-w-[1050px] text-[40px] leading-none md:text-5xl lg:text-[64px]">{HEADLINE}</h1>
          <p className="mx-auto mt-5 max-w-[560px] text-[17px] leading-[1.35] text-muted-foreground md:text-lg">
            AI spend by team, projected, with receipts.
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <Link href="/overview" className={cta("brand", "hero")}>
              Open dashboard
            </Link>
            <Link href="#how-it-works" className={cta("ghost", "hero")}>
              See how it works
            </Link>
          </div>

          {/* Product frame: a static mock of the overview hero, cropped by a fade into the page. */}
          <div className="relative mx-auto mt-10 max-w-[1050px] md:mt-14">
            <div className="overflow-hidden rounded-xl border border-border bg-card text-left">
              <div className="flex h-10 items-center justify-between border-b border-border px-4">
                <span className="eyebrow">Overview</span>
              </div>
              <HeroMock />
            </div>
            <div
              aria-hidden
              className="pointer-events-none absolute inset-x-0 bottom-0 h-[120px] rounded-b-xl bg-linear-to-b from-transparent to-background"
            />
          </div>
          </div>
        </section>

        {FEATURES.map((f) => (
          <FeatureSection key={f.id} {...f} />
        ))}

        {/* The rules, as three label + icon items; the mocks above already show each one. */}
        <section className="py-12 md:py-16" aria-label="Planning rules">
          <ul className={`${container} grid gap-4 border-t border-border pt-12 sm:grid-cols-3 md:pt-16`}>
            {RULES.map((r) => (
              <li key={r.label} className="flex items-center gap-3 text-sm text-muted-foreground">
                <r.icon className="size-4 shrink-0" strokeWidth={1.5} aria-hidden />
                {r.label}
              </li>
            ))}
          </ul>
        </section>

        {/* Closing CTA repeats the hero line verbatim */}
        <section className={`${container} py-20 md:py-28`}>
          <div className="rounded-2xl border border-border bg-card px-6 py-16 text-center md:py-20">
            <h2 className="mx-auto max-w-[760px] text-[34px] leading-[1.05] md:text-5xl">{HEADLINE}</h2>
            <div className="mt-8 flex justify-center">
              <Link href="/overview" className={cta("brand", "hero")}>
                Open dashboard
              </Link>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-border py-6">
        <div className={`${container} flex flex-wrap items-center justify-between gap-4 text-xs text-muted-foreground md:text-[13px]`}>
          <span className="flex items-center gap-2.5 text-foreground">
            <BrandMark />
            <span className="text-sm font-medium">AI Spend Planner</span>
          </span>
          <nav aria-label="Footer" className="flex gap-5">
            {FOOTER_LINKS.map((l) => (
              <Link key={l.href} href={l.href} className="transition-colors duration-300 hover:text-foreground">
                {l.label}
              </Link>
            ))}
          </nav>
        </div>
      </footer>
    </>
  );
}
