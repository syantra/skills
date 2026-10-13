---
name: snapseq
description: Set up and run a snapseq screenshot capture set, so a site's pages come out as numbered desktop and mobile screenshots on disk, scripted with Playwright and repeatable. Use whenever the user wants screenshots of a site's pages or of a review proof's pages (a page set, a capture set) taken or taken again, a capture written or fixed, or snapseq installed in a repo, a monorepo app or a standalone folder, even if they never say snapseq. Starts by assessing the directory, then writes the spec, the capture, and runs it.
license: ISC
compatibility: Needs uv for the setup script, Node 20+ with pnpm, yarn or npm, network access to the npm registry and to the site, and Chromium through Playwright (installed under Node 22 when the machine runs Node 26).
metadata:
  version: "0.1"
---

# snapseq

You set up and run a screenshot capture set with snapseq, a Playwright Test fixture package: one capture file per page set, every shot numbered, one folder per device, saved on disk. What to shoot comes from a reference: a review proof, a PDF, or a list of routes. Nothing leaves the machine. You take the shots and report the run directory; the user uploads them.

The rules a capture must follow are in [references/snapseq.md](references/snapseq.md). Read it before writing one.

## 1. Assess the directory, always first

```bash
uv run scripts/snapseq_setup.py assess /abs/path/to/dir      # from this skill's folder, so give dir as an absolute path
```

It prints JSON: `root`, `packageManager`, `workspace`, every `apps[]` record (framework, dev command and `port`, `snapseq` and `playwright` versions, `config`, existing `captures` and `sequences`), `node`, `node22`, `chromium`, and a `verdict`:

- `reuse`: `app` already has snapseq. Nothing to install.
- `add-to`: `app` is a package without snapseq. Install there.
- `standalone`: no package here. Make a folder of its own.

`app` is relative to `root`; `appPath` is the same app as an absolute path, which is what `init --app` takes. The app the directory is inside always wins. `choose` lists candidate apps when the script cannot pick one. Pick the app that serves the reference's pages if the routes make it obvious; otherwise ask the user, one question. Say the verdict in one line before going on.

## 2. Set up

**reuse.** Read the app's `snapseq.config.ts`, every file under `captures/` and every `*.sequence.md`. They hold the site's quirks (a tray that must land, a menu that opens only on pointer travel, an API without CORS on dev) and the helpers that handle them. Reuse those; do not write a second helper for a solved quirk.

**add-to.**

```bash
uv run scripts/snapseq_setup.py init --app <appPath>             # host from the dev script's port, webServer "<pm> dev"
uv run scripts/snapseq_setup.py init --app <appPath> --host http://localhost:4000 --dev-command "pnpm dev --port 4000"
```

**standalone.**

```bash
uv run scripts/snapseq_setup.py init --standalone <dir> --host https://www.example.com \
  --device desktop=1728x890@2 --device mobile=430x803@2+touch
```

- `<dir>`: a new folder in the current directory named `<site>-screenshots` (`example-screenshots`), unless the user names one. Never inside another project's repo.
- Devices: in a repo the config's devices stand, whatever the reference measures. Standalone, match the reference when it measured its captures (a proof's `css` width and `dpr`; the height only matters for viewport shots); with no measurement, pass no `--device` and snapseq's defaults apply (1920×1080, 390×844 at 2x).
- The script runs `install` and the Chromium install, under Node 22 when the machine is on Node 26 and nvm has a 22. If it says it skipped the browser, tell the user the command to run.

Add `--no-install` to write the files only. The script refuses to overwrite an existing config.

## 3. Write the spec before any code

`captures/<name>.sequence.md`, one row per shot in reference order; the capture follows the file, never the other way round. The template is [references/sequence.md](references/sequence.md). `<name>` is short and names the page set (`home`, `cost-savings`, the proof's job number).

Rows come from the first of these that applies:

1. **A review proof.** With the workfront-proof skill installed (`workfront-proof/SKILL.md` where this agent's skills live, such as `~/.claude/skills` or `.claude/skills`), run its `pages` command and use its page-by-page description. Without it, do not guess at the proof: ask the user for the proof's exported PDF or page images and read those, and mention that `npx skills add syantra/skills --skill workfront-proof` reads proofs directly. Any other tool that gives the same per-page facts (device, width and pixel ratio, extent, what changed between captures) serves as well. Every capture page is a row: its label or heading names the page, its device and extent give the column and the shot kind, what changed from the page before tells a state capture (a tab, a menu open) from a new page, and its measured width and pixel ratio give the device sizes for a standalone setup. Pages that are not captures (a cover, a sitemap diagram, a document) go under "Not shots".
2. **A PDF or images the user gives.** Read them page by page the same way.
3. **Routes the user lists.** One row each, `full` unless told otherwise.
4. **Nothing.** Open the host, read the primary navigation and `/sitemap.xml` or the sitemap page, and propose rows. Show the table and ask once before writing the capture.

`Route` comes from the code in a repo (search for the page heading or nav label) or from the navigation links on a live site. `State` and `Shot` come from the reference. `Action` comes from the page: find the control by role and visible name in the HTML (`curl -sL <url>`, or the component in the repo).

Privacy: the proof link, reviewer names and comment text never go into the project. Name the proof by its job number and version (`proof 12345, v3`). The link carries a token that acts as the user.

## 4. Write the capture

`captures/<name>.capture.ts`, one shot per row on every device so the numbers pair, a comment with the row number before each shot. Follow [references/snapseq.md](references/snapseq.md). In short:

- Motion off first (`disableTransitions`), then hide what is not the page (a dev badge, a cookie banner) with `addPersistentStyle`, each with a comment saying why.
- `full` is `seq.snapPage()`, `top` is `seq.snap()`. A page whose height follows the viewport (`100vh` sections) is `seq.snap({ fullPage: true })`; `snapPage` refuses it and says so.
- Wait for what the shot needs, a locator, never `networkidle`.
- A state that differs per device is a branch on `device` inside the row, so the row keeps its number. A state the reference has on one device only still takes one shot per row on the other device (its nearest equivalent, say the page with the menu closed), or goes in a capture of its own: a skipped shot would shift every later number on that device.
- A menu, dialog or pop-up: open it, wait for it, shoot, close it, park the pointer at 0,0.
- Site helpers go in `captures/helpers/`, one file per quirk, reused across captures.

## 5. Run and check

```bash
pnpm screenshot <name>                                      # every device; yarn or npm as the repo uses
pnpm screenshot <name> --device desktop
pnpm screenshot <name> --headed                             # watch it
SNAPSEQ_RUN="<run>" pnpm screenshot <name> --device mobile  # rerun one device into the same run
pnpm --filter <app> screenshot <name>                       # from a monorepo root
```

1. Read `.screenshots/<run>/<name>/<device>/shots.txt`. A line ending in `still loading` or `still changing` names a shot to check; `failed.png` is the page where a capture died.
2. Open the PNGs next to the reference's images: same page, same state, same extent; the sticky tray landed; no cookie banner; no hover left on a control; no blank band under the footer.
3. Fix the capture, not the numbers: a wait, a style, a route. Rerun that device into the same run.
4. Report the run directory, shots per device, the rows that differ from the reference and why, and any wait that ran out.

A live site on a first run usually needs one of: a cookie banner hidden, an interstitial dismissed, a drawer that opens itself on load closed after every `goto`, a widget whose backend rejects automated sessions replayed from a recording, or a WAF that still returns 403 after snapseq's user-agent rewrite. Say which one you hit and what you did.
