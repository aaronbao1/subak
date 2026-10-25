"use client";
import Image from "next/image";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { Pause, Play } from "lucide-react";
import { cn } from "@/lib/utils";

export interface MediaSlotProps {
  src: string;
  poster: string;
  alt: string;
  className?: string;
  priority?: boolean;
}

function subscribeToReducedMotion(callback: () => void) {
  const query = window.matchMedia("(prefers-reduced-motion: reduce)");
  query.addEventListener("change", callback);
  return () => query.removeEventListener("change", callback);
}

const prefersReducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const serverReducedMotion = () => true;

/** Current product captures, with the same screen visible before playback and on failure. */
export function MediaSlot({ src, poster, alt, className, priority = false }: MediaSlotProps) {
  const frame = useRef<HTMLDivElement>(null);
  const video = useRef<HTMLVideoElement>(null);
  const [visible, setVisible] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState(false);
  const [paused, setPaused] = useState(false);
  const reducedMotion = useSyncExternalStore(subscribeToReducedMotion, prefersReducedMotion, serverReducedMotion);
  const shouldPlay = visible && !paused && !reducedMotion;

  useEffect(() => {
    const element = frame.current;
    if (!element) return;
    const observer = new IntersectionObserver(([entry]) => setVisible(entry.isIntersecting), { threshold: 0.15 });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const element = video.current;
    if (!element) return;
    let active = true;
    if (shouldPlay) {
      void element.play().catch(() => { if (active) setPaused(true); });
    } else {
      element.pause();
    }
    return () => { active = false; };
  }, [shouldPlay, loaded]);

  return (
    <div ref={frame} className={cn("relative aspect-[8/5] w-full overflow-hidden rounded-xl border border-border bg-white", className)}>
      <Image src={poster} alt={alt} fill sizes={priority ? "(min-width: 1200px) 1050px, 100vw" : "(min-width: 1440px) 624px, (min-width: 1024px) 45vw, 100vw"} preload={priority} className="object-contain" />
      {!failed && !reducedMotion && (visible || loaded) && (
        <video
          ref={video}
          className={cn("absolute inset-0 size-full object-contain transition-opacity", loaded ? "opacity-100" : "opacity-0")}
          src={src}
          poster={poster}
          muted
          loop
          playsInline
          preload="metadata"
          aria-hidden="true"
          onLoadedData={() => setLoaded(true)}
          onError={() => setFailed(true)}
        />
      )}
      {!failed && !reducedMotion && loaded && (
        <button
          type="button"
          onClick={() => setPaused(value => !value)}
          aria-label={paused ? "Play demo" : "Pause demo"}
          className="absolute right-3 bottom-3 flex size-8 items-center justify-center rounded-full border border-black/10 bg-white/95 text-gray-800 shadow-sm transition-colors hover:bg-gray-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-600"
        >
          {paused ? <Play aria-hidden className="size-3.5" /> : <Pause aria-hidden className="size-3.5" />}
        </button>
      )}
    </div>
  );
}
