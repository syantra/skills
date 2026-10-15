# /// script
# requires-python = ">=3.10"
# ///
"""Check for floating.mjs: syntax and usage always; the live survey against a fixture page
when SNAPSEQ_PLAYWRIGHT_DIR names a directory whose node_modules has @playwright/test.

Run: uv run skills/snapseq/tests/test_floating.py
"""
import os
import subprocess
import sys
import tempfile
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "floating.mjs"

# One of each kind the survey must tell apart. Viewport 800x600, page 4080 tall.
FIXTURE = """<!doctype html><html><head><style>
  body { margin: 0 }
  .spacer { height: 1000px }
  #header { position: fixed; top: 0; left: 0; right: 0; height: 60px; background: #333 }
  #nested { position: fixed; top: 70px; left: 0; width: 100px; height: 20px; background: #999 }
  #promo { position: absolute; top: 60px; left: 0; right: 0; height: 40px; background: #cc3 }
  #hider { position: fixed; top: 100px; left: 0; width: 100px; height: 30px; background: #33c }
  #tab { position: fixed; top: 300px; right: 0; width: 40px; height: 200px; background: #c33 }
  #center { position: fixed; top: 50%; left: 0; width: 60px; height: 40px; background: #c3c }
  #flyout { position: fixed; bottom: 20px; right: 20px; width: 200px; height: 100px; background: #3c3; display: none }
  #slide { position: fixed; bottom: 200px; right: -200px; width: 200px; height: 100px; background: #3cc }
  #totop { position: fixed; bottom: 20px; left: 20px; width: 40px; height: 40px; background: #000; display: none }
  #tray { position: sticky; bottom: 0; height: 80px; background: #ccc }
  #cookie { position: absolute; top: 200px; left: 100px; width: 600px; height: 300px; background: #fff; display: none }
  #latch { height: 50px; left: 0; right: 0; background: #693 }
  #drawer { position: absolute; top: 400px; left: -200px; width: 200px; height: 100px; background: #963 }
  #consent { position: absolute; top: 100px; left: 100px; width: 300px; height: 100px; background: #fff; display: none }
</style></head><body>
  <div style="height: 50px"><div id="latch"></div></div>
  <div id="header"><div id="nested"></div></div><div id="promo"></div><div id="hider"></div><div id="tab"></div>
  <div id="center" class="top-1/2"></div><div id="flyout"></div><div id="slide"></div><div id="totop"></div><div id="cookie"></div>
  <div id="drawer"></div><div id="consent"></div>
  <div class="spacer"></div><div id="tray"></div><div class="spacer"></div><div class="spacer"></div><div class="spacer"></div>
  <script>
    setTimeout(() => {
      document.getElementById("flyout").style.display = "block";   // opens itself
      document.getElementById("slide").style.right = "0";          // slides in from off-screen
      document.getElementById("cookie").style.display = "block";   // an absolute overlay, late
    }, 1500);
    let last = 0;
    addEventListener("scroll", () => {
      if (scrollY > last) document.getElementById("promo").style.top = scrollY + 60 + "px";  // follows the scroll down only
      document.getElementById("hider").style.transform = scrollY > 0 ? "translateY(-200px)" : "";  // hides itself when scrolled
      document.getElementById("totop").style.display = scrollY > 100 ? "block" : "none";  // appears when scrolled
      const latch = document.getElementById("latch").style;
      latch.position = scrollY > 100 ? "fixed" : "static";  // static until scrolled
      latch.top = scrollY > 100 ? "0" : "";
      document.getElementById("drawer").style.left = scrollY > 0 ? "0" : "-200px";  // slides in sideways when scrolled
      if (scrollY > 100) document.getElementById("consent").style.display = "block";  // an absolute overlay, on first scroll
      last = scrollY;
    });
  </script>
</body></html>"""

# A page that fits the viewport: scrolling does nothing.
SHORT = """<!doctype html><html><head><style>
  body { margin: 0 }
  #header { position: fixed; top: 0; left: 0; right: 0; height: 60px; background: #333 }
</style></head><body><div id="header"></div><div style="height: 100px"></div></body></html>"""

