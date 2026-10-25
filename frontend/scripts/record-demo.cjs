/**
 * Re-record the landing-page product clips (public/media/*.webm) from the running app.
 *
 *   cd frontend
 *   npm run dev                         # the app, on port 3000
 *   npm i --no-save playwright-core@1.60.0   # matches the Chromium 1223 / ffmpeg 1011 builds in ~/Library/Caches/ms-playwright
 *   BASE=http://localhost:3000 OUT=public/media \
 *   FFMPEG=$HOME/Library/Caches/ms-playwright/ffmpeg-1011/ffmpeg-mac \
 *   node scripts/record-demo.cjs        # or: node scripts/record-demo.cjs hero overview
 *
 * Clips: hero (chart panned through history), overview (totals, cost components, models),
 * team-breakdown (team panel, team page, evidence), reallocate (assistant → review → apply → decisions).
 * If a flow fails it writes <name>-fail.png next to the clips so the broken selector is easy to spot.
 */
const path = require("node:path");
const fs = require("node:fs");
const { execFileSync } = require("node:child_process");
const { chromium } = require("playwright-core");

const BASE = process.env.BASE ?? "http://localhost:3002";
const OUT = process.env.OUT ?? path.join(__dirname, "out");
const FFMPEG = process.env.FFMPEG;
const SIZE = { width: 1440, height: 810 };
const FAKE_NOW = "2026-10-22T14:10:00";

const INIT = `
(() => {
  // Shifted clock: a fixed demo day, but time keeps moving so animations run.
  const Orig = Date;
  const offset = new Orig(${JSON.stringify(FAKE_NOW)}).getTime() - Orig.now();
  class ShiftedDate extends Orig {
    constructor(...args) { if (args.length === 0) super(Orig.now() + offset); else super(...args); }
    static now() { return Orig.now() + offset; }
  }
  window.Date = ShiftedDate;

  // Visible cursor with a click ripple, moved by the recorder alongside the real mouse.
  const ensure = () => {
    if (document.getElementById("__cur") || !document.body) return;
    const el = document.createElement("div");
    el.id = "__cur";
    el.style.cssText = "position:fixed;left:0;top:0;z-index:2147483647;pointer-events:none;transform:translate(-100px,-100px);transition:transform .5s cubic-bezier(.2,.7,.2,1);will-change:transform";
    el.innerHTML = '<svg width="24" height="24" viewBox="0 0 24 24" style="filter:drop-shadow(0 1px 2px rgba(0,0,0,.6))"><path d="M5 3l14 9.2-6.6 1.1L9.2 20z" fill="#fff" stroke="#111" stroke-width="1.4" stroke-linejoin="round"/></svg>'
      + '<div id="__rip" style="position:absolute;left:-12px;top:-12px;width:30px;height:30px;border-radius:50%;border:2px solid rgba(255,255,255,.95);opacity:0;transform:scale(.4)"></div>';
    document.body.appendChild(el);
    window.__cur = {
      move(x, y, ms) { el.style.transitionDuration = ms + "ms"; el.style.transform = "translate(" + x + "px," + y + "px)"; },
      click() { document.getElementById("__rip").animate([{ opacity: .95, transform: "scale(.4)" }, { opacity: 0, transform: "scale(1.7)" }], { duration: 480, easing: "ease-out" }); },
    };
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", ensure); else ensure();
  new MutationObserver(ensure).observe(document.documentElement, { childList: true });
})();
`;

const wait = (page, ms) => page.waitForTimeout(ms);

async function move(page, x, y, ms = 550) {
  await page.evaluate(([x, y, ms]) => window.__cur?.move(x, y, ms), [x, y, ms]);
  await page.mouse.move(x, y, { steps: 24 });
  await wait(page, ms);
}

async function moveTo(page, locator, ms) {
  await locator.first().waitFor({ state: "visible" });
  await locator.first().scrollIntoViewIfNeeded();
  const b = await locator.first().boundingBox();
  if (!b) throw new Error("no box");
  await move(page, b.x + b.width / 2, b.y + b.height / 2, ms);
}

