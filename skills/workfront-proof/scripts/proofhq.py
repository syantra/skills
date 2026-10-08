# /// script
# requires-python = ">=3.10"
# dependencies = ["pypdfium2==5.14.0", "pillow==12.3.0"]
# ///
"""Workfront proof helper: list review comments, show one with a crop of its marked area,
and reply to or resolve comments on the user's say-so.

  uv run proofhq.py list    <review-url> [--all]
  uv run proofhq.py show    <review-url> [N]               N defaults to #comment:N in the URL
  uv run proofhq.py pages   <review-url>                   every page in order: slices, thumbnail, capture size, what changed
  uv run proofhq.py versions  <review-url>                 every version: date, file, comment counts
  uv run proofhq.py reviewers <review-url>                 review stages, roles and decisions
  (list, show, pages and reviewers take --version N to read another version)
  uv run proofhq.py reply   <review-url> N "text" [--send]  preview unless --send
  uv run proofhq.py resolve <review-url> N [--reopen] [--send]
  uv run proofhq.py delete-reply <review-url> N REPLY_ID [--send]   reply ids come from `show`

Uses the same RPC as the Workfront proof viewer (undocumented). Reads run as an anonymous
link session; writes run as the reviewer saved by login.py.
Source files and crops are cached in ~/.cache/workfront-proof/<proof token>/.
"""
import argparse
import importlib
import json
import sys
import urllib.error

COMMANDS = ("list", "pages", "show", "versions", "reviewers", "write")  # modules in wfproof/cmd/, in --help order


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in COMMANDS:  # imported by name so a module called `list` never shadows the builtin
        importlib.import_module(f"wfproof.cmd.{name}").register(sub)
    args = ap.parse_args()
    try:
        result = args.handler(args)
    except urllib.error.HTTPError as e:
        hint = " The proof may require login, or the link is wrong." if e.code in (400, 401, 403, 404) else ""
        sys.exit(f"HTTP {e.code} from Workfront.{hint}")
    except urllib.error.URLError as e:
        sys.exit(f"Network error: {e.reason}")
    json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
    print()


if __name__ == "__main__":
    main()