check = subprocess.run(["node", "--check", str(SCRIPT)], capture_output=True, text=True)
assert check.returncode == 0, check.stderr
usage = subprocess.run(["node", str(SCRIPT)], capture_output=True, text=True)
assert usage.returncode == 2 and "usage:" in usage.stderr, usage
assert subprocess.run(["node", str(SCRIPT), "--help"], capture_output=True).returncode == 0
assert subprocess.run(["node", str(SCRIPT), "http://x/", "--wait", "soon"], capture_output=True).returncode == 2
for bad in (["http://x/", "--waait", "2"], ["http://x/", "--device", "0x600"], ["--wait", "2"], ["--device", "800x600", "--wait", "2"],
            ["http://x/", "--http-credentials", "nocolon"], ["http://x/", "--http-credentials"]):
    r = subprocess.run(["node", str(SCRIPT), *bad], capture_output=True, text=True)
    assert r.returncode == 2 and "usage:" in r.stderr, (bad, r)

pw_dir = os.environ.get("SNAPSEQ_PLAYWRIGHT_DIR")
if not pw_dir:
    print("skip: live survey; set SNAPSEQ_PLAYWRIGHT_DIR to a directory with @playwright/test")
    print("ok")
    sys.exit(0)


def survey(url):
    return subprocess.run(
        ["node", str(SCRIPT), url, "--device", "800x600", "--wait", "3"],
        cwd=pw_dir, capture_output=True, text=True, timeout=120,
    )


with tempfile.TemporaryDirectory() as t:
    (Path(t) / "index.html").write_text(FIXTURE)
    (Path(t) / "short.html").write_text(SHORT)
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=t))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}/"
    try:
        run = survey(base)
        short = survey(base + "short.html")
        missing = survey(base + "missing.html")
    finally:
        server.shutdown()

assert missing.returncode == 1 and "HTTP 404" in missing.stderr and "viewport" not in missing.stdout, missing
assert short.returncode == 0, short.stderr
assert "not scrolled" in {line.split()[0]: line for line in short.stdout.splitlines()[2:]}["div#header"], short.stdout
assert run.returncode == 0, run.stderr
out = run.stdout
lines = out.splitlines()[2:]
keys = [line.split()[0] for line in lines]
rows = dict(zip(keys, lines))
CENTER = "div#center.top-1\\/2"                                                    # the label is a valid selector
assert out.startswith("viewport 800x600  document 4130 px"), out
assert "fixed to the viewport" in rows["div#header"] and "top 0, full width" in rows["div#header"], out
assert rows["div#header"].rstrip().endswith("anchored top 0"), out
assert "div#nested" in rows, out                                                   # a fixed child of a fixed header is listed
assert "moves with the scroll (a script positions it, or content above it loaded); stranded at top 1825" in rows["div#promo"], out
assert rows["div#promo"].rstrip().endswith(" -"), out                             # stranded: no anchor reading
assert "fixed to the viewport, at top -100 when scrolled" in rows["div#hider"], out
assert "bottom 100, right 0" in rows["div#tab"] and rows["div#tab"].rstrip().endswith("anchored top 300"), out
assert "neither edge kept: top 300 at 600, 600 at 1200" in rows[CENTER], out
assert "appeared within 3 s after load" in rows["div#flyout"], out
assert "appeared within 3 s after load" in rows["div#cookie"] and rows["div#cookie"].split()[1] == "absolute", out
assert "changed within 3 s after load: was bottom 200, right -200, 200x100" in rows["div#slide"], out
assert "appears when scrolled: bottom 20, left 20, 40x40" in rows["div#totop"], out
assert "bottom 0, full width" in rows["div#tray"] and "sticks" in rows["div#tray"], out
assert rows["div#tray"].rstrip().endswith("at top 1050 in the taller viewport (landing, or still pinned)"), out
assert "becomes fixed when scrolled" in rows["div#latch"], out                     # static at load, fixed once scrolled
assert "moves with the scroll" in rows["div#drawer"], out                          # moves sideways only
assert "appears when scrolled" in rows["div#consent"] and rows["div#consent"].split()[1] == "absolute", out
expected = ["div#header", "div#nested", "div#promo", "div#hider", "div#tab", CENTER, "div#flyout", "div#slide", "div#cookie",
            "div#totop", "div#tray", "div#latch", "div#drawer", "div#consent"]
assert sorted(keys) == sorted(expected), out                                       # no ordinary block, no repeated label
print("ok")
