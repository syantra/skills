# /// script
# requires-python = ">=3.10"
# ///
"""Offline check for wfproof.api and wfproof.text: review URL parsing, comment text cleanup.

Run: uv run tests/test_api.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from wfproof import api, text

URL = ("https://example.my.workfront.adobe.com/proof/review/0123456789abcdef0123456789abcdef-PROOFTOKEN0000000000000000000000-t0000000"
       "?tcmsTenantId=00000000000000000000000000000000")
assert api.parse_review_url(URL + "#token:PROOFTOKEN0000000000000000000000,comment:3/") == ("PROOFTOKEN0000000000000000000000", 3, "00000000000000000000000000000000", None)
assert api.parse_review_url(URL)[:2] == ("PROOFTOKEN0000000000000000000000", None)  # no fragment: token from path
assert api.parse_review_url(URL + "#proof:CODE123,token:PROOFTOKEN0000000000000000000000,comment:3/")[3] == "CODE123"  # signed-in fragment

# A link that is not a proof review link (a document page) says what to copy instead of raising IndexError.
try:
    api.parse_review_url("https://example.my.workfront.com/document/65f0c1/proofs")
    raise AssertionError("a document link must be refused")
except SystemExit as e:
    assert "proof viewer" in str(e)

# Mentions and HTML entities come out as plain text.
assert text.plain('<a class="userlink" href="m@x.com" target="t">Kim Lee</a> or stet if it&#039;s normal') == "@Kim Lee or stet if it's normal"
# Paragraphs, line breaks and list items keep a break between them.
assert text.plain("<p>Hello</p><p>world</p>") == "Hello\nworld"
assert text.plain("a<br/>b<ul><li>c</li><li>d</li></ul>e<div>f</div>") == "a\nb\nc\nd\ne\nf"
# API codes -> words (codes as the reviewers response sends them).
assert text.label("decisionApprovedWithChanges", "decision") == "Approved with changes"
assert text.label("roleReviewerApprover", "role") == "Reviewer approver" and text.label(None) is None
print("ok")
