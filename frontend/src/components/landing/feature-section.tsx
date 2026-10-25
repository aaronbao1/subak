import Link from "next/link";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { MediaSlot } from "./media-slot";
import { container, textLink } from "./cta";

export interface FeatureSectionProps {
  id?: string;
  eyebrow: string;
  heading: string;
  body: string;
  /** Where "See it in the dashboard" goes. */
  href: string;
  mediaSrc: string;
  mediaAlt: string;
  /** Quiet JSX mock rendered inside the frame until the video loads. */
  placeholder?: ReactNode;
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
  placeholder,
  mediaSide = "right",
}: FeatureSectionProps) {
  const headingId = id ? `${id}-heading` : undefined;
  return (
    <section id={id} className="scroll-mt-20 py-12 md:py-20" aria-labelledby={headingId}>
      <div className={cn(container, "grid items-center gap-8 lg:grid-cols-2 lg:gap-16")}>
        <div className={cn(mediaSide === "left" && "lg:order-2")}>
          <p className="eyebrow">{eyebrow}</p>
          <h2 id={headingId} className="mt-3 max-w-[520px] text-[28px] leading-[1.1] md:text-[32px] lg:text-[40px]">
            {heading}
          </h2>
          <p className="mt-4 max-w-[480px] text-[15px] leading-[1.4] text-muted-foreground md:text-base">{body}</p>
          <Link href={href} className={cn(textLink, "mt-6")}>
            See it in the dashboard <span aria-hidden>→</span>
          </Link>
        </div>
        <MediaSlot src={mediaSrc} alt={mediaAlt} placeholder={placeholder} className={cn(mediaSide === "left" && "lg:order-1")} />
      </div>
    </section>
  );
}
