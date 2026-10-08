"""Turning raw API values into readable ones."""
import datetime
import html
import re


def when(ts):
    if not ts:
        return None
    return datetime.datetime.fromtimestamp(ts / 1000 if ts > 1e11 else ts, datetime.timezone.utc).isoformat(timespec="minutes")


def label(code, prefix=""):
    """API code -> words: label("decisionApprovedWithChanges", "decision") == "Approved with changes"."""
    if not code:
        return None
    return " ".join(re.findall(r"[A-Z][a-z]*|\d+", code.removeprefix(prefix))).capitalize()


def plain(text):
    """Comment HTML -> plain text: mention links become @Name, entities like &#039; are decoded."""
    text = re.sub(r'<a class="userlink"[^>]*>(.*?)</a>', r"@\1", text or "")
    return html.unescape(re.sub(r"<[^>]+>", "", text))
