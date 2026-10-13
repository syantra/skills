# snapseq rules

snapseq 0.2.0 is a set of Playwright Test fixtures for scripted screenshot captures: a capture is a Playwright test, and snapseq numbers its shots per run, capture and device.
Full docs: `https://github.com/syantra/snapseq/blob/main/docs/<file>.md`. Each section ends with `Docs: <file>.md`.

## Install and files

```bash
pnpm add -D @playwright/test snapseq
pnpm exec playwright install chromium
```

Install in the app that owns the pages. In a monorepo, each app gets its own install and its own config.
The browser install is once per machine. Under Node 26 it hangs: run it under Node 22 (`nvm use 22`). Captures run under any supported Node.
Add the script `"screenshot": "snapseq"` to `package.json`, then run `pnpm screenshot`. Config: `snapseq.config.ts` beside `package.json`. Captures: one file each in `captures/`.

```
.screenshots/                  snapseq writes a .gitignore inside it
  2026-10-01 at 4.07.16 PM/    one directory per run, local start time
    pricing/desktop/001.png
    pricing/desktop/shots.txt  one line per shot: file and URL
    pricing/mobile/...
```

Docs: getting-started.md

## Config

`snapseq.config.ts` default-exports `defineConfig()`, a Playwright Test config. The command finds it in the current directory, or takes `-c <path>`.

```ts
import { defineConfig } from "snapseq";
export default defineConfig({
  envs: {
    dev: { host: "http://localhost:3000", webServer: "pnpm dev" },
    prod: { host: "https://www.example.com", replay: { "**/api/search": "captures/replay/search.json" } },
  },
  devices: { desktop: { viewport: { width: 1920, height: 1080 } } },
});
```

| Field | Default | Notes |
| --- | --- | --- |
| `envs` | required | One entry per environment. |
| `defaultEnv` | `"dev"` if present, else the first env | Used when neither `--env` nor `SNAPSEQ_ENV` is given. |
| `devices` | desktop (1920x1080) and mobile (390x844, 2x, touch) | One Playwright project per key. |
| `capturesDir` | `"captures"` | Relative to the config file. Matches `*.capture.ts`. |
| `screenshotsDir` | `".screenshots"` | Relative to the config file. |
| `numbering` | `"000"` | Shape of a shot number: `"0000"` gives `0001.png`. Zeros only. Make it wide enough for the longest capture: `100.png` sorts before `99.png`. |

Env fields:

| Field | Notes |
| --- | --- |
| `host` | Base URL; `page.goto("/pricing")` resolves against it. `--host` or `SNAPSEQ_HOST` overrides it for one run. |
| `httpCredentials` | Basic auth, offered to the host's origin only (an overridden host counts). Playwright's `origin` field sends them to another origin, e.g. a host that redirects behind the same password. |
| `webServer` | Command that serves `host`. |
| `use` | This env's Playwright options, merged over the defaults: `extraHTTPHeaders`, `storageState`, `locale`, `bypassCSP`. Put a per-env option here, not in an override. |
| `replay` | Requests answered from recorded files instead of this env's backend. |

Dev server: the `webServer` command runs from the config file's directory and must listen on `host`. If `host` already passes Playwright's readiness check (2xx, 3xx or 400-403 after redirects), it is reused and the command is not started. Otherwise the command starts, with up to 120 s to become ready, and stops when the run ends, Ctrl-C included. An overridden host (`--host`, `SNAPSEQ_HOST`) never starts it. stdout is hidden, stderr shown; `DEBUG=pw:webserver` shows everything.

Devices: one Playwright project per key. The value is that project's `use` options, so `devices["iPhone 14"]` from `@playwright/test` works. The key is the directory name under each capture, the `device` fixture value, and what `--device` selects. It must be a directory name, not a path.

Replay, for a request the env cannot answer (bot check, charged per call, backend down):
- Each key is a `page.route` URL pattern, each value a JSON file relative to the config file. Before every capture, snapseq answers the pattern from the file; the rest of the page stays live. A missing file fails the run before its first shot and names the file.
- `pnpm screenshot --record` (or `SNAPSEQ_RECORD=1`) fetches each request live, writes its file and answers with it. Only an env with `replay` is affected.
- Record against a host where the request works, check the shot, commit the file: `pnpm screenshot --env prod --record --host https://staging.example.com`, then `pnpm screenshot --env prod`.
- JSON bodies only. Anything else goes through `page.routeFromHAR` in the capture.

Playwright defaults applied by `defineConfig`:

