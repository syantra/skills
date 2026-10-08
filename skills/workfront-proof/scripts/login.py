# /// script
# requires-python = ">=3.10"
# dependencies = ["playwright==1.63.0"]
# ///
"""Sign in to a Workfront proof as a reviewer so proofhq.py can reply and resolve as you.

  uv run login.py <review-url>

Opens the proof in Chrome. Sign in there (the viewer's own Sign in). Once signed in, the viewer
puts your reviewer code in the address bar (#proof:<code>,...); this script saves it to
~/.config/workfront-proof/codes.json (owner-only) for that proof and closes the window.
The code is never printed.
"""
import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

PROFILE = Path.home() / ".config/workfront-proof/browser-profile"
CODES = Path.home() / ".config/workfront-proof/codes.json"
WAIT_S = 600


def main(url):
    PROFILE.mkdir(parents=True, exist_ok=True)
    PROFILE.chmod(0o700)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(PROFILE, channel="chrome", headless=False, viewport=None)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(url)
        print("Sign in to the proof in the Chrome window (use the viewer's Sign in). Waiting up to 10 minutes.", flush=True)
        found = None
        for _ in range(WAIT_S):
            if not ctx.pages:
                break
            m = re.search(r"proof:([^,/]+),token:([^,/]+)", ctx.pages[0].evaluate("location.hash"))
            if m:
                found = m.groups()
                break
            time.sleep(1)
        ctx.close()
    if not found:
        sys.exit("No sign-in detected. Run again and sign in before closing the window.")
    code, token = found
    codes = json.loads(CODES.read_text()) if CODES.exists() else {}
    codes[token] = code
    CODES.write_text(json.dumps(codes))
    CODES.chmod(0o600)
    print(f"Signed in. Saved reviewer code for proof {token}.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