async function click(page, locator, settle = 700) {
  await moveTo(page, locator);
  await page.evaluate(() => window.__cur?.click());
  await locator.first().click();
  await wait(page, settle);
}

async function smoothScroll(page, locator, offset = -96, ms = 900) {
  await locator.first().waitFor({ state: "visible" });
  await locator.first().evaluate((el, offset) => {
    const top = el.getBoundingClientRect().top + window.scrollY + offset;
    window.scrollTo({ top, behavior: "smooth" });
  }, offset);
  await wait(page, ms);
}

async function dragChart(page, locator, dx, ms = 900) {
  const b = await locator.first().boundingBox();
  const x = b.x + b.width * 0.55, y = b.y + b.height * 0.5;
  await move(page, x, y, 500);
  await page.mouse.down();
  const steps = 30;
  for (let i = 1; i <= steps; i++) {
    const nx = x + (dx * i) / steps;
    await page.evaluate(([x, y]) => window.__cur?.move(x, y, 30), [nx, y]);
    await page.mouse.move(nx, y);
    await wait(page, ms / steps);
  }
  await page.mouse.up();
  await wait(page, 600);
}

async function openOverview(page) {
  await page.goto(`${BASE}/overview?teams=default`, { waitUntil: "networkidle" });
  await page.getByText("Daily spend by team").first().waitFor();
  await wait(page, 400);
}

const legendChip = (page, name) => page.locator("footer button, [aria-label='Teams'] button").filter({ hasText: new RegExp(`^${name}$`) });

const FLOWS = {
  // Hero: the overview chart, scrolled back through history and zoomed out, then back to today.
  async hero(page) {
    await openOverview(page);
    await wait(page, 900);
    await click(page, page.getByRole("button", { name: "Month", exact: true }), 1500);
    const chart = page.locator("section[aria-label='Daily spend'] .recharts-wrapper");
    await moveTo(page, chart, 300);
    await dragChart(page, chart, 380, 1100);
    await wait(page, 600);
    await click(page, page.getByRole("button", { name: "All", exact: true }), 1700);
    await click(page, page.getByRole("button", { name: "Month", exact: true }), 1000);
    const today = page.getByRole("button", { name: "Today", exact: true });
    if (await today.count()) await click(page, today, 1200);
    await move(page, 900, 560, 700);
    await move(page, 1100, 520, 900);
    await wait(page, 800);
  },

  // Overview: the company number counts up; then the cost components and the model split.
  async overview(page) {
    await openOverview(page);
    await wait(page, 1200);
    await move(page, 420, 230, 600);
    await move(page, 980, 230, 800);
    await wait(page, 500);
    await smoothScroll(page, page.getByText("Cost components").first(), -140, 1100);
    await moveTo(page, page.getByText("Extra usage").first(), 600);
    await moveTo(page, page.getByText("API", { exact: true }).first(), 700);
    await smoothScroll(page, page.getByText("API spend by model").first(), -120, 1100);
    await moveTo(page, page.getByText("Claude Opus 5.5").first(), 700);
    await moveTo(page, page.getByText("Gemini 3 Pro").first(), 800);
    await wait(page, 1200);
  },

  // Team breakdown: pick a team on the chart, open its panel, then the team page with people and evidence.
  async "team-breakdown"(page) {
    await openOverview(page);
    await wait(page, 900);
    await click(page, legendChip(page, "Research"), 1300);
    const panel = page.getByRole("dialog");
    await click(page, panel.locator("summary", { hasText: "Cost components" }), 900);
    await click(page, panel.locator("summary", { hasText: "By model" }), 1300);
    await click(page, panel.getByText(/View team/).first(), 300);
    const people = page.getByRole("heading", { name: /^People/ }).first();
    await people.waitFor({ timeout: 15000 });
    await wait(page, 1200);
    await smoothScroll(page, people, -120, 1000);
    await wait(page, 700);
    const evidenceHeading = page.getByRole("heading", { name: /^Context/ }).first();
    if (await evidenceHeading.count()) {
      await smoothScroll(page, evidenceHeading, -110, 1100);
    } else {
      await click(page, page.getByRole("link", { name: "Evidence", exact: true }).first(), 300);
      await page.waitForLoadState("networkidle");
      await wait(page, 1400);
    }
    const open = page.getByRole("button", { name: /^Open (thread|channel|task|page|board|doc|issue)/ }).first();
    if (await open.count()) { await click(page, open, 1800); await page.keyboard.press("Escape"); }
    else { await move(page, 720, 520, 800); }
    await wait(page, 900);
  },

  // Reallocate: ask the assistant, review the proposal, apply it, see the receipt in Decisions.
  async reallocate(page) {
    await openOverview(page);
    await wait(page, 700);
    await click(page, page.getByRole("button", { name: /Assistant/ }).first(), 900);
    await click(page, page.getByRole("button", { name: /another \$\d/ }).first(), 300);
    const review = page.getByRole("button", { name: "Review", exact: true }).first();
    await review.waitFor({ state: "visible", timeout: 15000 });
    await wait(page, 1200);
    await click(page, review, 1400);
    const why = page.getByText("Why", { exact: true }).first();
    if (await why.count()) await moveTo(page, why, 700);
    await click(page, page.getByRole("button", { name: "Apply", exact: true }), 300);
    await page.getByText(/^Applied( and saved)?\b/).first().waitFor({ timeout: 10000 });
    await wait(page, 1600);
    const done = page.getByRole("button", { name: "Done", exact: true });
    if (await done.count()) await click(page, done, 500);
    await page.keyboard.press("Escape");
    await wait(page, 500);
    await click(page, page.getByRole("link", { name: "Decisions", exact: true }).first(), 300);
    await page.getByText(/Decisions/).first().waitFor();
    await wait(page, 1800);
  },
};