| Option | Value | Why |
| --- | --- | --- |
| `workers` | 1 | Captures run one at a time, in order. |
| `timeout` | 10 min | Time allowed between shots, not per capture. |
| `actionTimeout` | 30 s | Per click, fill and wait. |
| `navigationTimeout` | 120 s | Allows a cold dev build; ends a `goto` that never settles. |
| `maxFailures` | 1 | Fail fast. `--max-failures 0` runs the rest. |
| `retries` | 0 | A retry would overwrite shots. Retries and `--repeat-each` are rejected. |
| `ignoreHTTPSErrors` | true | Self-signed staging certificates. |
| `userAgent` | `HeadlessChrome` rewritten to `Chrome` | Some WAFs 403 the headless token. Not rewritten if you set `userAgent`. |
| `outputDir` | `node_modules/.cache/snapseq` | Traces and error context stay out of the screenshots dir. |

Overrides: extra arguments to `defineConfig` are Playwright options merged underneath, e.g. `defineConfig({ envs }, { workers: 2, use: { launchOptions: { args: ["--lang=de"] } } })`. `use` is merged, the rest replaced; `webServer` entries concatenate; nested objects such as `launchOptions` are replaced whole. To drop a generated `webServer`, use `{ ...defineConfig({ /* ... */ }), webServer: undefined }`.

Docs: config.md, running.md

## Writing a capture

```ts
// captures/pricing.capture.ts
import { capture, disableTransitions } from "snapseq";

capture(async ({ page, seq, device }) => {
  await disableTransitions(page);                 // once, before the first goto
  await page.goto("/pricing");                    // relative to host
  await seq.snap();                               // 001.png  viewport
  await seq.snapPage();                           // 002.png  whole page
  if (device === "mobile") {
    await page.getByRole("button", { name: "Menu" }).click();
    await page.getByRole("navigation").waitFor(); // what the shot needs, then the shot
    await seq.snap();                             // 003.png  mobile only
  }
});
```

- The file name is the capture name: `captures/pricing.capture.ts` writes `.screenshots/<run>/pricing/<device>/`. Folders nest: `captures/campaign/pricing.capture.ts` writes `<run>/campaign/pricing/<device>/`.
- One `capture()` per file. A shot's number is its position in the file, so a second capture is a second file. Files not ending in `.capture.ts` are not captures: put helpers in `captures/helpers/`.

Fixtures, beyond Playwright's own (`page`, `context`, `browser`):

| Fixture | Value |
| --- | --- |
| `seq` | The shot sequence: `snap`, `snapPage`, `dir`. |
| `device` | The `devices` key this run is on, e.g. `"mobile"`. |
| `env` | The active env name, e.g. `"dev"`. |
| `host` | The resolved base URL. |
| `ctx` | All of the above plus `page`, for helpers that take a `CaptureContext`. |

Skipping:
- Top of file, decided before any fixture runs, so skipped devices get no directory: `skipIf(({ device }) => device !== "desktop", "desktop only");`
- Inside the body, for a condition learned mid-capture: `skipIf(condition, reason)`. The reason shows on the capture's terminal line.

A state that flips (a menu closes on navigation): put the precondition in the helper that takes the shot, so every call gets it. Call it as `await snapMenuOpen(ctx)`.

```ts
// captures/helpers/snap-menu.ts
import type { CaptureContext } from "snapseq";
export async function snapMenuOpen({ page, seq }: CaptureContext): Promise<string> {
  await page.getByRole("button", { name: "Menu" }).click();
  await page.getByRole("navigation").waitFor();
  return seq.snap();
}
```

Docs: captures.md, examples.md

## Shots

- `seq.snap()`: the viewport.
- `seq.snapPage()`: the viewport grows to the document height, so sticky and fixed elements rest in flow and a tray whose slot comes into view lands. One shot, viewport restored. Right for a sticky tray that docks and lands at the page end.
- `seq.snap({ fullPage: true })`: Playwright's native full page. The viewport stays, so sticky elements stay pinned where the scroll left them. Right for a layout that follows the viewport height (`100vh` hero, `vh` units, a loader pinned to the page end).
- `snapPage` measures once more after the viewport is set and refuses such a page, viewport restored: `snapPage: the document grew from 2140 to 3220 px after the viewport was set to its height ... Use snap({ fullPage: true }) for this page.`
- Both take Playwright's screenshot options (`mask`, `clip`, `style`, `omitBackground`, ...) except `path` and `type`, which the sequence owns. Both resolve to the PNG path.

Docs: captures.md, examples.md

## Waiting

