# Describing a proof

Read this when the user asks how a proof is laid out, which site page a screenshot is, or wants the capture set taken again. Run:

```bash
uv run <skill-dir>/scripts/proofhq.py pages "<review-url>"
```

It returns `proof` (the proof's name, the job's title for any tool that needs one), `version`, `latestVersion`, and every page in order, each with its `bookmark` (if the file has one; reviewers may say "pg3" for a bookmark, not the page number), its `comments`, `images`: the page cut top to bottom into readable slices, and `thumb`: the whole page in one image (the slices side by side). `sourceFiles[].path` is the original uploaded file; give that path when the user wants the PDF.

For screenshots it also measures the capture: `px` (image size), `css` (size in CSS px), `dpr` (pixel ratio), `device` (`mobile` under 768 CSS px wide, else `desktop`), `extent` and `changedFrom`. They are null for diagrams and documents.

## Labels

A capture tool may print a label above a screenshot: a band of one colour at the top of the image holding one line of text, whatever the tool wrote there. Not every capture has one, and `pages` looks only at the top.

- `label`: the band's text, as written. The capture's `css` and `changedFrom` are measured below the band.
- `label` is read by OCR and can misread a character. The strip's text is the label: when `label` looks wrong, check it against the first slice. A `bookmark` is supporting evidence, never a replacement.
- `label` is null on a capture without a band, and on anything but macOS, where the text is not read: it is still visible at the top of the first slice.
- `labelStrip`: the band most captures share: `height` in CSS px, `bg` and `fg` as colour names (`white`, `dark grey`, `dark purple`).
- The band is found by shape alone, so a site whose own top is a thin bar with a line of text can be taken for one. `label` then holds that bar's text, and the capture's height is `px` over `dpr`.

## Steps

1. Open the first image of every page. It usually names the page: highlighted navigation item, page heading. A capture of an overlay (a menu, a drawer, a dialog) hides its page; it belongs to the page it was opened on, usually the page before.
2. Open further slices only to list sections, or to tell near-identical captures apart. Proofs often capture the same page several times in different states: a tab, accordion, carousel step or menu open. Long mobile pages have many slices; skip what you don't need. `changedFrom: {page, box}` gives the area, in CSS px, that differs from the page before at the same width: a small box is the control whose state changed; a box spanning the whole body (often stopping where a block every page shares begins: a pinned footer bar, the footer) means a different page. When the two heights differ, trust only the box's top edge.
3. Note the sticky and fixed elements (a pinned footer bar, a pinned header, a cookie banner) and where each sits: docked in the page flow (a `full` capture), floating at the viewport bottom (a `viewport` capture), or repeated at the seams of a stitched capture.
4. Write the description in this format, one or two lines per page:

```
Proof: <name> (v<version>), <project or job code if visible>

p<N>  <device> <width>@<dpr>x <extent> · <route or -> · <state> · <label or ->  <page name>: <sections top to bottom>.  comments <numbers or ->

Groups: <runs of pages, e.g. p2-p7 desktop, p8-p11 mobile, p12 menu state>
Same page across captures: <e.g. p3 = p9 (desktop / mobile)>
Sticky: <e.g. a pinned footer bar docked above the footer; header not pinned>
Labels: <fg on bg, height CSS px, from labelStrip; or none>
```

## Fields

- `<device>`, `<width>`, `<dpr>`, `<extent>`: the page's `device`, `css[0]`, `dpr` and `extent`. `extent` is `viewport` for a shot of the screen only, at whatever window height the capture used (a menu or drawer is often shot in a tall window, so its height is not a phone's), and `full` for the whole page. Diagrams and documents have no `css`; write `diagram` or `document` in place of those four.
- `<label>`: the capture's `label` as written, `-` when it has none.
- `<route>`: the page's URL path, found in the codebase by searching for the page heading or nav label; `-` if not found.
- `<state>`: `default` or what differs (tab 2 open, menu open).
- `Labels:` reports `labelStrip` by the names the script measured, never a hex value: `dark grey on white` is a plain strip, while a hue (`white on dark purple`) means the band is coloured, which is worth saying.

These fields are guesses from the image size. Confirm on `thumb`, or on the last slice when the thumb is too small to read: a footer at the bottom means `full`.

This description is the input when the user wants the capture set taken again; see Reproducing the capture set in [SKILL.md](../SKILL.md).
