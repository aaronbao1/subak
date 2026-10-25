"use client";
import { createContext, useContext, useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { cn } from "@/lib/utils";

/*
 * Scroll entrance for the landing page. The wrapper fades up once (the global `animate-rise` keyframe) the
 * first time 20% of it is in view, then stops observing. Children can read `useRevealed()` to start their own
 * motion (count-ups, bar growth, row stagger) at the same moment. Outside a <Reveal>, `useRevealed()` is true,
 * so the same mocks animate on mount in the hero. Server components stay server components: only this wrapper
 * and the mocks are client code.
 */
const RevealContext = createContext(true);

/** True once the nearest <Reveal> has entered the viewport (always true outside one). */
export function useRevealed(): boolean {
  return useContext(RevealContext);
}

export interface RevealProps {
  children: ReactNode;
  /** Extra animation delay in ms, for staggering siblings (60ms steps). */
  delay?: number;
  className?: string;
  as?: "div" | "article";
}

export function Reveal({ children, delay = 0, className, as = "div" }: RevealProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [revealed, setRevealed] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (typeof IntersectionObserver === "undefined") {
      const raf = requestAnimationFrame(() => setRevealed(true));
      return () => cancelAnimationFrame(raf);
    }
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setRevealed(true);
          io.disconnect();
        }
      },
      { threshold: 0.2 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  const Tag = as as "div";
  return (
    <RevealContext.Provider value={revealed}>
      <Tag
        ref={ref}
        className={cn(revealed ? "animate-rise" : "opacity-0", className)}
        style={{ "--rise-delay": `${delay}ms` } as CSSProperties}
      >
        {children}
      </Tag>
    </RevealContext.Provider>
  );
}
