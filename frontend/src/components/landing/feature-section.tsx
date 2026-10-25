import { cn } from "@/lib/utils";
import { ArrowLink } from "./arrow-link";
import { MediaSlot } from "./media-slot";
import { Reveal } from "./reveal";
import { container } from "./cta";

export interface FeatureSectionProps {
  id?: string;
  eyebrow: string;
  heading: string;
  body: string;
  /** Where "See it in the dashboard" goes. */
  href: string;
  mediaSrc: string;
  mediaAlt: string;
  mediaPoster: string;
  /** Media on the right (default) or on the left at lg and up. Stacks text-first on phones either way. */
  mediaSide?: "right" | "left";
}

export function FeatureSection({
  id,
  eyebrow,
  heading,
  body,
  href,
  mediaSrc,
  mediaAlt,
  mediaPoster,
  mediaSide = "right",
}: FeatureSectionProps) {
  const headingId = id ? `${id}-heading` : undefined;
  return (
    <section id={id} className="scroll-mt-20 py-12 md:py-20" aria-labelledby={headingId}>
      {/* Reveal each feature when it enters the viewport. */}
      <Reveal className={cn(container, "grid items-center gap-8 lg:grid-cols-2 lg:gap-16")}>
        <div className={cn(mediaSide === "left" && "lg:order-2")}>
          <p className="eyebrow">{eyebrow}</p>
          <h2 id={headingId} className="mt-3 max-w-[520px] text-[28px] leading-[1.1] md:text-[32px] lg:text-[40px]">
            {heading}
          </h2>
          <p className="mt-4 max-w-[480px] text-[15px] leading-[1.4] text-muted-foreground md:text-base">{body}</p>
          <ArrowLink href={href} className="mt-6">
            See it in the dashboard
          </ArrowLink>
        </div>
        <MediaSlot src={mediaSrc} poster={mediaPoster} alt={mediaAlt} className={cn(mediaSide === "left" && "lg:order-1")} />
      </Reveal>
    </section>
  );
}
