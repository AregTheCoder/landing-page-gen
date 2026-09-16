"""The stock pool's API ledger: one sqlite file, two tables, no new dependency.

`responses` is a plain HTTP cache — a re-run of the same search inside the TTL
costs zero requests, which is what makes `pool search` resumable after a crash
and cheap to iterate on. Pixabay's terms *require* results to be cached for 24
hours, so its TTL has a floor that even `--refresh` respects.

`requests` is the budget. Every network call is written here before its body is
parsed, so the sliding windows in `apiclient.Limiter` are read from what was
actually spent (including the 429s and 5xx the platform counted against us),
not from a counter that a crash would reset. Cache hits are logged for the
report but never counted against a window.

The file is per-machine state keyed to per-machine API keys, so it is
gitignored; the run reports in `_runs.jsonl` beside it are the part worth
keeping."""

import hashlib
import json
import sqlite3
import time
import urllib.parse
from pathlib import Path

LEDGER_DB = Path("corpus/pool/_api.sqlite")
RUNS_JSONL = Path("corpus/pool/_runs.jsonl")
TTL = {"pexels": 7 * 86400, "unsplash": 7 * 86400, "pixabay": 7 * 86400,
       "flickr": 86400, "openverse": 7 * 86400}
DEFAULT_TTL = 7 * 86400
# Pixabay: "requests must be cached for 24 hours" — a floor, not a default
MIN_TTL = {"pixabay": 86400}
SECRET_PARAMS = ("key", "api_key", "client_id")
KEEP_DAYS = 45  # longer than the longest window, with margin

SCHEMA = """
CREATE TABLE IF NOT EXISTS responses (
  cache_key TEXT PRIMARY KEY,
  platform TEXT NOT NULL,
  endpoint TEXT NOT NULL,
  params TEXT NOT NULL,
  status INTEGER NOT NULL,
  body TEXT NOT NULL,
  fetched_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS requests (
  id INTEGER PRIMARY KEY,
  platform TEXT NOT NULL,
  endpoint TEXT NOT NULL,
  ts REAL NOT NULL,
  status INTEGER,
  cached INTEGER NOT NULL DEFAULT 0,
  attempt INTEGER NOT NULL DEFAULT 1,
  remaining INTEGER,
  run_id TEXT
);
CREATE INDEX IF NOT EXISTS requests_platform_ts ON requests(platform, ts);
"""


class Ledger:
    def __init__(self, path=LEDGER_DB, clock=time.time):
        self.path, self.clock = Path(path), clock
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(self.path)
        self.con.executescript(SCHEMA)
        self.con.commit()

    def close(self):
        self.con.close()

    @staticmethod
    def cache_key(platform, url):
        """(key, endpoint, params) with the secret stripped: Pixabay carries
        its key in the query string, and neither the cache nor the log may
        hold it."""
        parts = urllib.parse.urlsplit(url)
        params = {k: v for k, v in urllib.parse.parse_qsl(parts.query)
                  if k.lower() not in SECRET_PARAMS}
        endpoint = f"{parts.netloc}{parts.path}"
        canonical = json.dumps(params, sort_keys=True)
        key = hashlib.sha1(f"{platform}|{endpoint}|{canonical}".encode()).hexdigest()
        return key, endpoint, params

    def ttl(self, platform):
        return TTL.get(platform, DEFAULT_TTL)

    def get(self, key, platform, refresh=False):
        """The cached body, or None when missing or stale. `refresh` skips the
        cache except where the platform's terms impose a floor."""
        row = self.con.execute(
            "SELECT body, fetched_at FROM responses WHERE cache_key = ?", (key,)).fetchone()
        if row is None:
            return None
        body, fetched_at = row
        age = self.clock() - fetched_at
        limit = MIN_TTL.get(platform, 0) if refresh else self.ttl(platform)
        if age > limit:
            return None
        return json.loads(body or "null")

    def put(self, key, platform, endpoint, params, status, body):
        if not (200 <= int(status) < 300):
            return  # only a good answer is worth replaying
        self.con.execute(
            "INSERT OR REPLACE INTO responses (cache_key, platform, endpoint, params, status, body, fetched_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (key, platform, endpoint, json.dumps(params or {}, sort_keys=True), int(status), body, self.clock()))
        self.con.commit()

    def record(self, platform, endpoint, status, cached=0, attempt=1, remaining=None, run_id=None):
        try:
            remaining = int(remaining) if remaining is not None else None
        except (TypeError, ValueError):
            remaining = None
        self.con.execute(
            "INSERT INTO requests (platform, endpoint, ts, status, cached, attempt, remaining, run_id)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (platform, endpoint or "", self.clock(), status, int(cached), int(attempt), remaining, run_id))
        self.con.commit()

    def counts(self, platform, windows, now=None):
        """One (requests made, oldest timestamp) per window. Cache hits are
        excluded: they cost the platform nothing."""
        now = self.clock() if now is None else now
        out = []
        for _, secs in windows or []:
            row = self.con.execute(
                "SELECT COUNT(*), MIN(ts) FROM requests WHERE platform = ? AND cached = 0 AND ts > ?",
                (platform, now - secs)).fetchone()
            out.append((row[0] or 0, row[1]))
        return out

    def prune(self, keep_days=KEEP_DAYS):
        """Drop request rows older than any window and responses past TTL."""
        now = self.clock()
        self.con.execute("DELETE FROM requests WHERE ts < ?", (now - keep_days * 86400,))
        for platform, secs in list(TTL.items()) + [("", DEFAULT_TTL)]:
            if platform:
                self.con.execute("DELETE FROM responses WHERE platform = ? AND fetched_at < ?",
                                 (platform, now - secs))
        self.con.commit()

    def append_run(self, report, path=RUNS_JSONL):
        """One JSON line per run: the optimisation ledger over time, and the
        half of this store worth committing."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a") as f:
            f.write(json.dumps(report, sort_keys=False) + "\n")
        return path
