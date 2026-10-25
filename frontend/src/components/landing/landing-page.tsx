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
    body:
      "Spent to date, projected for the period, and the total allotted on one line. When the projection passes the allotment, the bar shows how far over, in the unit you budget in.",
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
    body:
      "Every line on the spend chart is a team. Open one to see its cost components, where each amount came from, and the people behind the number, without leaving the overview.",
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
    body:
      "Ask the assistant, review a proposal, and apply it. Every decision lands in a log with what changed, who applied it, and the projection that was on screen when it was reviewed.",
    href: "/decisions",
    mediaSrc: "/media/reallocate.mp4",
    mediaAlt: "Reallocate: proposal review, apply, and the decision log",
    mediaSide: "right",
    placeholder: <ReceiptMock />,
  },
] as const;

const RULES = [
  {
    icon: ArrowLeftRight,
    title: "Add budget is never redistribute",
    body:
      "Every proposal says which one it is before you apply it. Redistribute keeps the company total constant; adding budget raises it.",
  },
  {
    icon: FileSearch,
    title: "Provenance on every amount",
    body:
      "Reported charge, estimate, or usage only: each figure says how it was arrived at, and days with incomplete data are marked, not smoothed over.",
    href: "/evidence",
  },
  {
    icon: Receipt,
    title: "Receipts for every decision",
    body:
      "Applied decisions land in a log with what changed, when, why, and who, alongside the projection that was reviewed at the time.",
  },
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
            Daily AI spend, projections and allocations by team, with an assistant that proposes reallocations and leaves
            a receipt.
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

        {/* Feature C: the rules the UI keeps visible */}
        <section className="py-12 md:py-20" aria-labelledby="rules-heading">
          <div className={container}>
            <p className="eyebrow">Planning rules</p>
            <h2 id="rules-heading" className="mt-3 max-w-[640px] text-[28px] leading-[1.1] md:text-[32px] lg:text-[40px]">
              Planning records, kept honest
            </h2>
            <div className="mt-10 grid gap-6 md:grid-cols-3">
              {RULES.map((r) => (
                <article
                  key={r.title}
                  className="rounded-xl border border-border bg-card p-6 transition-colors duration-300 hover:border-border-strong"
                >
                  <div className="flex size-10 items-center justify-center rounded-lg border border-border">
                    <r.icon className="size-4 text-muted-foreground" strokeWidth={1.5} aria-hidden />
                  </div>
                  <h3 className="mt-5 text-[22px] leading-[1.15]">
                    {"href" in r ? (
                      <Link href={r.href} className="underline underline-offset-4 decoration-border-strong transition-colors duration-300 hover:decoration-foreground">
                        {r.title}
                      </Link>
                    ) : (
                      r.title
                    )}
                  </h3>
                  <p className="mt-3 text-sm leading-5 text-muted-foreground">{r.body}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        {/* Closing CTA repeats the hero line verbatim */}
        <section className={`${container} py-20 md:py-28`}>
          <div className="rounded-2xl border border-border bg-card px-6 py-16 text-center md:py-20">
            <h2 className="mx-auto max-w-[760px] text-[34px] leading-[1.05] md:text-5xl">{HEADLINE}</h2>
            <p className="mx-auto mt-4 max-w-[480px] text-[15px] text-muted-foreground md:text-base">
              Open the dashboard: one period, a shared allotment, and an assistant ready to propose a change.
            </p>
            <div className="mt-8 flex justify-center">
              <Link href="/overview" className={cta("brand", "hero")}>
                Open dashboard
              </Link>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-border py-12">
        <div className={`${container} flex flex-col gap-8 text-xs text-muted-foreground md:flex-row md:items-start md:justify-between md:text-[13px]`}>
          <div className="max-w-[420px]">
            <div className="flex items-center gap-2.5 text-foreground">
              <BrandMark />
              <span className="text-sm font-medium">AI Spend Planner</span>
            </div>
            <p className="mt-3 leading-[1.5]">Planning records, not provider limits or purchases.</p>
          </div>
          <nav aria-label="Footer" className="flex flex-col gap-2.5">
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