async function record(name) {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: SIZE,
    colorScheme: "dark",
    recordVideo: { dir: OUT, size: SIZE },
  });
  await context.addInitScript(INIT);
  const page = await context.newPage();
  let failed;
  try {
    await FLOWS[name](page);
  } catch (e) {
    failed = e;
    try { await page.screenshot({ path: path.join(OUT, `${name}-fail.png`) }); } catch {}
  }
  const video = page.video();
  await context.close();
  const raw = path.join(OUT, `${name}.raw.webm`);
  await video.saveAs(raw);
  await video.delete().catch(() => {});
  await browser.close();
  if (failed) { console.error(`✗ ${name}: ${failed.message.split("\n")[0]}`); fs.rmSync(raw, { force: true }); return false; }
  const dest = path.join(OUT, `${name}.webm`);
  try {
    if (!FFMPEG) throw new Error("no ffmpeg");
    // Trim the blank lead-in and re-encode at a steady bitrate.
    execFileSync(FFMPEG, ["-y", "-loglevel", "error", "-ss", "0.7", "-i", raw, "-c:v", "libvpx", "-b:v", "2000k", "-crf", "12", "-auto-alt-ref", "0", "-an", dest]);
    fs.rmSync(raw, { force: true });
  } catch (e) {
    console.error(`  (kept raw recording: ${e.message.split("\n")[0]})`);
    fs.renameSync(raw, dest);
  }
  const kb = Math.round(fs.statSync(dest).size / 1024);
  console.log(`✓ ${name} → ${dest} (${kb} KB)`);
  return true;
}

(async () => {
  const names = process.argv.slice(2).length ? process.argv.slice(2) : Object.keys(FLOWS);
  fs.mkdirSync(OUT, { recursive: true });
  let ok = true;
  for (const n of names) ok = (await record(n)) && ok;
  process.exit(ok ? 0 : 1);
})();
