"use client";
import { useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface MediaSlotProps {
  /** Product video, e.g. /media/overview.mp4. Rendered over the placeholder; a missing file fails silently. */
  src?: string;
  poster?: string;
  alt: string;
  /** Quiet JSX mock shown until (or instead of) the video. Falls back to the alt text. */
  placeholder?: ReactNode;
  className?: string;
}

/**
 * 16:9 product frame for the landing page: 1px border, card surface, no shadow or ring.
 * The placeholder always renders underneath; when a video is given it sits on top and simply
 * disappears if the browser cannot load it, so dropping a file into public/media is all that is needed.
 */
export function MediaSlot({ src, poster, alt, placeholder, className }: MediaSlotProps) {
  const [failed, setFailed] = useState(false);
  const showVideo = Boolean(src) && !failed;

  return (
    <div
      className={cn("relative aspect-video w-full overflow-hidden rounded-xl border border-border bg-card", className)}
      role={showVideo ? undefined : "img"}
      aria-label={showVideo ? undefined : alt}
    >
      <div className="absolute inset-0" aria-hidden>
        {placeholder ?? <Fallback alt={alt} />}
      </div>
      {showVideo && (
        <video
          className="absolute inset-0 size-full object-cover"
          src={src}
          poster={poster}
          autoPlay
          muted
          loop
          playsInline
          preload="metadata"
          aria-label={alt}
          onError={() => setFailed(true)}
        />
      )}
    </div>
  );
}

function Fallback({ alt }: { alt: string }) {
  return (
    <div className="flex size-full items-end p-4">
      <span className="text-xs text-muted-foreground">{alt}</span>
    </div>
  );
}
