#!/usr/bin/env node
// Survey a page's floating elements before the spec is written: what is fixed
// or sticky or moves when scrolled, where each sits at load, what it does when
// scrolled, what opened itself after load or on scroll (an absolute overlay
// too: a cookie dialog), and what moves when the viewport grows (a tab at `top: 50%`, which
// a full-page shot would put mid-page). It measures what is there, not what
// the reference wants: an element open at load reads as its open size.
// Run from the directory whose node_modules has @playwright/test (the app or
// the standalone folder):
//   node <skill>/scripts/floating.mjs <url> [--device WxH[@dpr][+touch]] [--wait <seconds>] [--http-credentials user:pass]
// Limits: one page at one size, a plain context (basic auth only, no login, no
// storage state, the default user agent), no shadow roots or iframes, only
// what happens within the wait.
import { createRequire } from "node:module";
import { resolve } from "node:path";

const usage = "usage: node floating.mjs <url> [--device WxH[@dpr][+touch]] [--wait <seconds>] [--http-credentials user:pass]";
const args = process.argv.slice(2);
if (args.includes("--help")) {
  console.log(usage);
  process.exit(0);
}
const positional = [];
let deviceArg = "1920x1080"; // snapseq's default desktop
let waitArg = "5";
let credArg = null;
let unknown = false;
for (let i = 0; i < args.length; i++) {
  if (args[i] === "--device") deviceArg = args[++i];
  else if (args[i] === "--wait") waitArg = args[++i];
  else if (args[i] === "--http-credentials") credArg = args[++i] ?? "";
  else if (args[i].startsWith("--")) unknown = true;
  else positional.push(args[i]);
}
const [url] = positional;
const [, width, height, dpr, touch] = /^(\d+)x(\d+)(?:@(\d+(?:\.\d+)?))?(\+touch)?$/.exec(deviceArg ?? "") ?? [];
const waitMs = Number(waitArg) * 1000;
const cred = credArg === null ? null : /^([^:]*):(.*)$/s.exec(credArg);
if ((credArg !== null && !cred) || unknown || positional.length !== 1 || !(width > 0 && height > 0) || (dpr !== undefined && !(dpr > 0)) || !Number.isFinite(waitMs) || waitMs < 0) {
  console.error(usage);
  process.exit(2);
}

let chromium;
try {
  ({ chromium } = createRequire(resolve("package.json"))("@playwright/test"));
} catch {
  console.error(`@playwright/test not found from ${process.cwd()}: run from the app or the standalone folder`);
  process.exit(2);
}

// The same freeze snapseq applies, so a transition cannot blur a measurement.
const NO_MOTION = `*, *::before, *::after { transition: none !important; animation: none !important; } html { scroll-behavior: auto !important; }`;