Every shot first waits, in this order: DOM quiet (no mutation for 200 ms, 3 s cap, then a painted frame); fonts (`document.fonts.ready`, 5 s cap); images (every `<img>`, lazy ones made eager, 5 s cap for the lot); DOM quiet again.
A wait that ran out is noted on the shot's `shots.txt` line (`007.png  http://...  2 images still loading after 5 s`) and printed once in the terminal. A ready shot says nothing.
The wait does not see: a state that lands after the DOM was quiet for 200 ms (a late fetch); video, canvas, CSS backgrounds, iframes, shadow trees; motion that never touches the DOM (Web Animations API); anything while `page.clock` is paused.
Wait for those yourself, before the shot: a locator (`await page.locator(".chart svg path").first().waitFor()`) or a bounded `page.evaluate`. Wait for what the shot needs, not `networkidle`. A page that polls or streams never goes idle, and `goto` runs to the 120 s bound.
`page.evaluate` has no timeout of its own. Race every in-page wait against a timer, or the capture dies 10 min after its last shot.
Use arrow functions only inside `page.evaluate`, `locator.evaluate` and `addInitScript`. A named function gets a `__name()` wrapper that does not exist in the page (`ReferenceError: __name is not defined`).

Docs: captures.md, examples.md, troubleshooting.md

## Helpers

- `disableTransitions(page)`: no transitions, animations or smooth scrolling, on this document and every one the page navigates to later. Call it once per capture, before the first `goto`.
- `addPersistentStyle(page, css)`: the same persistence for your own CSS, e.g. `addPersistentStyle(page, "#chat-widget { display: none !important }")`.
- Both inject a `<style>` element. A strict `style-src` blocks it: set `use: { bypassCSP: true }` for that site (on the env or composed over the config).

Docs: captures.md, troubleshooting.md

## Site quirks

- Dev API without CORS (widget stays a skeleton on dev, fine on staging): `await page.route("https://api.example.com/**", async (route) => { await route.fulfill({ response: await route.fetch() }); })`. Playwright adds the header and answers preflights. Gate it with `env === "dev"`.
- API sends a wrong `access-control-allow-origin`: `const res = await route.fetch();` then `route.fulfill({ response: res, headers: { ...res.headers(), "access-control-allow-origin": new URL(host).origin } })`.
- Backend rejects automated sessions, charges per call or is down: give the env a `replay` entry and record it once. The capture stays what a user does.
- 403 or error page from the headless user agent: snapseq already rewrites `HeadlessChrome` to `Chrome`. If you set `userAgent`, keep it realistic.
- Device-only state: branch on `device` in the body. The other device gets fewer shots.
- A menu that opens on pointer travel needs stepped `page.mouse.move`, not `locator.hover()`.
- An element that opens itself on load (a promo drawer, a chat bubble): close it after every `goto`, in the helper that opens pages, so every row starts from the reference's state.
- A fixed element (a sticky bar, a drawer tab) covers a control's hit area on a phone wherever it scrolls, so `click()` times out on "intercepts pointer events": `locator.dispatchEvent("click")` sends the click to the element itself, which the page handles the same.
- A video frame: pause, set `currentTime`, then race `seeked` against a 5 s timer inside `video.evaluate`, so a video that never seeks cannot hang the capture.
- What changes between runs: `seq.snap({ mask: [page.locator("time")], maskColor: "#888" })`.

Docs: captures.md, examples.md, troubleshooting.md

## Running

Forms: `pnpm screenshot pricing --device mobile`, `pnpm screenshot --env staging`, `SNAPSEQ_RUN=review-1 pnpm screenshot`. From a monorepo root: `pnpm --filter <app> screenshot pricing --device desktop`.

| Flag | Variable | Effect |
| --- | --- | --- |
| `[filter...]` | | Playwright's file filter: captures whose path matches. |
| `--env <name>` | `SNAPSEQ_ENV` | The env from the config. Default: `defaultEnv`, else `dev`, else the first. |
| `--host <url>` | `SNAPSEQ_HOST` | Override that env's host for this run. Its `webServer` is not started. |
| `--device <name>` | | Only this device; repeatable. Playwright's `--project`. |
| `--record` | `SNAPSEQ_RECORD` | Fetch the env's `replay` requests live and write their files. |
| `-c, --config <path>` | | Config file. Default: `./snapseq.config.{ts,mts,cts,js,mjs,cjs}`. |
| | `SNAPSEQ_RUN` | Run directory name. Default: local start time. A name, not a path. |

