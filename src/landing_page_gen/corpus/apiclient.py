"""Metered HTTP for the stock clients: one sliding window per platform.

`hooks/credit_guard.py` and its siblings match MCP tool names (`picsart_*`),
so nothing above this module can see, pace, cap or ledger a Pexels call — a
`uv run lp-corpus pool search` is one opaque Bash invocation to them. The
discipline has to live here: every request is counted against the platform's
published free tier (at `SAFETY` of it, leaving headroom for the download
pings and for calls made by hand), spaced by `MIN_INTERVAL`, retried with
jitter on 429 and 5xx, and written to the ledger before the body is parsed.
The window is read from the ledger's request log rather than an in-memory
bucket, so a run resumed after a crash cannot re-trip the hour cap.

One platform's refusal never stops another: the errors below are raised per
platform and `pool.search` drops that platform for the run and carries on."""

import json
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from email.utils import parsedate_to_datetime

UA = "lp-corpus/0.1 (landing-page-gen stock pool)"
# every window must admit the request; (requests, seconds). Unsplash's demo
# tier is 50/hr and its production tier 1000/hr, which is a per-key fact, not
# a per-platform one — hence the env override rather than a second table.
LIMITS = {
    "pexels": [(200, 3600), (20_000, 30 * 86400)],
    "unsplash": [(50, 3600)],
    "pixabay": [(100, 60)],
}
UNSPLASH_PRODUCTION = [(1000, 3600)]
SAFETY = 0.9
MIN_INTERVAL = {"pixabay": 0.6, "default": 0.25}
MAX_ATTEMPTS = 4
MAX_WAIT = 120   # a computed wait longer than this stops the platform for the run: resumable beats sleeping
RESERVE = 2      # X-Ratelimit-Remaining at or under this: treat the window as spent
BACKOFF = 1.0    # 1, 2, 4 seconds, each times jitter


class RateLimited(Exception):
    """The platform said 429 and the wait is not worth taking here."""


class BudgetExceeded(Exception):
    """A window (or --max-requests) would be exceeded; retry_at says when."""

    def __init__(self, platform, retry_at=None):
        super().__init__(f"{platform}: request budget spent")
        self.platform, self.retry_at = platform, retry_at


class AuthError(Exception):
    """401/403: the key is missing or wrong. Skip the platform, never retry."""


class Unavailable(Exception):
    """5xx or a dead connection, after MAX_ATTEMPTS."""


class ClientError(Exception):
    """A 4xx that is not auth or rate limiting: this URL, not this platform."""


def limits_for(platform, limits=None, environ=None):
    """The platform's windows, with Unsplash's production tier honoured when
    UNSPLASH_PRODUCTION is set (the key has to be approved for it)."""
    import os
    table = dict(limits or LIMITS)
    environ = os.environ if environ is None else environ
    if platform == "unsplash" and environ.get("UNSPLASH_PRODUCTION"):
        return UNSPLASH_PRODUCTION
    return table.get(platform) or []


def header(headers, name):
    """Case-insensitive lookup: urllib preserves the server's casing."""
    if not headers:
        return None
    for k, v in headers.items():
        if k.lower() == name.lower():
            return v
    return None


def urllib_transport(url, headers=None, timeout=60):
    """(status, headers, body). Never raises on an HTTP status — the Client
    decides what a status means; a dead connection is status 0."""
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read() or b""
        except Exception:
            body = b""
        return exc.code, dict(exc.headers or {}), body
    except Exception:
        return 0, {}, b""


def from_fetch(fetch):
    """Adapt a legacy `fetch(url, headers=None) -> dict` stub (the seam every
    test already uses) to a transport, so the clients can be exercised with
    or without the metering."""
    def transport(url, headers=None, timeout=60):
        try:
            return 200, {}, json.dumps(fetch(url, headers=headers)).encode()
        except RateLimited:
            return 429, {}, b""
    return transport


def _seconds(value, now):
    """Retry-After is either a delta in seconds or an HTTP date."""
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        pass
    try:
        return max(0.0, parsedate_to_datetime(value).timestamp() - now)
    except Exception:
        return 0.0


