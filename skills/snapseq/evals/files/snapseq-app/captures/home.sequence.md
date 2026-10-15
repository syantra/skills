# Home capture sequence

What `home.capture.ts` shoots, in order. One line per shot; the script follows
this file, this file does not follow the script. The rows are the reference's
pages 2-6 on desktop and 7-11 the same rows on a phone. The script runs once
per device, so a row is the same number in both folders:
`.screenshots/<run>/home/desktop/NN.png` and `home/mobile/NN.png`.

## Shot kinds

| Kind   | Shows                                              | How                            |
| ------ | -------------------------------------------------- | ------------------------------ |
| `top`  | the viewport as a visitor sees it                  | `seq.snap()`                   |
| `full` | the whole page, fixed elements at their anchors    | `seq.snapPage()`               |

## Rules

- Motion off first (`disableTransitions`).
- Every row is exactly one shot on every device, so the numbers pair. Row 5 is
  the only row whose action differs by device.
- Every shot passes its row's Label.
- Pages open through `helpers/open-page.ts`.
- The reference's full pages measure 2555 CSS px tall at both widths.

## Rows

| Row | Reference page (desktop / mobile) | Route      | State                                          | Action                                         | Shot   | Label                   |
| --- | --------------------------------- | ---------- | ---------------------------------------------- | ---------------------------------------------- | ------ | ----------------------- |
| 1   | 2 / 7                             | `/`        | default                                        | open                                           | `top`  | `Home`                  |
| 2   | 3 / 8                             | `/`        | default                                        | the same page                                  | `full` | `Home`                  |
| 3   | 4 / 9                             | `/pricing` | default                                        | open                                           | `full` | `Pricing`               |
| 4   | 5 / 10                            | `/docs`    | Contact link focused                           | focus the footer's "Contact" link              | `full` | `Docs, Contact focused` |
| 5   | 6 / 11                            | `/`        | mobile: menu open; desktop: header as it is    | mobile: click "Menu", wait for the menu        | `top`  | `Home, menu`            |

Not shots: reference page 1 is the cover.