The flag wins over the variable. An empty value (`--env ""`) means unset. Everything else goes to `playwright test`: `--headed`, `--ui`, `--debug`, `--trace on`, `--reporter json`, `--max-failures 0`, `--last-failed`. Traces land in `node_modules/.cache/snapseq`.

Run directories:
- A capture's `<capture>/<device>` directory is wiped when that capture starts. A directory outside the screenshots dir is never wiped.
- A failed or timed-out capture leaves `failed.png` beside its shots (the page as teardown found it, 5 s at most) and a `failed.png` line in `shots.txt`. The run stops there (`maxFailures: 1`).
- Rerun into the same run: `SNAPSEQ_RUN="<run>" pnpm screenshot --last-failed`. It is not a resume: captures that never ran are not included, and a rerun capture starts at `001.png` again. Run those by name with the same `SNAPSEQ_RUN`.

Terminal: an interactive run draws one live frame, one line per capture and device, then a summary, and opens the run directory in Finder (Explorer on Windows). When stdout is not a terminal (CI, a pipe, `--list`, `--debug`) it uses Playwright's list reporter, one line per shot with file and URL, and never opens a window. `--reporter list` overrides the default. `NO_COLOR` or `FORCE_COLOR=0` drops colors.

Docs: running.md, config.md, examples.md

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| Animations still run, or `addPersistentStyle` / `page.addStyleTag` throws | Strict `style-src` rejects the injected `<style>`. Set `use: { bypassCSP: true }` for that site. |
| `ReferenceError: __name is not defined` | A named function inside `page.evaluate`. Arrow functions only. |
| `No shot for 10 min.`, stack in a `page.evaluate` | The callback awaited an event that never fired. Race every in-page wait against a timer. |
| 403 or error page in the shot, fine in a browser | Headless token rejected. snapseq rewrites it; keep any custom `userAgent` realistic. Check CORS if the page's API calls fail. |
| `playwright install chromium` hangs | Node 26. Run the install under Node 20 or 22 (`nvm use 22`), once per machine. |
| `page.goto: Timeout 120000ms exceeded.` | Usually `networkidle` on a polling page, or a cold dev build. Drop `networkidle`, wait for a locator. For a slow build, warm the server or raise `navigationTimeout` in the env's `use`. |
| `shots.txt` says a wait ran out (`images still loading`, `fonts still loading`, `DOM still changing after 3 s`) | The cap hit and the shot was taken anyway; it may be fine. Else hide or stop the moving part with `addPersistentStyle`, route the stalled asset with `page.route`, or wait for the state. |
| `snapPage: the document grew from ... px` | Layout follows the viewport height. Use `seq.snap({ fullPage: true })` for that page. |
| Sticky bar sits mid-page in a full-page shot | `snap({ fullPage: true })` keeps the viewport. Use `seq.snapPage()`. |
| Shot caught an animation mid-frame | `disableTransitions` missing, or Web Animations API motion. Call it once before the first `goto`; for WAAPI wait for the final state with a locator, or `Promise.all(document.getAnimations().map((a) => a.finished))` raced against a timer. |
| Basic auth not sent, or sent to the wrong host | Credentials go to the host's origin only. A redirect to another origin needs Playwright's `origin` on `httpCredentials`. An overridden host counts automatically. |
| `snapseq: unknown env "..."` | Use a name listed in `envs`, or `--env ""` for the default. |
| `snapseq: SNAPSEQ_RUN must be a directory name, not a path` | Use a plain name (`review-1`), no slash, not `.` or `..`. Same rule for device names. |
| `snapseq: --repeat-each and retries are not supported` | A second run would overwrite the first. Use a new run directory; wait for the state instead of retrying. |
| `snapseq: the Playwright config must come from snapseq's defineConfig()` | Wrong `-c <path>` or a plain Playwright config picked up. Point at `snapseq.config.ts`; pass Playwright options as the second argument to `defineConfig`. |
| Dev server starts although one runs, or never starts | Readiness is 2xx, 3xx or 400-403 at `host`; another port or a 404/5xx root does not count. `--host` never starts it. Match `host` to the listening port, or start it yourself and pass `--host`. |
| No live terminal view, one line per shot | Stdout is not a terminal, or `--list`, `--debug`, `PWDEBUG`, `TERM=dumb`. None needed. Words (`ok`, `FAIL`) mean the terminal cannot draw marks. |
| `snapseq: no replay file for ...` | Record it: `pnpm screenshot --record` against a host where the request works (`--host`), check the shot, keep the file. |
| Whole widget missing on dev, present on staging | CORS. Re-serve the API through `page.route` on dev (see Site quirks). |

Docs: troubleshooting.md
