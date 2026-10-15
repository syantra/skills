---
name: snapseq
description: Set up and run a snapseq screenshot capture set, so a site's pages come out as numbered desktop and mobile screenshots on disk, scripted with Playwright and repeatable, each shot labelled on a strip above it when the reference labels it, and bound into one PDF per device. Use whenever the user wants a site's pages screenshotted as a set (a page set, a capture set, a labelled PDF of each page), the pages of a review proof shot again from the site, a capture written or fixed, or snapseq installed in a repo, a monorepo app or a standalone folder, even if they never say snapseq. Not for one quick screenshot to look at a page, a capture of what is open in the user's browser, Playwright visual tests (toHaveScreenshot), or exporting a proof's own pages (the workfront-proof skill does that).
license: ISC
compatibility: Needs uv for the setup script, Node 20+ with pnpm, yarn or npm, network access to the npm registry and to the site, and Chromium through Playwright (installed under Node 22 when the machine runs Node 26).
metadata:
  version: "0.3"
---

# snapseq

You set up and run a screenshot capture set with snapseq, a Playwright Test fixture package: one capture file per job, every shot numbered, one folder per device, saved on disk. What to shoot comes from a reference: a review proof, a PDF, or a list of routes. Nothing leaves the machine. You take the shots, with the reference's labels on a strip above them and bound into a PDF per device, and report the run directory; the user uploads the PDFs.

The rules a capture must follow are in [references/snapseq.md](references/snapseq.md). Read it before writing one. `<skill-dir>` below is the folder holding this file; run every command from the user's directory, never from `<skill-dir>`.

## 1. Assess the directory, always first

```bash
uv run <skill-dir>/scripts/snapseq_setup.py assess <dir>     # <dir> defaults to .
```

For a standalone job, assess the directory the new folder will go in. It prints JSON: `root`, `packageManager`, `workspace`, every `apps[]` record (framework, dev command and `port`, `snapseq` and `playwright` versions, `plugins` (the `snapseq-*` packages installed), `config`, existing `captures` and `sequences`), `node`, `node22`, `chromium`, and a `verdict`:

- `reuse`: `app` already has snapseq.
- `add-to`: `app` is a package without snapseq. Install there.
- `standalone`: no package here. Make a folder of its own.

`app` is relative to `root`; `appPath` is the same app as an absolute path, which is what `init --app` takes. The app the directory is inside always wins. `choose` lists candidate apps when the script cannot pick one. Pick the app that serves the reference's pages if the routes make it obvious; otherwise ask the user, one question. If no assessed app serves the reference's site (its routes and page headings are not in the code), the job is standalone whatever the verdict: ask the user where to put the folder. Say the verdict in one line before going on.

## 2. Read the reference

It gives the rows, and the device sizes and routes that setup and the survey need. Rows come from the first of these that applies:

1. **A review proof.** With the workfront-proof skill installed, run its `pages` command and use its page-by-page description. Without it, do not guess at the proof: ask the user for the proof's exported PDF or page images and read those, and mention that `npx skills add syantra/skills --skill workfront-proof` reads proofs directly. Any other tool that gives the same per-page facts (device, width and pixel ratio, extent, what changed between captures) serves as well. Group the pages into jobs before numbering: a desktop run and the mobile run that follows it are one job, a second desktop run starts the next. A job is one capture, every page in reference order. Never split a job, never join two jobs, never pad a capture. Within a job, pair each desktop capture page with its mobile counterpart (the same page in the same state) into one row. How a page's label, extent, changes, size and the `Labels:` line become the row, its shot and the config is under Rows from a reference in [references/sequence.md](references/sequence.md). A page whose `label` is null while `labelStrip` is set (a `Labels:` line other than `none`; off macOS the text is not read): read the strip's text from the page's first slice image.
2. **A PDF or images the user gives.** Read them page by page the same way; a line of text on a band above a capture is its label.
3. **Routes the user lists.** One row each, `full` unless told otherwise.
4. **Nothing.** Open the host, read the primary navigation and `/sitemap.xml` or the sitemap page, and propose rows. Show the table and ask once before writing the capture.

The reference must come from the host you shoot. A proof or PDF whose name says `dev`, `staging` or `UAT`, or that shows states the host does not have (a form, a result, a section that is not in the page), is a build the host lacks: stop and ask for that build's host before setup. Never fill such rows with the nearest live state or a repeated shot unless the user says to; a set that does not match its reference is not a result.

## 3. Set up

