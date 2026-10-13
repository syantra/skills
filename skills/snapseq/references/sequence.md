# The sequence spec

`captures/<name>.sequence.md` sits beside `captures/<name>.capture.ts`. One row per shot; the capture follows the file, the file does not follow the capture. Fill the angle brackets; drop a section that has nothing to say.

```markdown
# <Name> capture sequence

What `<name>.capture.ts` shoots, in order. One line per shot; the script follows
this file, this file does not follow the script. The rows are <the reference:
proof 12345 v3, pages 3–15 desktop and 16–28 the same rows on a phone; or
`<file>.pdf`, 20 pages; or the routes the owner listed on 2026-10-13>. The
script runs once per device, so a row is the same number in both folders:
`.screenshots/<run>/<name>/desktop/NNN.png` and `<name>/mobile/NNN.png`.
`<pm> screenshot <name>` runs both; `--device desktop` runs one.

## Shot kinds

| Kind   | Shows                                                                         | How                           |
| ------ | ----------------------------------------------------------------------------- | ----------------------------- |
| `top`  | the viewport as a visitor sees it: scroll 0 unless the row says otherwise     | `seq.snap()`                  |
| `full` | the whole page, sticky elements landed in flow, footer                        | `seq.snapPage()`              |
| `tall` | the whole page of a layout that follows the viewport height; sticky stays put | `seq.snap({ fullPage: true })` |

## Rules

- First lines of the capture: motion off (`disableTransitions`), then what
  every page hides (<a dev badge, a cookie banner>) with `addPersistentStyle`;
  both persist across navigations.
- Every row is exactly one shot on every device, so the numbers pair. <Row N
  is the only row whose action differs by device.>
- <One line per site quirk and how the capture handles it: the header menu
  opens on pointer travel, so `page.mouse.move` in steps, never `hover()`; the
  sticky tray must land before a `full`, so wait for `<selector>`; on dev the
  form's API sends no CORS header, so `helpers/<file>.ts` re-serves it; the
  search backend rejects automated sessions, so the env replays
  `captures/replay/<file>.json`.>
- The pointer parks at 0,0 after a row leaves it on a control.

## Rows

| Row | Reference page (desktop / mobile) | Route        | State        | Action                                        | Shot   |
| --- | --------------------------------- | ------------ | ------------ | --------------------------------------------- | ------ |
| 1   | 3 / 16                            | `/`          | default      | open                                          | `top`  |
| 2   | 4 / 17                            | `/`          | default      | the same page                                 | `full` |
| 3   | 5 / 18                            | `/`          | tab 2 open   | click the second tab                          | `full` |
| 4   | 10 / 23                           | `/find`      | dialog open  | click "Find a specialist", wait for the dialog | `top`  |

Not shots: <reference pages that are not captures and why: page 1 is the
cover, page 2 the sitemap diagram, pages 40–42 a document>.

## Elsewhere and later

- <Another capture of the same site: `<other>.sequence.md`, so its states
  cannot renumber these rows.>
- <What is deferred: the phone pass at 2x, the menu's expanded panels.>
```

Column meanings:

- **Reference page**: where the row is in the reference, desktop first. `-` when the reference has it on one device only; the row then says which.
- **Route**: the path under the env's host. From the code in a repo, from the navigation on a live site.
- **State**: `default`, or what differs from it (tab 2 open, menu open, form with errors). States of one page are rows of their own.
- **Action**: what the capture does to reach the state, in words a reader can check against the code. `desktop: …; mobile: …` when they differ.
- **Shot**: a kind from the table above.
