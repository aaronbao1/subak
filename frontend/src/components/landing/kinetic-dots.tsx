"use client";
import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";

/*
 * Hero backdrop: a 24px dot grid that leans toward the pointer and brightens around it, with a ring that
 * runs out from each click. Canvas-drawn so thousands of dots cost one paint. The dots use the current
 * text color (so they follow the theme), draw at device pixel ratio, and the loop only runs while the
 * pointer is over the hero or a ripple is still live; otherwise a single static frame is left on screen.
 * Touch pointers and reduced-motion users get the static grid.
 */

const SPACING = 24;
const INFLUENCE = 220; // px around the pointer that reacts
const MAX_PULL = 14; // px a dot can move toward the pointer
const EASE = 0.1; // pointer and strength easing per frame
const BASE_ALPHA = 0.1;
const ACTIVE_ALPHA = 0.6;
const BASE_RADIUS = 1;
const ACTIVE_RADIUS = 1.8;

const RIPPLE_SPEED = 380; // px per second
const RIPPLE_LIFE = 0.9; // seconds
const RIPPLE_WIDTH = 48; // px band that moves
const RIPPLE_PUSH = 10; // px of outward displacement

interface Ripple {
  x: number;
  y: number;
  born: number;
}

export function KineticDots({ className }: { className?: string }) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    let w = 0;
    let h = 0;
    let ink = getComputedStyle(canvas).color;
    const mouse = { x: 0, y: 0 };
    const target = { x: 0, y: 0 };
    let strength = 0; // 0 = pointer away, 1 = pointer over the hero
    let targetStrength = 0;
    const ripples: Ripple[] = [];
    let raf = 0;
    let running = false;

    const draw = (now: number) => {
      ctx.clearRect(0, 0, w, h);
      for (let i = ripples.length - 1; i >= 0; i--) {
        if ((now - ripples[i].born) / 1000 > RIPPLE_LIFE) ripples.splice(i, 1);
      }

      const cols = Math.ceil(w / SPACING) + 1;
      const rows = Math.ceil(h / SPACING) + 1;
      const offX = ((w % SPACING) + SPACING) / 2;
      const offY = SPACING / 2;

      ctx.fillStyle = ink;
      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          const gx = offX + c * SPACING;
          const gy = offY + r * SPACING;
          let x = gx;
          let y = gy;
          let t = 0;

          // Pull toward the pointer with a bell falloff; dots right under it stay put so it never "snaps".
          const dx = gx - mouse.x;
          const dy = gy - mouse.y;
          const dist = Math.hypot(dx, dy);
          if (strength > 0.001 && dist < INFLUENCE && dist > 0) {
            const n = dist / INFLUENCE;
            t = (1 - n) * (1 - n) * strength;
            const pull = t * MAX_PULL * Math.min(1, dist / 40);
            x -= (dx / dist) * pull;
            y -= (dy / dist) * pull;
          }

          // Each click sends a thin ring outward; dots in the band move with it and light up briefly.
          for (const rp of ripples) {
            const age = (now - rp.born) / 1000;
            const radius = age * RIPPLE_SPEED;
            const fade = 1 - age / RIPPLE_LIFE;
            const rdx = gx - rp.x;
            const rdy = gy - rp.y;
            const rd = Math.hypot(rdx, rdy);
            const diff = rd - radius;
            if (rd > 0 && Math.abs(diff) < RIPPLE_WIDTH) {
              const s = (1 - Math.abs(diff) / RIPPLE_WIDTH) * fade;
              x += (rdx / rd) * s * RIPPLE_PUSH;
              y += (rdy / rd) * s * RIPPLE_PUSH;
              t = Math.max(t, s * 0.8);
            }
          }

          ctx.globalAlpha = BASE_ALPHA + (ACTIVE_ALPHA - BASE_ALPHA) * t;
          ctx.beginPath();
          ctx.arc(x, y, BASE_RADIUS + (ACTIVE_RADIUS - BASE_RADIUS) * t, 0, Math.PI * 2);
          ctx.fill();
        }
      }
      ctx.globalAlpha = 1;
    };

    const loop = (now: number) => {
      mouse.x += (target.x - mouse.x) * EASE;
      mouse.y += (target.y - mouse.y) * EASE;
      strength += (targetStrength - strength) * EASE;
      draw(now);

      const settled =
        targetStrength === 0 && strength < 0.005 && ripples.length === 0;
      if (settled) {
        strength = 0;
        draw(now);
        running = false;
        return;
      }
      raf = requestAnimationFrame(loop);
    };

    const wake = () => {
      if (running || reduced) return;
      running = true;
      raf = requestAnimationFrame(loop);
    };

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = rect.width;
      h = rect.height;
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      // Resolve the CSS color (oklch) to something the canvas can take, via the canvas itself.
      ctx.fillStyle = getComputedStyle(canvas).color;
      ink = ctx.fillStyle;
      draw(performance.now());
    };

    const ro = new ResizeObserver(resize);
    ro.observe(canvas);
    resize();

    if (reduced) return () => ro.disconnect();

    const localPoint = (e: PointerEvent) => {
      const rect = canvas.getBoundingClientRect();
      return {
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
        inside:
          e.clientX >= rect.left - INFLUENCE &&
          e.clientX <= rect.right + INFLUENCE &&
          e.clientY >= rect.top - INFLUENCE &&
          e.clientY <= rect.bottom + INFLUENCE,
      };
    };

    const onMove = (e: PointerEvent) => {
      if (e.pointerType !== "mouse") return;
      const p = localPoint(e);
      if (p.inside) {
        if (targetStrength === 0 && strength < 0.005) {
          // Coming in from outside: start the eased pointer at the entry point so dots do not sweep in.
          mouse.x = p.x;
          mouse.y = p.y;
        }
        target.x = p.x;
        target.y = p.y;
        targetStrength = 1;
      } else {
        targetStrength = 0;
      }
      wake();
    };

    const onLeave = () => {
      targetStrength = 0;
      wake();
    };

    const onDown = (e: PointerEvent) => {
      if (e.pointerType !== "mouse" || e.button !== 0) return;
      const p = localPoint(e);
      const rect = canvas.getBoundingClientRect();
      if (e.clientX < rect.left || e.clientX > rect.right || e.clientY < rect.top || e.clientY > rect.bottom) return;
      ripples.push({ x: p.x, y: p.y, born: performance.now() });
      wake();
    };

    window.addEventListener("pointermove", onMove, { passive: true });
    window.addEventListener("pointerdown", onDown, { passive: true });
    document.addEventListener("pointerleave", onLeave);
    window.addEventListener("blur", onLeave);

    return () => {
      ro.disconnect();
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerdown", onDown);
      document.removeEventListener("pointerleave", onLeave);
      window.removeEventListener("blur", onLeave);
      cancelAnimationFrame(raf);
    };
  }, []);

  return (
    <canvas
      ref={ref}
      aria-hidden
      className={cn(
        "pointer-events-none text-foreground [mask-image:linear-gradient(to_bottom,black_55%,transparent_100%)]",
        className,
      )}
    />
  );
}