def _reset_seconds(value, now):
    """X-Ratelimit-Reset is a unix timestamp on Pexels and a delta on Pixabay."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, v - now) if v > 1e9 else max(0.0, v)


class Limiter:
    """When may this platform be called again: the platform's own headers
    first, then our spacing, then the sliding windows."""

    def __init__(self, limits=None, safety=SAFETY, min_interval=None, clock=time.time, environ=None):
        self.limits, self.environ = limits, environ
        self.safety = safety
        self.min_interval = dict(min_interval or MIN_INTERVAL)
        self.clock = clock
        self._not_before = {}
        self._last = {}

    def windows(self, platform):
        return limits_for(platform, self.limits, self.environ)

    def mark(self, platform, now=None):
        self._last[platform] = self.clock() if now is None else now

    def pending(self, platform, now=None):
        now = self.clock() if now is None else now
        return max(0.0, self._not_before.get(platform, 0.0) - now)

    def hint(self, platform, status, headers, now=None):
        """Whatever the platform says beats our table: Retry-After, a reset
        stamp, or a remaining count down to RESERVE."""
        now = self.clock() if now is None else now
        wait = 0.0
        after = header(headers, "Retry-After")
        if after:
            wait = max(wait, _seconds(after, now))
        reset = header(headers, "X-Ratelimit-Reset")
        remaining = header(headers, "X-Ratelimit-Remaining")
        spent = False
        try:
            spent = remaining is not None and int(remaining) <= RESERVE
        except (TypeError, ValueError):
            pass
        if (status == 429 or spent) and reset:
            wait = max(wait, _reset_seconds(reset, now))
        if wait:
            self._not_before[platform] = max(self._not_before.get(platform, 0.0), now + wait)
        return wait

    def wait_for(self, platform, counts, now=None):
        """Seconds until every window admits one more call. `counts` is one
        (n, oldest timestamp) per window, in the order `windows` returns."""
        now = self.clock() if now is None else now
        wait = self.pending(platform, now)
        last = self._last.get(platform)
        if last is not None:
            gap = self.min_interval.get(platform, self.min_interval.get("default", 0.0))
            wait = max(wait, last + gap - now)
        for (cap, secs), (n, oldest) in zip(self.windows(platform), counts or []):
            if n >= max(1, int(cap * self.safety)):
                wait = max(wait, (oldest + secs - now) if oldest else float(secs))
        return max(0.0, wait)


class Client:
    """One metered session over the ledger. `fetch_for(platform)` hands back
    the `fetch(url, headers=None)` closure the stock clients already take."""

    def __init__(self, transport=urllib_transport, ledger=None, limiter=None, clock=time.time,
                 sleep=time.sleep, rng=random.random, run_id=None, max_requests=0,
                 refresh=False, timeout=60, log=print):
        self.transport, self.ledger = transport, ledger
        self.limiter = limiter or Limiter(clock=clock)
        self.clock, self.sleep, self.rng = clock, sleep, rng
        self.run_id, self.max_requests = run_id, max_requests
        self.refresh, self.timeout, self.log = refresh, timeout, log
        self.requests_made = 0
        self.stats = {}

    def stat(self, platform):
        return self.stats.setdefault(platform, {"requests": 0, "cache_hits": 0, "waits": 0,
                                                "wait_s": 0.0, "retries": 0, "stopped": None})

    def fetch_for(self, platform, cacheable=True):
        def fetch(url, headers=None):
            return self.get(platform, url, headers=headers, cacheable=cacheable)
        return fetch

    def _counts(self, platform):
        if self.ledger is None:
            return []
        return self.ledger.counts(platform, self.limiter.windows(platform), now=self.clock())

    def get(self, platform, url, headers=None, cacheable=True):
        st = self.stat(platform)
        key = endpoint = params = None
        if self.ledger is not None:
            key, endpoint, params = self.ledger.cache_key(platform, url)
            if cacheable:
                hit = self.ledger.get(key, platform, refresh=self.refresh)
                if hit is not None:
                    st["cache_hits"] += 1
                    self.ledger.record(platform, endpoint, 200, cached=1, run_id=self.run_id)
                    return hit
        for attempt in range(1, MAX_ATTEMPTS + 1):
            if self.max_requests and self.requests_made >= self.max_requests:
                raise BudgetExceeded(platform)
            now = self.clock()
            wait = self.limiter.wait_for(platform, self._counts(platform), now=now)
            if wait > MAX_WAIT:
                raise BudgetExceeded(platform, now + wait)
            if wait > 0:
                self.sleep(wait)
                st["waits"] += 1
                st["wait_s"] = round(st["wait_s"] + wait, 3)
            status, hdrs, body = self.transport(url, {**(headers or {}), "User-Agent": UA}, self.timeout)
            self.limiter.mark(platform, self.clock())
            self.requests_made += 1
            st["requests"] += 1
            remaining = header(hdrs, "X-Ratelimit-Remaining")
            if self.ledger is not None:
                self.ledger.record(platform, endpoint, status, cached=0, attempt=attempt,
                                   remaining=remaining, run_id=self.run_id)
            hinted = self.limiter.hint(platform, status, hdrs, now=self.clock())
            if 200 <= status < 300:
                text = body.decode() if isinstance(body, bytes) else str(body)
                if cacheable and self.ledger is not None:
                    self.ledger.put(key, platform, endpoint, params, status, text)
                return json.loads(text or "null")
            if status in (401, 403):
                raise AuthError(f"{platform}: {status} (key missing, wrong or not approved)")
            if status == 429:
                back = max(hinted, BACKOFF * (2 ** (attempt - 1)) * (0.5 + self.rng()))
                if attempt >= MAX_ATTEMPTS or back > MAX_WAIT:
                    raise RateLimited(url)
                self.sleep(back)
                st["retries"] += 1
                st["wait_s"] = round(st["wait_s"] + back, 3)
                continue
            if status == 0 or status >= 500:
                if attempt >= MAX_ATTEMPTS:
                    raise Unavailable(f"{platform}: {status or 'no response'} after {attempt} attempts")
                back = BACKOFF * (2 ** (attempt - 1)) * (0.5 + self.rng())
                self.sleep(back)
                st["retries"] += 1
                st["wait_s"] = round(st["wait_s"] + back, 3)
                continue
            raise ClientError(f"{platform}: {status} for {urllib.parse.urlsplit(url).path}")
        raise Unavailable(f"{platform}: gave up after {MAX_ATTEMPTS} attempts")
