import Link from "next/link";
import { ArrowLeftRight, FileSearch, Receipt } from "lucide-react";
import { BrandMark } from "@/components/shell/brand-mark";
import { TopBar } from "./top-bar";
import { FeatureSection } from "./feature-section";
import { MediaSlot } from "./media-slot";
import { KineticDots } from "./kinetic-dots";
import { container, cta } from "./cta";

/* The hero line is repeated verbatim in the closing band. 5 words, two declaratives, sentence case. */
const HEADLINE = "See the spend. Decide faster.";

const FEATURES = [
  {
    id: "how-it-works",
    eyebrow: "Company outlook",
    heading: "See this week. Plan the next.",
    body: "Compare recorded spend with the forecast, review each week, and see how much room is left in the company budget.",
    href: "/overview",
    mediaSrc: "/media/overview.webm",
    mediaPoster: "/media/overview.webp",
    mediaAlt: "Current Overview with company budget, recorded and expected spend, weekly forecasts, and team allocations",
    mediaSide: "right",
  },
  {
    id: "team-breakdown",
    eyebrow: "Team spending",
    heading: "Follow the forecast into every team",
    body: "Compare allocations and expected spend, then open a team to explore its spending outlook, people, and the plans behind the numbers.",
    href: "/teams",
    mediaSrc: "/media/team-breakdown.webm",
    mediaPoster: "/media/team-breakdown.webp",
    mediaAlt: "Teams comparison and team spending outlook with expected spend and allocation details",
    mediaSide: "left",
  },
  {
    id: "team-requests",
    eyebrow: "Team requests",
    heading: "Bring the team's plans into the review",
    body: "Review project updates and funding requests alongside each team's budget position, supporting evidence, and finance discussion.",
    href: "/requests",
    mediaSrc: "/media/requests.webm",
    mediaPoster: "/media/requests.webp",
    mediaAlt: "Team requests inbox and a project update with team budget position and supporting context",
    mediaSide: "right",
  },
  {
    id: "usage-activity",
    eyebrow: "Usage activity",
    heading: "Trace spend to the day and model",
    body: "Switch between spend and tokens, filter by team or provider, and open a day to inspect the models and people behind the activity.",
    href: "/usage",
    mediaSrc: "/media/usage.webm",
    mediaPoster: "/media/usage.webp",
    mediaAlt: "Usage activity with spend and token views, daily activity calendar, and model breakdown",
    mediaSide: "left",
  },
  {
    id: "evidence",
    eyebrow: "Evidence",
    heading: "Keep the source within reach",
    body: "Find the documents behind a team's plans, inspect source details, and review assessments and forecast changes in the same workspace.",
    href: "/evidence",
    mediaSrc: "/media/evidence.webm",
    mediaPoster: "/media/evidence.webp",
    mediaAlt: "Evidence workspace with source documents, filters, and an open source detail",
    mediaSide: "right",
  },
  {
    id: "decisions",
    eyebrow: "Allocations and decisions",
    heading: "Reallocate with receipts",
    body: "Adjust team allocations, review the impact on the company budget, and apply the change with a reason and a saved decision record.",
    href: "/decisions",
    mediaSrc: "/media/reallocate.webm",
    mediaPoster: "/media/reallocate.webp",
    mediaAlt: "Allocation workbench with a reviewed budget change and its saved decision receipt",
    mediaSide: "left",
  },
] as const;

const RULES = [
  { icon: ArrowLeftRight, label: "Separate funding from redistribution" },
  { icon: FileSearch, label: "Evidence behind the forecast" },
  { icon: Receipt, label: "A receipt for every decision" },
] as const;

const FOOTER_LINKS = [
  { label: "Overview", href: "/overview" },
  { label: "Teams", href: "/teams" },
  { label: "Team requests", href: "/requests" },
  { label: "Usage", href: "/usage" },
  { label: "Planning", href: "/planning" },
  { label: "Evidence", href: "/evidence" },
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
          <div className={`${container} relative pt-20 pb-12 text-center md:pt-28 md:pb-20`}>
            <p className="eyebrow">AI spend planning for finance</p>
            <h1 className="mx-auto mt-4 max-w-[1050px] text-[40px] leading-none md:text-5xl lg:text-[64px]">{HEADLINE}</h1>
            <p className="mx-auto mt-5 max-w-[560px] text-[17px] leading-[1.35] text-muted-foreground md:text-lg">
              AI spend, weekly forecasts, and team budgets in one workspace.
            </p>
            <div className="mt-8 flex flex-wrap justify-center gap-3">
              <Link href="/overview" className={cta("brand", "hero")}>
                Open dashboard
              </Link>
              <Link href="#how-it-works" className={cta("ghost", "hero")}>
                See how it works
              </Link>
            </div>

            {/* Real product recording and a matching still from the current demo workspace. */}
            <div className="relative mx-auto mt-10 max-w-[1050px] md:mt-14">
              <div className="overflow-hidden rounded-xl border border-border bg-card text-left">
                <div className="flex h-10 items-center justify-between border-b border-border px-4">
                  <span className="eyebrow">Overview</span>
                  <span className="text-xs text-muted-foreground">Demo workspace</span>
                </div>
                <MediaSlot
                  src="/media/hero.webm"
                  poster="/media/hero.webp"
                  alt="Subak Overview: company outlook, weekly actual and forecast spending, team allocations, and requests"
                  priority
                  className="rounded-none border-0"
                />
              </div>
            </div>
          </div>
        </section>

        {FEATURES.map((f) => (
          <FeatureSection key={f.id} {...f} />
        ))}

        {/* Shared principles across the planning workflow. */}
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
            <span className="text-sm font-medium">Subak</span>
          </span>
          <nav aria-label="Footer" className="flex flex-wrap gap-x-5 gap-y-3">
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