**reuse.** Read the app's `snapseq.config.ts`, every file in its captures folder (the config's `capturesDir`, `captures/` by default) and every `*.sequence.md`. They hold the site's quirks (a sticky bar that must land, a menu that opens only on pointer travel, an API without CORS on dev) and the helpers that handle them. Reuse those; do not write a second helper for a solved quirk. The config's devices stand, whatever the reference measures. With `chromium: false` or no `node_modules` in the app, run `<pm> install`, then `<pm> exec playwright install chromium` (`npx` under npm), with assess's `node22` first on `PATH` when `node` is 26 or later. A `snapseq` below 0.3, or `plugins` without `snapseq-label` and `snapseq-pdf`: in `appPath`, run `<pm> add -D snapseq@^0.3.0 snapseq-label snapseq-pdf @playwright/test@^1.59`, then the browser install, and add `plugins: [label(), pdf()]` to the config. 0.3 numbers shots `01.png`; set `numbering: "000"` when the app's sequences and past uploads say `001.png`.

**add-to.**

```bash
uv run <skill-dir>/scripts/snapseq_setup.py init --app <appPath>             # host from the dev script's port, webServer "<pm> dev"
uv run <skill-dir>/scripts/snapseq_setup.py init --app <appPath> --host http://localhost:4000 --dev-command "pnpm dev --port 4000"
```

**standalone.**

```bash
uv run <skill-dir>/scripts/snapseq_setup.py init --standalone <dir> --host https://www.example.com \
  --device desktop=<W>x<H>@<dpr> --device mobile=<W>x<H>@<dpr>+touch
```

