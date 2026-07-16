"""Optional web tools (fetch + search)."""

from __future__ import annotations

import html as html_lib
import re
from typing import List, Tuple
from urllib.parse import quote_plus, urlparse

import httpx

_TAG_RE = re.compile(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>|<[^>]+>", re.I)
_WS_RE = re.compile(r"\s+")


def _strip_html(raw: str) -> str:
    text = _TAG_RE.sub(" ", raw)
    text = html_lib.unescape(text)
    return _WS_RE.sub(" ", text).strip()


def fetch_url(
    url: str,
    *,
    timeout: float = 30.0,
    max_chars: int = 20_000,
    user_agent: str = "xp-harness/0.5 (+https://github.com/245678000000/xp)",
) -> str:
    if not url.startswith(("http://", "https://")):
        return "error: url must start with http:// or https://"
    parsed = urlparse(url)
    if parsed.hostname in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
        return "error: refusing localhost URLs"
    if parsed.hostname and (
        parsed.hostname.startswith("10.")
        or parsed.hostname.startswith("192.168.")
        or parsed.hostname.startswith("169.254.")
    ):
        return "error: refusing private network URLs"

    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": user_agent})
            ctype = resp.headers.get("content-type", "")
            body = resp.text
    except Exception as e:  # noqa: BLE001
        return f"error: fetch failed: {type(e).__name__}: {e}"

    if "html" in ctype or body.lstrip().lower().startswith("<!doctype") or "<html" in body[:200].lower():
        text = _strip_html(body)
    else:
        text = body
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n…[truncated {len(text) - max_chars} chars]"
    return f"status={resp.status_code} content-type={ctype}\nurl={str(resp.url)}\n\n{text}"


def web_search(
    query: str,
    *,
    max_results: int = 5,
    timeout: float = 30.0,
) -> str:
    """
    Lightweight search via DuckDuckGo HTML (no API key).
    Results quality varies; prefer fetch_url on known docs URLs.
    """
    query = query.strip()
    if not query:
        return "error: empty query"
    max_results = max(1, min(int(max_results), 10))
    url = "https://html.duckduckgo.com/html/"
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.post(
                url,
                data={"q": query},
                headers={
                    "User-Agent": "xp-harness/0.5",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
            raw = resp.text
    except Exception as e:  # noqa: BLE001
        return f"error: search failed: {type(e).__name__}: {e}"

    results = _parse_ddg_html(raw, max_results=max_results)
    if not results:
        # Fallback: DDG lite
        try:
            lite = f"https://lite.duckduckgo.com/lite/?q={quote_plus(query)}"
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                resp = client.get(lite, headers={"User-Agent": "xp-harness/0.5"})
            results = _parse_ddg_lite(resp.text, max_results=max_results)
        except Exception as e:  # noqa: BLE001
            return f"error: search parse failed: {e}"

    if not results:
        return f"no results for: {query}"

    lines = [f"search: {query}", ""]
    for i, (title, href, snippet) in enumerate(results, 1):
        lines.append(f"{i}. {title}")
        lines.append(f"   {href}")
        if snippet:
            lines.append(f"   {snippet}")
        lines.append("")
    return "\n".join(lines).strip()


def _parse_ddg_html(raw: str, max_results: int) -> List[Tuple[str, str, str]]:
    # result blocks: class="result__a" href=...
    items: List[Tuple[str, str, str]] = []
    for m in re.finditer(
        r'class="result__a"[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>',
        raw,
        re.I,
    ):
        href = html_lib.unescape(m.group(1))
        title = _strip_html(m.group(2))
        # snippet nearby
        snippet = ""
        sn = re.search(
            r'class="result__snippet"[^>]*>([\s\S]*?)</(?:a|td|div)',
            raw[m.end() : m.end() + 800],
            re.I,
        )
        if sn:
            snippet = _strip_html(sn.group(1))[:240]
        # DDG redirect links
        if "uddg=" in href:
            um = re.search(r"uddg=([^&]+)", href)
            if um:
                from urllib.parse import unquote

                href = unquote(um.group(1))
        items.append((title or href, href, snippet))
        if len(items) >= max_results:
            break
    return items


def _parse_ddg_lite(raw: str, max_results: int) -> List[Tuple[str, str, str]]:
    items: List[Tuple[str, str, str]] = []
    for m in re.finditer(r'rel="nofollow"\s+href="(https?://[^"]+)"[^>]*>([\s\S]*?)</a>', raw, re.I):
        href = html_lib.unescape(m.group(1))
        title = _strip_html(m.group(2))
        if "duckduckgo.com" in href:
            continue
        items.append((title or href, href, ""))
        if len(items) >= max_results:
            break
    return items
