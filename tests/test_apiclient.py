"""Metered stock HTTP: the sliding windows, the backoff, the cache and the
request budget — with the clock and the network faked, so nothing sleeps."""
import json

from landing_page_gen.corpus import apiclient, ledger


class FakeClock:
    """Time only moves when something sleeps on it."""

    def __init__(self, now=1_000_000.0):
        self.now = now
        self.slept = []

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(round(seconds, 3))
        self.now += seconds


def responder(*answers):
    """A transport replaying (status, headers, body) in order, last one held."""
    calls = []

    def transport(url, headers=None, timeout=60):
        calls.append(url)
        status, hdrs, body = answers[min(len(calls), len(answers)) - 1]
        return status, hdrs, json.dumps(body).encode() if not isinstance(body, bytes) else body
    transport.calls = calls
    return transport


def client(tmp_path, transport, clock=None, **kw):
    clock = clock or FakeClock()
    led = ledger.Ledger(tmp_path / "_api.sqlite", clock=clock.time)
    lim = apiclient.Limiter(limits=kw.pop("limits", None), safety=kw.pop("safety", 1.0),
                            min_interval=kw.pop("min_interval", {"default": 0.0}),
                            clock=clock.time, environ={})
    c = apiclient.Client(transport=transport, ledger=led, limiter=lim, clock=clock.time,
                         sleep=clock.sleep, rng=lambda: 0.5, log=lambda m: None, **kw)
    return c, led, clock


def test_sliding_window_sleeps_until_the_oldest_call_leaves(tmp_path):
    t = responder((200, {}, {"ok": 1}))
    c, _, clock = client(tmp_path, t, limits={"x": [(4, 60)]})
    for i in range(4):
        c.get("x", f"https://x.test/s?q={i}")
        clock.now += 1  # four calls at t, t+1, t+2, t+3
    assert clock.slept == [] and t.calls and len(t.calls) == 4
    c.get("x", "https://x.test/s?q=fifth")
    # the window is full; the oldest call was 4 s ago, so it clears in 56
    assert clock.slept == [56.0] and c.stat("x")["waits"] == 1


def test_backoff_on_429_honours_retry_after_then_succeeds(tmp_path):
    t = responder((429, {"Retry-After": "7"}, {}), (200, {}, {"photos": [1]}))
    c, led, clock = client(tmp_path, t)
    assert c.get("pexels", "https://api.pexels.com/v1/search?query=cup") == {"photos": [1]}
    assert clock.slept == [7.0] and c.stat("pexels")["retries"] == 1
    # both attempts are on the log: the platform counted the 429 against us too
    rows = led.con.execute("SELECT status, attempt, cached FROM requests ORDER BY id").fetchall()
    assert rows == [(429, 1, 0), (200, 2, 0)]


def test_5xx_backoff_caps_attempts_and_4xx_does_not_retry(tmp_path):
    t = responder((503, {}, {}))
    c, _, clock = client(tmp_path, t)
    try:
        c.get("pexels", "https://api.pexels.com/v1/search?query=cup")
        assert False, "should give up"
    except apiclient.Unavailable as exc:
        assert "4 attempts" in str(exc)
    assert clock.slept == [1.0, 2.0, 4.0] and len(t.calls) == apiclient.MAX_ATTEMPTS
    t2 = responder((404, {}, {}))
    c2, _, _ = client(tmp_path / "b", t2)
    try:
        c2.get("pexels", "https://api.pexels.com/v1/search?query=cup")
        assert False, "should not retry a 404"
    except apiclient.ClientError:
        assert len(t2.calls) == 1


def test_auth_error_and_max_requests_stop_without_retrying(tmp_path):
    t = responder((401, {}, {}))
    c, _, _ = client(tmp_path, t)
    try:
        c.get("unsplash", "https://api.unsplash.com/search/photos?query=cup")
        assert False, "should raise on 401"
    except apiclient.AuthError:
        assert len(t.calls) == 1
    t2 = responder((200, {}, {"ok": 1}))
    c2, _, _ = client(tmp_path / "b", t2, max_requests=2)
    c2.get("pexels", "https://a.test/1")
    c2.get("pexels", "https://a.test/2")
    try:
        c2.get("pexels", "https://a.test/3")
        assert False, "should refuse past the run cap"
    except apiclient.BudgetExceeded as exc:
        assert exc.platform == "pexels"


