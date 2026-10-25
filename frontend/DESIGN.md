# Design system — house decisions (Oct 24)

Source spec: `/private/tmp/claude-501/-Users-erfanballew/08f08e85-80db-4705-b54b-8b0968f697e5/scratchpad/ramp-style-spec.md`
(a measured translation of ramp.com into dark tokens). Read it once. These house decisions override it where they differ.

## Deviations from the spec (decided by the owner)
1. **Surfaces stay cool (hue 260), not warm charcoal.** The owner wants the landing and dashboard on the same dark blue-gray. Use the existing `bg-background` / `bg-card` / `bg-popover` tokens. Do not introduce warm neutrals or `#000`.
2. **Team charts keep the validated 8-slot categorical palette** (`--chart-1..8`, `--chart-other`), not the accent. Identity colors follow the team, in fixed order, never cycled; a 9th+ team folds into "Other" (`--chart-other`) with a picker to swap teams in.
3. **The accent is budgeted exactly as the spec says**: one primary CTA per screen (`<Button variant="brand">` or `bg-brand text-brand-foreground`), mono eyebrows (`.eyebrow`), the active sidebar rule, the focus ring, selected-row wash (`bg-brand-soft`). Nowhere else. Status colors stay `--success` / `--warning` / `--destructive`.

## Tokens that exist now (globals.css)
- Fonts: `font-sans` = Instrument Sans (400/500/600), `font-mono` = IBM Plex Mono (400/500). `h1,h2,h3` default to weight 500, tracking -0.01em, balanced. Never use `font-bold`/700.
- `.eyebrow` = mono 11px uppercase +0.08em muted. `.num` = mono tabular. Use `.num` on every money/percent/date value and `text-right` in tables.
- Colors: `brand`, `brand-hover`, `brand-foreground`, `brand-soft`, `border`, `border-strong`, `success`, `warning`, `destructive`, `chart-1..8`, `chart-other`, plus the shadcn set.
- Radius: 4 chips (`rounded-sm`), 6 buttons/inputs/badges (`rounded-md`), 8 icon tiles (`rounded-lg`), 12 cards/frames/panels (`rounded-xl`), 16 bands/dialogs (`rounded-2xl`). `rounded-full` only for dots and avatars.

## Rules every lane follows
- **Type carries hierarchy, not weight or color.** Display 40/48/64, h1 34/40/48, h2 28/32/40, h3 22/25/28, body 15/16, small 14, caption 12/13. Weight 400–500 only; emphasis is 500 or an ink shift.
- **Ink levels:** `text-foreground` (primary), `text-foreground/80` or `text-muted-foreground` (secondary/captions). No alpha below `/70` on informative text.
- **1px borders, no resting shadows.** Cards: `rounded-xl border border-border bg-card`. Hover = `border-border-strong`, never a shadow or lift. Shadows only on floating layers (popover, dialog, sheet).
- **Never nest a card in a card.** Use `divide-y divide-border` sections inside one panel.
- **Two section rhythms** on the landing: `py-12 md:py-20`. Container `max-w-[1440px] mx-auto px-4 md:px-8 lg:px-12 xl:px-16`. Dashboard content `p-6 space-y-6 max-w-[1600px]`.
- **Buttons:** h-9 (nav) / h-10 (page) / h-[42px] (hero), `px-4 rounded-md text-sm font-medium`, `transition-colors duration-300`. Primary = brand. Secondary = ink fill (`bg-primary text-primary-foreground`). Ghost = `bg-popover border border-border`. Never uppercase, never icon-only without an aria-label.
- **Tables:** header `h-10 .eyebrow border-b border-border-strong`, rows `h-12 border-b border-border last:border-0 hover:bg-popover`, no zebra, numerics `.num text-right`, selected row `bg-brand-soft shadow-[inset_2px_0_0_var(--brand)]`.
- **Stat / hero number:** label above (`.eyebrow`), number in `.num` at 32–56px weight 400–500, delta row below in caption size. Exactly one hero figure per view (the overview's total spend, ≥48px).
- **Charts (dataviz skill at `/private/tmp/claude-501/bundled-skills/2.1.306/d78aaa2fa86feb2b77b7d2c22ec7c066/dataviz`, read `references/marks-and-anatomy.md` and `references/anti-patterns.md`):** 2px lines, round joins; markers ≥8px (r≥4) with a 2px `var(--card)` ring; bars ≤24px wide, 4px rounded data-end, square at the baseline, 2px surface gap between stacked segments; horizontal hairline grid only, solid, `var(--border)`; no axis lines; axis text mono 11px muted; legend always present for ≥2 series as chips with a square 8px swatch; text never wears the series color; one y-axis.
- **Motion:** 150ms (menus) and 300ms (color/opacity) only, plus at most one fade-up on enter. No parallax, no hover lift, no glow. Respect `prefers-reduced-motion` (already global).
- **Chrome is quiet:** sentence case everywhere; uppercase only in `.eyebrow`. Icons `size-4 text-muted-foreground` stroke 1.5. No colored headers, no gradient bars, no icon backgrounds.
- **Copy:** sentence case, 4–6 word two-clause headlines, no exclamation marks, no Title Case. Product rules in `CLAUDE.md` still apply (add ≠ redistribute, units explicit, provenance visible, missing data shown, placeholder tagged).
