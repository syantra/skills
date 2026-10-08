"""Original uploaded files: download once into the cache, read their bookmarks."""
import urllib.request
from pathlib import Path

import pypdfium2 as pdfium

CACHE = Path.home() / ".cache/workfront-proof"


def source_file(token, start, page):
    """Download (once) the original file that holds this page -> (path, 0-based page in file, mime)."""
    for f in start["proof"]["sourceFiles"]:
        if f["pagesFrom"] <= page <= f["pagesTo"]:
            path = CACHE / token / f["name"]
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                tmp = path.with_suffix(".part")
                urllib.request.urlretrieve(f["url"], tmp)
                tmp.rename(path)
            return path, page - f["pagesFrom"], f["mime"]
    raise SystemExit(f"No source file covers page {page}.")


def bookmarks(path, mime):
    """PDF bookmarks -> {0-based page in file: title}; the last bookmark wins when several share a page."""
    if mime != "application/pdf":
        return {}
    return {b.get_dest().get_index(): b.get_title() for b in pdfium.PdfDocument(path).get_toc() if b.get_dest()}