// One evaluate for the scroll measurements, so elements keep their identity.
// The listed elements stay on `window` for the taller-viewport measurement.
// Arrow functions only: a named function gets a wrapper the page does not have.
const survey = async ({ waitMs }) => {
  const sleep = (ms) => new Promise((done) => setTimeout(done, ms));
  const floats = (m) => m.position === "fixed" || m.position === "sticky";
  const measure = () => {
    const map = new Map();
    for (const el of document.body.querySelectorAll("*")) {
      const cs = getComputedStyle(el);
      const r = el.getBoundingClientRect();
      if (r.width === 0 || r.height === 0 || cs.display === "none" || cs.visibility === "hidden" || Number(cs.opacity) === 0) continue;
      map.set(el, {
        position: cs.position,
        docTop: Math.round(r.top + scrollY),
        docLeft: Math.round(r.left + scrollX),
        top: Math.round(r.top),
        bottom: Math.round(innerHeight - r.bottom),
        left: Math.round(r.left),
        right: Math.round(innerWidth - r.right),
        width: Math.round(r.width),
        height: Math.round(r.height),
      });
    }
    return map;
  };
  const label = (el) =>
    el.tagName.toLowerCase() +
    (el.id ? `#${CSS.escape(el.id)}` : "") +
    [...el.classList].slice(0, 2).map((c) => `.${CSS.escape(c)}`).join("");
  // The nearer edges. Which edge anchors it is what the taller viewport tells.
  const place = (m) => {
    if (m.top >= innerHeight) return `below the viewport, slot at ${m.docTop}, ${m.width}x${m.height}`;
    const vertical = m.top <= m.bottom ? `top ${m.top}` : `bottom ${m.bottom}`;
    const horizontal =
      m.width >= innerWidth * 0.95 ? "full width" : m.left <= m.right ? `left ${m.left}` : `right ${m.right}`;
    return `${vertical}, ${horizontal}, ${m.width}x${m.height}`;
  };
  const differs = (a, b) => ["top", "left", "width", "height"].some((k) => Math.abs(a[k] - b[k]) > 2);

  scrollTo(0, 0);
  await sleep(300);
  const atLoad = measure();
  await sleep(waitMs);
  const settled = measure();
  const half = Math.round((document.documentElement.scrollHeight - innerHeight) / 2);
  scrollTo(0, half);
  await sleep(500);
  const didScroll = scrollY > 0; // 0 when the page fits the viewport or a container scrolls
  const scrolled = measure();
  scrollTo(0, 0);
  await sleep(500);
  const back = measure();

  const listed = new Set();
  const rows = [];
  const underListed = (el) => {
    for (let p = el.parentElement; p; p = p.parentElement) if (listed.has(p)) return true;
    return false;
  };
  const consider = (el, m, present) => {
    const a = atLoad.get(el);
    const s = scrolled.get(el);
    const b = back.get(el);
    const moved = didScroll && s !== undefined && (Math.abs(s.docTop - m.docTop) > 2 || Math.abs(s.docLeft - m.docLeft) > 2);
    const lateOverlay = present && a === undefined && m.position === "absolute";
    const everFloats = [a, m, s, b].some((x) => x !== undefined && floats(x));
    if (!everFloats && !moved && !lateOverlay) return;
    // A child moving only because a listed ancestor moves says nothing new; a
    // fixed or sticky child of a fixed header is its own element.
    if (!everFloats && !lateOverlay && underListed(el)) return;
    listed.add(el);
    const shifted =
      s === undefined
        ? ""
        : Math.abs(s.top - m.top) > 2
          ? `, at top ${s.top} when scrolled`
          : Math.abs(s.left - m.left) > 2
            ? `, at left ${s.left} when scrolled`
            : "";
    const scrollNote = !present
      ? "-"
      : s === undefined
        ? "hidden"
        : m.position === "fixed"
          ? moved
            ? `fixed to the viewport${shifted}`
            : "scrolls with the page (fixed inside a transformed ancestor)"
          : m.position === "sticky"
            ? moved
              ? "sticks"
              : "stays in flow"
            : moved
              ? "moves with the scroll (a script positions it, or content above it loaded)"
              : "stays in flow";
    const onScroll = !didScroll
      ? "not scrolled (the page fits the viewport, or a container scrolls)"
      : present && s !== undefined && s.position !== m.position
        ? `becomes ${s.position} when scrolled${floats(s) ? `, at top ${s.top}` : ""}`
        : scrollNote;
    const stranded =
      present && didScroll && b !== undefined && Math.abs(b.docTop - m.docTop) > 2 ? `; stranded at top ${b.top} after scrolling back` : "";
    const afterLoad = !present
      ? `gone within ${waitMs / 1000} s after load`
      : a === undefined
        ? `appeared within ${waitMs / 1000} s after load`
        : differs(a, m)
          ? `changed within ${waitMs / 1000} s after load: was ${place(a)}`
          : "";
    const ref = b ?? m;
    rows.push({ element: label(el), position: m.position, atLoad: place(m), onScroll: onScroll + stranded, afterLoad, grow: present && b !== undefined && !stranded, top: ref.top, bottom: ref.bottom, docTop: ref.docTop });
  };
  for (const [el, m] of settled) consider(el, m, true);
  for (const [el, m] of atLoad) if (!settled.has(el) && floats(m)) consider(el, m, false);
  // An absolute overlay a scroll shows (a dialog on first scroll) counts, as after load.
  const shows = (el, m) => floats(m) || (m.position === "absolute" && !underListed(el));
  for (const [el, s] of scrolled) {
    if (!didScroll || settled.has(el) || atLoad.has(el) || !shows(el, s)) continue;
    listed.add(el);
    rows.push({ element: label(el), position: s.position, atLoad: "-", onScroll: `appears when scrolled: ${place(s)}`, afterLoad: "", grow: false });
  }
  for (const [el, b] of back) {
    if (!didScroll || settled.has(el) || atLoad.has(el) || scrolled.has(el) || !shows(el, b)) continue;
    listed.add(el);
    rows.push({ element: label(el), position: b.position, atLoad: "-", onScroll: `appears when scrolled back: ${place(b)}`, afterLoad: "", grow: false });
  }
  window.__floating = [...listed];
  return { viewport: `${innerWidth}x${innerHeight}`, docHeight: document.documentElement.scrollHeight, rows };
};

