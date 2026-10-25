"use client";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";

/* ------------------------------------------------------------------ */
/* One motion vocabulary for the app. No dependencies; rAF + CSS.      */
/*   ease:   cubic-bezier(.32,.72,0,1) in CSS, easeOutCubic in JS      */
/*   enter:  cards rise 12px and fade in, 60ms stagger                 */
/*   count:  numbers count up over 900ms                               */
/*   draw:   chart lines/bars grow from the baseline over ~1.1s        */
/* Everything respects prefers-reduced-motion by jumping to the end.  */
/* ------------------------------------------------------------------ */

export const easeOutCubic = (t: number) => 1 - Math.pow(1 - t, 3);
export const EASE_CSS = "cubic-bezier(.32,.72,0,1)";
export const ENTER_STAGGER_MS = 60;

const mq = () => (typeof window === "undefined" ? null : window.matchMedia("(prefers-reduced-motion: reduce)"));
const subscribeReduce = (cb: () => void) => {
  const m = mq();
  m?.addEventListener("change", cb);
  return () => m?.removeEventListener("change", cb);
};
export function usePrefersReducedMotion(): boolean {
  return useSyncExternalStore(subscribeReduce, () => mq()?.matches ?? false, () => false);
}

/**
 * Eased 0..1 progress that runs once per `key` (restart by changing the key).
 * Returns 1 immediately under reduced motion or when disabled.
 */
export function useProgress({ duration = 1100, delay = 0, key = 0, enabled = true }: { duration?: number; delay?: number; key?: string | number; enabled?: boolean } = {}): number {
  const reduce = usePrefersReducedMotion();
  const [p, setP] = useState(0);
  useEffect(() => {
    if (!enabled || reduce) return;
    let raf = 0;
    let start = 0;
    const tick = (now: number) => {
      if (!start) start = now + delay;
      const t = Math.max(0, Math.min(1, (now - start) / duration));
      setP(easeOutCubic(t));
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [key, enabled, reduce, duration, delay]);
  if (!enabled || reduce) return 1;
  return p;
}

/**
 * Counts from `from` (default: the previous target, or 0 on first render) to `target`.
 * Re-runs whenever `target` changes, so applying a proposal ticks the number to its new value.
 */
export function useCountUp(target: number, { duration = 900, delay = 0, from }: { duration?: number; delay?: number; from?: number } = {}): number {
  const reduce = usePrefersReducedMotion();
  const prev = useRef<number | null>(null);
  const [value, setValue] = useState(from ?? 0);
  useEffect(() => {
    if (reduce || !Number.isFinite(target)) { prev.current = target; return; }
    const start = from ?? prev.current ?? 0;
    prev.current = target;
    let raf = 0;
    let t0 = 0;
    const tick = (now: number) => {
      if (!t0) t0 = now + delay;
      const t = Math.max(0, Math.min(1, (now - t0) / duration));
      setValue(start + (target - start) * easeOutCubic(t));
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
    // `from` is an initial override only; re-running on it would restart finished counts.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target, reduce, duration, delay]);
  if (reduce || !Number.isFinite(target)) return target;
  return value;
}

/** True after the first client paint; lets CSS `animate-rise` run once on mount and never on re-render. */
const noop = () => () => {};
export function useMounted(): boolean {
  return useSyncExternalStore(noop, () => true, () => false);
}

/** Inline style for the nth element in an entrance sequence. */
export const riseDelay = (index: number, step = ENTER_STAGGER_MS) => ({ ["--rise-delay" as string]: `${index * step}ms` });