def test_cache_hit_costs_zero_requests_expires_and_keeps_pixabay_24h(tmp_path):
    t = responder((200, {}, {"hits": [1]}))
    c, led, clock = client(tmp_path, t)
    url = "https://pixabay.com/api/?key=SECRET&q=cup"
    assert c.get("pixabay", url) == {"hits": [1]}
    assert c.get("pixabay", url) == {"hits": [1]} and len(t.calls) == 1  # served from cache
    assert c.stat("pixabay")["cache_hits"] == 1
    # the secret never reaches the store
    body = led.con.execute("SELECT params FROM responses").fetchone()[0]
    assert "SECRET" not in body and json.loads(body) == {"q": "cup"}
    # --refresh refetches Pexels but Pixabay stays cached inside its ToS floor
    c.refresh = True
    assert c.get("pixabay", url) == {"hits": [1]} and len(t.calls) == 1
    clock.now += ledger.MIN_TTL["pixabay"] + 1
    assert c.get("pixabay", url) == {"hits": [1]} and len(t.calls) == 2
    c.refresh = False
    c.get("pexels", "https://api.pexels.com/v1/search?query=cup")
    assert len(t.calls) == 3
    clock.now += ledger.TTL["pexels"] + 1
    c.get("pexels", "https://api.pexels.com/v1/search?query=cup")
    assert len(t.calls) == 4, "a stale entry is refetched"


def test_budget_refusal_isolates_platforms_and_remaining_header_defers(tmp_path):
    t = responder((200, {}, {"ok": 1}))
    c, led, clock = client(tmp_path, t, limits={"pexels": [(2, 3600)], "pixabay": [(100, 60)]})
    c.get("pexels", "https://a.test/1")
    c.get("pexels", "https://a.test/2")
    try:
        c.get("pexels", "https://a.test/3")
        assert False, "the hour window is spent"
    except apiclient.BudgetExceeded as exc:
        assert exc.platform == "pexels" and exc.retry_at > clock.now
    c.get("pixabay", "https://pixabay.com/api/?q=cup")  # a different platform is untouched
    assert len(t.calls) == 3
    # a near-exhausted remaining count defers the next call to the reset
    t2 = responder((200, {"X-Ratelimit-Remaining": "1", "X-Ratelimit-Reset": "30"}, {"ok": 1}),
                   (200, {}, {"ok": 2}))
    c2, _, clock2 = client(tmp_path / "b", t2)
    c2.get("pixabay", "https://pixabay.com/api/?q=a")
    c2.get("pixabay", "https://pixabay.com/api/?q=b")
    assert clock2.slept == [30.0]


def test_runs_jsonl_appends_and_prune_keeps_the_windows(tmp_path):
    clock = FakeClock()
    led = ledger.Ledger(tmp_path / "_api.sqlite", clock=clock.time)
    path = led.append_run({"run_id": "a", "family": "full-bleed"}, path=tmp_path / "_runs.jsonl")
    led.append_run({"run_id": "b", "family": "cinematic-still"}, path=path)
    assert [json.loads(l)["run_id"] for l in path.read_text().splitlines()] == ["a", "b"]
    led.record("pexels", "/v1/search", 200)
    clock.now += ledger.KEEP_DAYS * 86400 + 10
    led.record("pexels", "/v1/search", 200)
    led.prune()
    assert led.con.execute("SELECT COUNT(*) FROM requests").fetchone()[0] == 1


def test_from_fetch_adapts_a_legacy_stub_and_limits_read_the_env():
    t = apiclient.from_fetch(lambda url, headers=None: {"photos": []})
    assert t("https://x.test")[0] == 200

    def boom(url, headers=None):
        raise apiclient.RateLimited(url)
    assert apiclient.from_fetch(boom)("https://x.test")[0] == 429
    assert apiclient.limits_for("unsplash", environ={}) == [(50, 3600)]
    assert apiclient.limits_for("unsplash", environ={"UNSPLASH_PRODUCTION": "1"}) == [(1000, 3600)]