// After the viewport grew: which edge each element keeps tells its anchor, and
// one that keeps neither is placed by a share of the viewport height. Null
// when the document was replaced and `__floating` is gone.
const regrow = () =>
  window.__floating?.map((el) => {
    const cs = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0 || cs.display === "none" || cs.visibility === "hidden" || Number(cs.opacity) === 0) return null;
    return { position: cs.position, docTop: Math.round(r.top + scrollY), top: Math.round(r.top), bottom: Math.round(innerHeight - r.bottom) };
  }) ?? null;

const browser = await chromium.launch();
try {
  const probe = await browser.newContext();
  const userAgent = (await (await probe.newPage()).evaluate(() => navigator.userAgent)).replace("HeadlessChrome", "Chrome");
  await probe.close();
  const viewport = { width: Number(width), height: Number(height) };
  const context = await browser.newContext({
    viewport,
    deviceScaleFactor: dpr ? Number(dpr) : 1,
    hasTouch: Boolean(touch), // what snapseq's mobile device sets; no isMobile, so the survey measures the capture's context
    ignoreHTTPSErrors: true,
    userAgent,
    httpCredentials: cred ? { username: cred[1], password: cred[2], origin: new URL(url).origin } : undefined, // the page's origin only
  });
  const page = await context.newPage();
  await page.addInitScript((css) => {
    const style = document.createElement("style");
    style.textContent = css;
    const head = document.head ?? document.documentElement;
    if (head) head.appendChild(style);
    else document.addEventListener("DOMContentLoaded", () => document.head.appendChild(style), { once: true });
  }, NO_MOTION);
  const response = await page.goto(url, { waitUntil: "load", timeout: 60_000 });
  if (!response || response.status() >= 400) {
    console.error(`${url}: HTTP ${response ? response.status() : "no response"}; nothing surveyed`);
    process.exitCode = 1;
  } else {
    const result = await page.evaluate(survey, { waitMs });
    const taller = viewport.height * 2;
    let grown = null;
    let unmeasured = "the page reloaded on resize";
    try {
      await page.setViewportSize({ width: viewport.width, height: taller });
      await page.waitForTimeout(500);
      grown = await page.evaluate(regrow);
    } catch (e) {
      unmeasured = String(e.message).split("\n")[0];
    }
    if (!grown) console.error(`taller viewport not measured: ${unmeasured}`);
    result.rows.forEach((row, i) => {
      const g = grown?.[i];
      row.taller = !row.grow || !grown
        ? "-"
        : g === null
          ? "hidden"
          : g.position !== row.position
            ? `becomes ${g.position} in the taller viewport`
            : row.position === "sticky"
              ? Math.abs(g.docTop - row.docTop) > 2
                ? `at top ${g.docTop} in the taller viewport (landing, or still pinned)`
                : "stays"
              : Math.abs(g.top - row.top) <= 2
                ? `anchored top ${g.top}`
                : Math.abs(g.bottom - row.bottom) <= 2
                  ? `anchored bottom ${g.bottom}`
                  : `neither edge kept: top ${row.top} at ${viewport.height}, ${g.top} at ${taller} (a share of the viewport height, or a breakpoint)`;
    });
    const widths = [56, 9, 36, 52, 44, 0];
    const line = (cells) => cells.map((c, i) => String(c).padEnd(widths[i])).join("  ").trimEnd();
    console.log(`viewport ${result.viewport}  document ${result.docHeight} px  ${url}`);
    console.log(line(["element", "position", "at load (scroll 0)", "on scroll", "after load", `viewport ${taller} tall`]));
    for (const r of result.rows) console.log(line([r.element, r.position, r.atLoad, r.onScroll, r.afterLoad, r.taller]));
    if (result.rows.length === 0) console.log("(nothing floats)");
  }
} finally {
  await browser.close();
}