- `<dir>`: an absolute path outside any repo, `<site>-screenshots` in the user's directory, `<site>` the host without `www.` and the TLD (`example-screenshots` for `www.example.com`), unless the user names one. When the user's directory is inside a repo, ask where.
- Devices, on add-to and standalone: pass `--device` to match the reference when it measured its captures (a proof's `css` width and `dpr`; the height only matters for viewport shots, and a reference captured at two heights gets the one most rows use, the other rows noted in the spec); with no measurement, pass no `--device` and snapseq's defaults apply (1920×1080, 390×844 at 2x).
- The script runs `install` and the Chromium install, under Node 22 when the machine is on Node 26 and nvm has a 22. If it says it skipped the browser, tell the user the command to run. If the install fails after the files are written, a rerun is refused (the folder is not empty): finish inside the folder with `<pm> install`, then the browser install.

`init` installs `snapseq-label` and `snapseq-pdf` with snapseq and lists both in the config as `plugins: [label(), pdf()]`; the label style is set from the reference once the spec names it (Plugins in [references/snapseq.md](references/snapseq.md)). Add `--no-install` to write the files only. The script refuses to overwrite an existing config.

## 4. Survey what floats

A reference of routes only has nothing to hold the survey against: skip it, treat every element as `flow`, and survey a page only when a first run misplaces something. Otherwise, before the spec, run the survey on the pages the reference covers, at every device size in the config, from the app or the standalone folder (where `@playwright/test` is installed; under Yarn PnP there is no `node_modules`, so run it with `yarn node`). The survey does not start a server: for a local host, start the app's dev server (the `webServer` command in the config) first and wait until the URL answers. Behind basic auth (HTTP 401), add `--http-credentials <user>:<password>`.

```bash
node <skill-dir>/scripts/floating.mjs <host><route> --device <W>x<H>@<dpr>          # each device in the config
node <skill-dir>/scripts/floating.mjs <host><route> --device <W>x<H>@<dpr>+touch    # one with hasTouch
```

Each line is one element that is fixed or sticky, moves when scrolled, or appeared after load: where it sits at scroll 0, what it does when scrolled, what changed after load, and the edge it keeps in a taller viewport. Hold each line's size and place against the reference; that gives the spec's Floating table. How to read the lines, and what the survey cannot see, is under Floating elements in [references/snapseq.md](references/snapseq.md).

## 5. Write the spec before any code

`<name>.sequence.md` in the captures folder, one row per shot in reference order; the capture follows the file, never the other way round. The template is [references/sequence.md](references/sequence.md). A capture is named after its job's title as a slug (the proof's name or the PDF's filename, `12345-spring-launch`), never after the site: `captures/<job>.capture.ts` runs to `<run>/<job>/<device>/`, one PDF per device per job. A routes-only reference is one capture, named after what the user calls the set. Each capture has its own `<name>.sequence.md` beside it; shots run from 01 through the job, and the spec's Proof page column keeps the mapping to the reference. The filter is a path regex, so `<pm> screenshot <job>` runs one job.

`Route` comes from the code in a repo (search for the page heading or nav label) or from the navigation links on a live site. `State` and `Shot` come from the reference. `Action` comes from the page: find the control by role and visible name in the HTML (`curl -sL <url>`, or the component in the repo).

The Floating table is the survey held against the reference: one line per element, its anchor, what the reference shows, and a treatment from [references/snapseq.md](references/snapseq.md) (`flow`, `hide`, `closed`, `pin`). A state the reference shows on purpose (the same on several pages, or named in its labels) is a row. One that looks left behind by its tool (a menu open on one full page only, a scroll-triggered button mid-page) is not reproduced: list it under "Not reproduced" with why, and ask once if the user may want it as a row.

Privacy: the proof link, reviewer names and comment text never go into the project. Name the proof by its job number and version (`proof 12345, v3`). The link carries a token that acts as the user.

## 6. Write the capture

`<name>.capture.ts` beside the spec, one shot per row on every device so the numbers pair, a comment with the row number before each shot. Follow [references/snapseq.md](references/snapseq.md). In short:

- Motion off first (`disableTransitions`), then hide what is not the page (a dev badge, a cookie banner the reference does not show) with `addPersistentStyle`, each with a comment saying why.
- `full` is `seq.snapPage()`, `top` is `seq.snap()`, each with `{ label: "<the row's Label>" }` when the row has one, spelled as the spec spells it. A page whose height follows the viewport (`100vh` sections) is `seq.snap({ fullPage: true })`; `snapPage` refuses it and says so.
- Wait for what the shot needs, a locator, never `networkidle`.
- A state that differs per device is a branch on `device` inside the row, so the row keeps its number. A state the reference has on one device only still takes one shot per row on the other device (its nearest equivalent, say the page with the menu closed): a skipped shot would shift every later number on that device.
- A menu, dialog or pop-up: open it, wait for it, shoot, close it, park the pointer at 0,0.
- Floating elements as the spec's table says, each with a comment naming what the reference shows: `hide` is a rule in the `addPersistentStyle` call; `closed` is a close in the helper that opens pages, after waiting for the element to appear; `pin` is a rule that turns `fixed` into `absolute` at the coordinate of the state the reference shows. The rules are under Floating elements in [references/snapseq.md](references/snapseq.md).
- A shot after an action that scrolled the page (a click below the fold, a form filled and sent): `await page.evaluate(() => scrollTo(0, 0))` first, unless the row wants the scrolled view. `tall` draws fixed elements where the scroll is, and an element a script positions rests where the last scroll event left it, in either full-page kind.
- Site helpers go in `helpers/` in the captures folder, one file per quirk, reused across captures.

## 7. Run and check

```bash
pnpm screenshot <name>                                      # every device; yarn the same; npm run screenshot -- <name> under npm
pnpm screenshot <name> --device desktop
pnpm screenshot <name> --headed                             # watch it
SNAPSEQ_RUN="<run>" pnpm screenshot <name> --device mobile  # rerun one device into the same run
pnpm --filter <app> screenshot <name>                       # from a monorepo root
```

1. Read `<run>/<name>/<device>/shots.txt` in the screenshots folder (the config's `screenshotsDir`, `.screenshots/` by default). A line containing `still` names a shot to check; `failed.png` is the page where a capture died.
2. Open the PNGs next to the reference's images: same page, same state, same extent; every floating element where the reference has it (mid-page, open or expanded only when the reference shows it so), none twice, a top bar at the top edge of every `full` shot whose reference has one (missing there means stranded further down), a sticky bar landed; no cookie banner unless the reference shows one; no hover left on a control; no blank band under the footer; the strip above every shot whose row has a Label, its text as the spec spells it, its height over the pixel ratio equal to the reference's. Compare heights, the reference's CSS height against the PNG height over the device's pixel ratio: a page much taller than the reference usually has a panel expanded; much shorter, a section that did not load, a menu the reference has open, or a reference taken from another build of the page; find the region that differs before changing the capture. A reference image carries a label strip at the top, and so does a shot with a label: measure from the content, not the image edge.
3. Fix the capture, not the numbers: a wait, a style, a route. Rerun that device into the same run.
4. A reference that is one document (a proof, a PDF) holding more than one of the run's PDFs: merge them back into one in its order, each job's `desktop.pdf` then its `mobile.pdf`, job by job, to `<run>/<reference>.pdf`, `<reference>` the proof's name or the PDF's filename as a slug. With the pdf-merge skill installed, run its script with the output first, then the inputs in that order, every path absolute and quoted (the run name has spaces); its total is the shots of every input. Without it, skip the merge and mention `npx skills add syantra/skills --skill pdf-merge`. A routes-only reference has no document to follow: no merge.
5. Report the run directory, shots per device, the merged PDF when step 4 made one, else the PDF per device (`<run>/<name>/<device>.pdf`); that is what the user uploads, the rows that differ from the reference and why, and any wait that ran out. A live site on a first run usually needs one of: a cookie banner hidden, an interstitial dismissed, a drawer that opens itself on load closed after every `goto`, a widget whose backend rejects automated sessions replayed from a recording, or a WAF that still returns 403 after snapseq's user-agent rewrite. Say which one you hit and what you did.
