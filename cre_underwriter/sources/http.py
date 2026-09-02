"""
Minimal HTTP helper on urllib. No requests, no aiohttp, no dependency tree.

Two things worth knowing:

1.  Several of the sources here are ASP.NET web forms, not APIs. Talking to them
    means a GET to collect hidden state and a POST to submit. That is a normal
    HTTP conversation, not browser automation — no headless Chrome is involved.
    It is also, obviously, more fragile than a documented API. Every adapter
    that does this says so in its docstring and in the report output.

2.  An optional on-disk cache keeps repeat runs off the public servers. It is
    off by default and writes only to a directory you name.
"""

import gzip
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from typing import Optional

USER_AGENT = (
    "cre-underwriter/0.1 (open-source LA multifamily underwriting tool; "
    "contact: repository issue tracker)"
)

DEFAULT_TIMEOUT = 30

# Simple politeness gate so a batch run does not hammer a county server.
_MIN_INTERVAL = 0.25
_last_call = [0.0]


class FetchError(RuntimeError):
    pass


def _throttle() -> None:
    gap = time.time() - _last_call[0]
    if gap < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - gap)
    _last_call[0] = time.time()


def _cache_path(cache_dir: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]
    return os.path.join(cache_dir, h + ".cache")


def fetch(
    url: str,
    data: Optional[dict] = None,
    headers: Optional[dict] = None,
    timeout: int = DEFAULT_TIMEOUT,
    opener=None,
    cache_dir: Optional[str] = None,
    cache_ttl: int = 86400,
) -> str:
    """GET, or POST when `data` is given. Returns decoded text.

    Raises FetchError on any transport or HTTP failure. Callers convert that
    into a reported failure — never into a default value.
    """
    cache_key = url + "|" + urllib.parse.urlencode(sorted((data or {}).items()))
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
        path = _cache_path(cache_dir, cache_key)
        if os.path.exists(path) and (time.time() - os.path.getmtime(path)) < cache_ttl:
            with open(path, "r", encoding="utf-8") as fh:
                return fh.read()

    hdrs = {
        "User-Agent": USER_AGENT,
        "Accept": "*/*",
        "Accept-Encoding": "gzip",
    }
    if headers:
        hdrs.update(headers)

    body = None
    if data is not None:
        body = urllib.parse.urlencode(data).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/x-www-form-urlencoded")

    req = urllib.request.Request(url, data=body, headers=hdrs)
    _throttle()
    try:
        op = opener or urllib.request.build_opener()
        with op.open(req, timeout=timeout) as resp:
            raw = resp.read()
            if resp.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
            text = raw.decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        raise FetchError(f"HTTP {exc.code} from {url}") from exc
    except urllib.error.URLError as exc:
        raise FetchError(f"could not reach {url}: {exc.reason}") from exc
    except Exception as exc:  # socket timeouts, DNS, TLS
        raise FetchError(f"request to {url} failed: {exc}") from exc

    if cache_dir:
        with open(_cache_path(cache_dir, cache_key), "w", encoding="utf-8") as fh:
            fh.write(text)
    return text


def fetch_json(url: str, **kw) -> dict:
    text = fetch(url, **kw)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        # Bot-protection layers on some county sites answer with an HTML shell.
        head = text.lstrip()[:80].replace("\n", " ")
        raise FetchError(
            f"expected JSON from {url}, got {head!r} — the endpoint may have "
            f"changed or a bot-protection layer intercepted the request"
        ) from exc


def session_opener():
    """An opener that keeps cookies, for the two ASP.NET form sources."""
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
