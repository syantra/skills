# The sequence spec

`<name>.sequence.md` sits beside `<name>.capture.ts` in the captures folder (the config's `capturesDir`, `captures/` by default); `<screenshotsDir>` below is the screenshots folder (`screenshotsDir`, `.screenshots/` by default). One row per shot; the capture follows the file, the file does not follow the capture. Fill the angle brackets; drop a section that has nothing to say.

```markdown
# <Name> capture sequence

What `<name>.capture.ts` shoots, in order. One line per shot; the script follows
this file, this file does not follow the script. The rows are <the reference:
proof 12345 v3, pages 3–15 desktop and 16–28 the same rows on a phone; or
`<file>.pdf`, 20 pages; or the routes the owner listed on 2026-10-13>. The
script runs once per device, so a row is the same number in both folders:
`<screenshotsDir>/<run>/<name>/desktop/NN.png` and `<name>/mobile/NN.png`, and each
device's shots are bound into `<name>/<device>.pdf` beside its folder.
`<pm> screenshot <name>` runs both; `--device desktop` runs one (under npm:
`npm run screenshot -- <name> --device desktop`).

## Shot kinds

| Kind   | Shows                                                                         | How                           |
| ------ | ----------------------------------------------------------------------------- | ----------------------------- |
| `top`  | the viewport as a visitor sees it: scroll 0 unless the row says otherwise     | `seq.snap()`                  |
| `full` | the whole page, fixed elements at their anchors, sticky ones landed, footer    | `seq.snapPage()`              |
| `tall` | the whole page of a layout that follows the viewport height; fixed elements where the scroll pins them | `seq.snap({ fullPage: true })` |

## Rules

- First lines of the capture: motion off (`disableTransitions`), then what
  every page hides (<a dev badge, a cookie banner>) with `addPersistentStyle`;
  both persist across navigations.
- Every row is exactly one shot on every device, so the numbers pair. <Row N
  is the only row whose action differs by device.>
- <Every shot passes its row's Label; the reference's strip is dark grey on
  white, 24 CSS px at 2x, so the config has `label({ scale: true })`.>
- <One line per site quirk and how the capture handles it: the header menu
  opens on pointer travel, so `page.mouse.move` in steps, never `hover()`; the
  sticky tray must land before a `full`, so wait for `<selector>`; on dev the
  form's API sends no CORS header, so `helpers/<file>.ts` re-serves it; the
  search backend rejects automated sessions, so the env replays
  `captures/replay/<file>.json`.>
- The pointer parks at 0,0 after a row leaves it on a control.

## Rows

| Row | Reference page (desktop / mobile) | Route        | State        | Action                                        | Shot   | Label               |
| --- | --------------------------------- | ------------ | ------------ | --------------------------------------------- | ------ | ------------------- |
| 1   | 3 / 16                            | `/`          | default      | open                                          | `top`  | `Home`              |
| 2   | 4 / 17                            | `/`          | default      | the same page                                 | `full` | `Home`              |
| 3   | 5 / 18                            | `/`          | tab 2 open   | click the second tab                          | `full` | `Home, tab 2`       |
| 4   | 10 / 23                           | `/contact`   | dialog open  | click "Contact us", wait for the dialog        | `top`  | `Contact us`        |

Not shots: <reference pages that are not captures and why: page 1 is the
cover, page 2 the sitemap diagram, pages 40–42 a document>.

## Floating

What the survey listed, held against the reference. Treatments: `flow` (a
`full` shot lands it at its anchor), `hide` (the reference never shows it),
`closed` / `collapsed` (closed after every goto, before any shot), `pin` (kept
at the coordinate of the state the reference shows: a `top: 50%` tab, a `tall`
shot, a stranded bar).

| Element (survey line)                    | Anchor               | Reference shows                        | Treatment         |
| ---------------------------------------- | -------------------- | -------------------------------------- | ----------------- |
| `header.site-header`, fixed              | top 0, full width    | at the top of every shot               | `flow`            |
| `div.cookie-bar`, fixed                  | bottom 0, full width | at the page end on a `full`            | `flow`            |
| `aside.promo-flyout`, appears after load | right 0, mid-height  | its tab only, never the open panel     | `closed`          |
| `div.chat-bubble`, fixed                 | bottom 16, right 16  | never                                  | `hide`            |

## Elsewhere and later

- <What is deferred: the phone pass at 2x, the menu's expanded panels.>
- Not reproduced: <a state the reference carries that no row asked for: the
  menu its tool left open on the full pages, a back-to-top button mid-page>.
```

Column meanings:

- **Reference page**: where the row is in the reference, desktop first. `-` when the reference has it on one device only; the row then says which.
- **Route**: the path under the env's host. From the code in a repo, from the navigation on a live site.
- **State**: `default`, or what differs from it (tab 2 open, menu open, form with errors). States of one page are rows of their own.
- **Action**: what the capture does to reach the state, in words a reader can check against the code. `desktop: …; mobile: …` when they differ.
- **Shot**: a kind from the table above.
- **Label**: the text the reference prints above that capture, as written;
  `-` when it has none. `desktop: …; mobile: …` when the two differ.
- **Anchor**: the survey's place at scroll 0 and the edge it keeps in a taller viewport (`top 0, full width, anchored top`; `bottom 0`; `top 307, right 0, neither edge kept`).
- **Treatment**: a word from the Floating section, per row or per device when it differs (`row 1 flow, row 2 hide`; `desktop: closed`); the capture's comment on the rule or the close names the element.

## Rows from a reference

How a proof's page-by-page description (or a PDF read the same way) fills a row, once the pages are grouped (one capture per job, as SKILL.md step 2 says) and desktop and mobile pages are paired:

- The page's `label`, as written, is the row's Label; it or the page heading names the page.
- Its device and extent give the column and the Shot. Trust the measured height over the extent tag: a page tagged viewport but taller than every viewport height the reference uses is a `full`; one that matches the reference's other height stays a `top`, cut at the device's height, and the spec notes the difference.
- What changed from the page before tells a state (a tab, a menu open) from a new page.
- Its measured width and pixel ratio give the device sizes for a new config.
- Pages that are not captures (a cover, a sitemap diagram, a document) go under "Not shots".
- The `Labels:` line (the strip's colours and height) sets the `label()` options in the config, by the rule under Plugins in [snapseq.md](snapseq.md). A reference without strips has no `Labels:` line, and `label()` stays idle.
