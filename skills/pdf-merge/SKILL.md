---
name: pdf-merge
description: Merge PDFs and images (JPEG, PNG, TIFF, WebP) into one PDF, pages in a chosen order, each page keeping its own size, images embedded without loss. Use whenever the user wants files combined, joined, compiled, bound or stitched into a single PDF, a folder of screenshots, scans or photos turned into one PDF, or pages from several PDFs put together, even if they never say merge.
license: ISC
compatibility: Needs uv (the script declares its own dependencies). Runs offline once they are installed.
metadata:
  version: "0.1"
---

# PDF merge

You put the user's PDFs and images into one PDF. One script does the work; your part is choosing the files, their order and the output, then reporting what came out.

```bash
uv run scripts/pdf_merge.py /abs/out.pdf /abs/a.pdf /abs/photo.jpg /abs/folder   # from this skill's folder, so give absolute paths
```

Pages come out in the order the inputs are given. A folder adds the PDFs and images directly in it, sorted by name with numbers in order (`2.png` before `10.png`); it skips subfolders, other files and hidden files, and lists what it skipped.

## 1. Choose the files and their order

- List what is there first (`ls`, or `find` for a tree). Merge only PDFs and images.
- Order: the order the user gave; otherwise name order, which is what a folder gives. When the names carry no order (files from different places, names without numbers) and the order matters, show the order you plan and ask once.
- A tree: pass its folders, or the files in them, in the order wanted. The script does not walk subfolders.
- The same pages twice: a folder that holds a PDF and the images it was made from (`report.pdf` beside `report/01.png`, `report/02.png`) would put every page in twice. Merge one or the other; when the request does not say which, ask.

## 2. Choose the output

The path the user names. Otherwise `<name>-merged.pdf` beside the inputs, after the folder or the first file, outside any folder you pass. The script refuses to write over an input, and over an existing file unless given `--force`; ask the user before passing it.

## 3. Run and report

The script prints each input with its page count, then the skipped files, then the total. Report the output path, the page total, and anything skipped that looks like it was meant to go in.

Sizing, which the user may ask about:

- A PDF page keeps its size.
- An image page takes the image's shape, sized from its DPI (72 when it has none), so a 300-DPI scan of an A4 page comes out A4. Nothing is cropped or padded to a paper size.
- A PDF page cannot be larger than 200 inches (14400 pt) in Acrobat. When an image page would be, every image page shrinks by the same factor, so screenshots of one width stay one width. The script prints the factor.
- JPEGs go in byte for byte. Other images go in lossless; transparency shows as white. A phone photo turned by its EXIF tag is placed upright, and lossless, so it takes more space than the JPEG.

## Limits

- A PDF that needs a password to open stops the run. Ask the user for an unlocked copy. PDFs locked only against editing merge as usual.
- HEIC and other formats are not read. Convert them to JPEG or PNG first (`sips -s format jpeg in.heic --out in.jpg` on macOS).
- Bookmarks are not carried over.
