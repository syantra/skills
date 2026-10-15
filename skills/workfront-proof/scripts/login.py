# /// script
# requires-python = ">=3.10"
# dependencies = ["playwright==1.63.0", "truststore==0.10.5"]
# ///
"""Sign in to a Workfront proof as a reviewer so proofhq.py can reply and resolve as you.

  uv run login.py <review-url>

Opens the proof in Chrome, without any reviewer code the link carries, so you sign in as yourself
(the viewer's own Sign in). Once signed in, the viewer puts your reviewer code in the address bar
(#proof:<code>,...); this script checks that Workfront accepts it, saves it to
~/.config/workfront-proof/codes.json (owner-only) for that proof and closes the window.
The code is never printed.
"""
import json
import os
import re
import sys
import urllib.parse
from pathlib import Path

import truststore
from playwright.sync_api import Error as PlaywrightError, sync_playwright

from wfproof import api

truststore.inject_into_ssl()  # trust the OS certificate store for the sign-in check, as proofhq.py does

PROFILE = Path.home() / ".config/workfront-proof/browser-profile"
CODES = Path.home() / ".config/workfront-proof/codes.json"
WAIT_S = 600


def identified(tenant, code, token):
    """True when Workfront accepts this reviewer code and says who it is."""
    try:
        return bool(api.rpc(tenant, "startup", token=token, proofingCode=code).get("recipient"))
    except api.Refused:
        return False


def main(url):
    tenant = api.parse_review_url(url)[2]  # also rejects a link that is not a proof review link
    PROFILE.mkdir(parents=True, exist_ok=True)
    CODES.parent.chmod(0o700)
    PROFILE.chmod(0o700)
    with sync_playwright() as p:
        try:
            ctx = p.chromium.launch_persistent_context(PROFILE, channel="chrome", headless=False, viewport=None)
        except PlaywrightError as e:
            sys.exit(f"Could not open Chrome: {str(e).split(chr(10))[0]}. Install Google Chrome, or close the window already using the sign-in profile.")
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        u = urllib.parse.urlsplit(url)  # drop a `proof:` code the pasted link carries (it may be a colleague's): the user signs in themselves
        page.goto(u._replace(fragment=",".join(x for x in u.fragment.split(",") if not x.startswith("proof:"))).geturl())
        print("Sign in to the proof in the Chrome window (use the viewer's Sign in). Waiting up to 10 minutes.", flush=True)
        found = last = None
        for _ in range(WAIT_S):
            try:  # a Playwright call, not time.sleep: only Playwright calls pick up the browser's events, so `url` and `pages` stay current
                ctx.pages[0].wait_for_timeout(1000)
                fragment = ctx.pages[0].url.partition("#")[2]  # the address bar, not a page script, which a single-sign-on redirect would break
            except (IndexError, PlaywrightError):  # the window was closed, or is mid-navigation
                fragment = ""
            if not ctx.pages:
                break
            m = re.search(r"proof:([^,/]+),token:([^,/]+)", fragment)
            if m and m.groups() != last:  # the viewer can show a code Workfront refuses: check each one before trusting it
                last = m.groups()
                try:
                    if identified(tenant, *last):
                        found = last
                        break
                except OSError:
                    last = None  # network trouble: look again
        ctx.close()
    if not found:
        sys.exit("No sign-in detected. Run again and sign in before closing the window.")
    code, token = found
    codes = json.loads(CODES.read_text()) if CODES.exists() else {}
    codes[token] = code
    with os.fdopen(os.open(CODES, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as f:  # owner-only from the first byte
        json.dump(codes, f)
    CODES.chmod(0o600)  # a file saved by an older version keeps its old mode otherwise
    print(f"Signed in. Saved reviewer code for proof {token}.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
