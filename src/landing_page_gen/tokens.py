"""lp-tokens: token and dollar accounting for one build-landing-page run.

Reads the Claude Code session transcript that drove a run (``~/.claude/projects/
<cwd-slug>/<session>.jsonl`` plus its ``<session>/subagents/agent-*.jsonl``) and
attributes tokens to the manager, each section-worker and each section-reviewer.

The cost of a role is context x turns: cache-read is 70-85% of every bill, so a
file read once is paid for on every later turn. This meter surfaces that -- turns,
average context, and the reads/polls/sleeps that drive both -- and emits the
``## Agents`` table build-landing-page/SKILL.md wants in report.md.

Usage counts are deduplicated by ``message.id`` (one API response is logged once
per content block, with identical usage each time; last line wins)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

# Per-million-token prices, by model. Cache write is billed at the tier's TTL
# multiple of the base input price (5m = 1.25x, 1h = 2x); cache read at 0.1x.
PRICING = {
    "claude-opus-4-8": {"input": 15.0, "output": 75.0, "cw5m": 18.75, "cw1h": 30.0, "read": 1.5},
    "claude-opus-5": {"input": 15.0, "output": 75.0, "cw5m": 18.75, "cw1h": 30.0, "read": 1.5},
    "claude-sonnet-5": {"input": 3.0, "output": 15.0, "cw5m": 3.75, "cw1h": 6.0, "read": 0.3},
    "claude-fable-5": {"input": 15.0, "output": 75.0, "cw5m": 18.75, "cw1h": 30.0, "read": 1.5},
    "claude-haiku-4-5-20251001": {"input": 1.0, "output": 5.0, "cw5m": 1.25, "cw1h": 2.0, "read": 0.1},
}
DEFAULT_MODEL = "claude-opus-4-8"

SECTION_RE = re.compile(r"\bSection (S\d+)")
REVIEW_RE = re.compile(r"\bReview sections?\s+((?:S\d+[\s,and]*)+)", re.I)
SECTION_LABEL_RE = re.compile(r"S\d+")
RUN_RE = re.compile(r"runs/([A-Za-z0-9._-]+)/")

# Synthetic user turns injected by the harness -- not real human prompts, so they
# never bound a run window.
SYNTHETIC_PREFIXES = ("<task-notification>", "<local-command", "<command-name>",
                      "<system-reminder>", "<create-pr-command>", "[Image", "[Request interrupted")


def project_dir(cwd: Path) -> Path:
    """The ~/.claude/projects/<slug> directory Claude Code keeps for this cwd."""
    slug = re.sub(r"[^A-Za-z0-9]", "-", str(cwd.resolve()))
    return Path.home() / ".claude" / "projects" / slug


def read_jsonl(path: Path) -> list[dict]:
    out = []
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return out


def locate_session(run: str, pdir: Path) -> Path | None:
    """The session that actually drove the run: the one whose subagents hold the
    most Section/Review agents for runs/<run>/. Falls back to the newest top-level
    .jsonl that merely mentions the run when no session spawned run agents."""
    needle = f"runs/{run}/"
    scored: list[tuple[int, float, Path]] = []
    mention: list[tuple[float, Path]] = []
    for f in pdir.glob("*.jsonl"):
        sub = f.with_suffix("") / "subagents"
        n = sum(1 for _ in _run_agents(sub, run)) if sub.is_dir() else 0
        if n:
            scored.append((n, f.stat().st_mtime, f))
        try:
            with f.open() as fh:
                if any(needle in line for line in fh):
                    mention.append((f.stat().st_mtime, f))
        except OSError:
            continue
    if scored:
        return max(scored)[2]
    return max(mention)[1] if mention else None


def _blocks(rec: dict) -> list:
    c = rec.get("message", {}).get("content")
    return c if isinstance(c, list) else []


def _first_user_text(lines: list[dict]) -> str:
    for d in lines:
        if d.get("type") == "user":
            c = d.get("message", {}).get("content")
            if isinstance(c, str):
                return c
            if isinstance(c, list):
                txt = " ".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text")
                if txt.strip():
                    return txt
    return ""


def _is_human(rec: dict) -> bool:
    """A real human/prompt turn: a user record with text and no tool_result."""
    if rec.get("type") != "user":
        return False
    c = rec.get("message", {}).get("content")
    if isinstance(c, str):
        txt = c.strip()
    elif isinstance(c, list):
        types = {b.get("type") for b in c if isinstance(b, dict)}
        if "tool_result" in types or "text" not in types:
            return False
        txt = " ".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text").strip()
    else:
        return False
    return bool(txt) and not txt.startswith(SYNTHETIC_PREFIXES)


def _classify_read(path: str, run: str) -> str:
    """Bucket a Read's target path for the by-class byte tally."""
    if not path:
        return "other"
    if f"runs/{run}/" in path:
        if path.endswith("brief.md"):
            return "brief"
        if path.endswith("workflow.yaml"):
            return "own workflow.yaml"
        return "own run"
    m = RUN_RE.search(path)
    if m and m.group(1) != run:
        return "other run"
    if "/.claude/skills/" in path or "/.claude/agents/" in path:
        return "skill/agent docs"
    if "/src/" in path:
        return "src/"
    return "other"


@dataclass
class Usage:
    input: int = 0
    output: int = 0
    cw5m: int = 0
    cw1h: int = 0
    read: int = 0

    def add(self, u: dict) -> None:
        self.input += u.get("input_tokens", 0) or 0
        self.output += u.get("output_tokens", 0) or 0
        self.read += u.get("cache_read_input_tokens", 0) or 0
        cc = u.get("cache_creation") or {}
        cw1h = cc.get("ephemeral_1h_input_tokens")
        cw5m = cc.get("ephemeral_5m_input_tokens")
        if cw1h is None and cw5m is None:
            # older logs: only the flat total
            self.cw5m += u.get("cache_creation_input_tokens", 0) or 0
        else:
            self.cw1h += cw1h or 0
            self.cw5m += cw5m or 0

    def cost(self, price: dict) -> float:
        return (
            self.input * price["input"]
            + self.output * price["output"]
            + self.cw5m * price["cw5m"]
            + self.cw1h * price["cw1h"]
            + self.read * price["read"]
        ) / 1e6


@dataclass
class AgentReport:
    role: str
    label: str
    section: str = ""
    model: str = DEFAULT_MODEL
    turns: int = 0
    usage: Usage = field(default_factory=Usage)
    ctx_total: int = 0  # sum of per-turn context, for the average
    image_reads: int = 0
    job_polls: int = 0
    sleeps: int = 0
    ledger_bash: int = 0
    read_bytes: dict = field(default_factory=lambda: defaultdict(int))

    @property
    def avg_ctx(self) -> int:
        return round(self.ctx_total / self.turns) if self.turns else 0

    def cost(self, price: dict) -> float:
        return self.usage.cost(price)


def _tally(lines: list[dict], report: AgentReport, run: str) -> None:
    """Accumulate turns, deduped usage and tool-call counts over a slice of records."""
    seen: dict[str, dict] = {}  # message.id -> usage (last wins)
    read_result_kind: dict[str, str] = {}  # tool_use_id -> 'image'|'text'
    read_paths: dict[str, str] = {}  # tool_use_id -> path bucket
    read_ids_order: list[str] = []

    for d in lines:
        if d.get("type") == "assistant":
            msg = d.get("message", {})
            mid = msg.get("id")
            u = msg.get("usage")
            if mid and u is not None:
                seen[mid] = u
            if msg.get("model"):
                report.model = msg["model"]
            for b in _blocks(d):
                if not isinstance(b, dict) or b.get("type") != "tool_use":
                    continue
                name = b.get("name", "")
                inp = b.get("input", {}) or {}
                if name.endswith("picsart_job_status"):
                    report.job_polls += 1
                elif name == "Bash":
                    cmd = inp.get("command", "")
                    if re.search(r"(^|\s|&&|;|\|)\s*sleep\b", cmd):
                        report.sleeps += 1
                    if "ledger.jsonl" in cmd:
                        report.ledger_bash += 1
                elif name == "Read":
                    tid = b.get("id")
                    if tid:
                        read_paths[tid] = _classify_read(inp.get("file_path", ""), run)
                        read_ids_order.append(tid)
        elif d.get("type") == "user":
            for b in _blocks(d):
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    tid = b.get("tool_use_id")
                    if tid in read_paths:
                        ct = b.get("content")
                        if isinstance(ct, list):
                            for x in ct:
                                if not isinstance(x, dict):
                                    continue
                                if x.get("type") == "image":
                                    report.image_reads += 1
                                    read_result_kind[tid] = "image"
                                elif x.get("type") == "text":
                                    report.read_bytes[read_paths[tid]] += len(x.get("text", ""))
                        elif isinstance(ct, str):
                            report.read_bytes[read_paths[tid]] += len(ct)

    report.turns = len(seen)
    for u in seen.values():
        report.usage.add(u)
        report.ctx_total += (
            (u.get("input_tokens", 0) or 0)
            + (u.get("cache_read_input_tokens", 0) or 0)
            + (u.get("cache_creation_input_tokens", 0) or 0)
        )


def _run_agents(sub_dir: Path, run: str):
    """Yield (kind, section, lines, tool_use_id) for each worker/reviewer of this run."""
    if not sub_dir.is_dir():
        return
    for f in sorted(sub_dir.glob("agent-*.jsonl")):
        lines = read_jsonl(f)
        first = _first_user_text(lines)
        if f"runs/{run}/" not in "".join(json.dumps(x) for x in lines[:6]) and f"runs/{run}/" not in first:
            # cheap check on the head; fall through to the full scan only if needed
            if not any(f"runs/{run}/" in json.dumps(x) for x in lines):
                continue
        m = REVIEW_RE.search(first)
        if m:
            kind, section = "reviewer", "+".join(SECTION_LABEL_RE.findall(m.group(1)))
        else:
            m = SECTION_RE.search(first)
            if not m:
                continue
            kind, section = "worker", m.group(1)
        meta = f.with_suffix(".meta.json")
        tid = ""
        if meta.exists():
            try:
                tid = json.loads(meta.read_text()).get("toolUseId", "")
            except (OSError, json.JSONDecodeError):
                pass
        yield kind, section, lines, tid


def _manager_window(main_lines: list[dict], spawn_tids: set[str]) -> tuple[int, int]:
    """[start, end) line indices bounding the run's manager turns: from the human
    prompt preceding the first run spawn to the human prompt following the last."""
    spawn_idx = [
        i
        for i, d in enumerate(main_lines)
        if d.get("type") == "assistant"
        for b in _blocks(d)
        if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("id") in spawn_tids
    ]
    if not spawn_idx:
        return 0, len(main_lines)
    first, last = min(spawn_idx), max(spawn_idx)
    humans = [i for i, d in enumerate(main_lines) if _is_human(d)]
    start = max([h for h in humans if h <= first], default=0)
    end = min([h for h in humans if h > last], default=len(main_lines))
    return start, end


def analyse(run: str, session: Path, price: dict) -> dict:
    main_lines = read_jsonl(session)
    sub_dir = session.with_suffix("") / "subagents"

    workers: list[AgentReport] = []
    reviewers: list[AgentReport] = []
    spawn_tids: set[str] = set()
    spawns_per_section: dict[str, int] = defaultdict(int)

    for kind, section, lines, tid in _run_agents(sub_dir, run):
        if tid:
            spawn_tids.add(tid)
        rep = AgentReport(role=kind, label=f"{section} {kind}", section=section)
        _tally(lines, rep, run)
        if kind == "worker":
            workers.append(rep)
            spawns_per_section[section] += 1
        else:
            reviewers.append(rep)

    start, end = _manager_window(main_lines, spawn_tids)
    manager = AgentReport(role="manager", label="manager")
    _tally(main_lines[start:end], manager, run)

    workers.sort(key=lambda r: (r.section, r.label))
    reviewers.sort(key=lambda r: r.section)
    return {
        "run": run,
        "session": str(session),
        "manager": manager,
        "workers": workers,
        "reviewers": reviewers,
        "spawns_per_section": dict(spawns_per_section),
        "price": price,
    }


def _fmt_k(n: int) -> str:
    return f"{n/1000:.0f}k" if n >= 1000 else str(n)


def render_markdown(data: dict) -> str:
    price = data["price"]
    mgr = data["manager"]
    workers = data["workers"]
    reviewers = data["reviewers"]

    def row(r: AgentReport) -> str:
        extra = []
        if r.job_polls:
            extra.append(f"{r.job_polls} polls")
        if r.sleeps:
            extra.append(f"{r.sleeps} sleeps")
        if r.ledger_bash:
            extra.append(f"{r.ledger_bash} ledger")
        if r.image_reads:
            extra.append(f"{r.image_reads} img")
        note = ", ".join(extra)
        return (
            f"| {r.label} | {r.turns} | {_fmt_k(r.avg_ctx)} | "
            f"{_fmt_k(r.usage.output)} | {_fmt_k(r.usage.read)} | ${r.cost(price):.2f} | {note} |"
        )

    lines = ["## Agents", ""]
    lines.append("| agent | turns | avg ctx | output | cache-read | cost | notes |")
    lines.append("|---|--:|--:|--:|--:|--:|---|")
    lines.append(row(mgr))
    for r in workers:
        lines.append(row(r))
    for r in reviewers:
        lines.append(row(r))

    wt = sum(r.turns for r in workers)
    rt = sum(r.turns for r in reviewers)
    wc = sum(r.cost(price) for r in workers)
    rc = sum(r.cost(price) for r in reviewers)
    total = mgr.cost(price) + wc + rc
    lines.append(
        f"| **total** | {mgr.turns+wt+rt} | | | | **${total:.2f}** "
        f"| manager ${mgr.cost(price):.2f}, {len(workers)} workers ${wc:.2f}/{wt}t, "
        f"{len(reviewers)} reviewers ${rc:.2f}/{rt}t |"
    )
    lines.append("")
    resumes = {s: n for s, n in data["spawns_per_section"].items() if n > 1}
    if resumes:
        detail = ", ".join(f"{s}x{n}" for s, n in sorted(resumes.items()))
        lines.append(f"Resume spawns (section x spawns): {detail}.")
    polls = sum(r.job_polls for r in workers)
    sleeps = sum(r.sleeps for r in workers)
    ledger = sum(r.ledger_bash for r in reviewers) + sum(r.ledger_bash for r in workers)
    lines.append(f"Worker job_status polls: {polls}; sleep calls: {sleeps}; ledger Bash calls: {ledger}.")
    lines.append("")
    return "\n".join(lines)


def _to_json(data: dict) -> dict:
    price = data["price"]

    def d(r: AgentReport) -> dict:
        return {
            "label": r.label,
            "role": r.role,
            "section": r.section,
            "model": r.model,
            "turns": r.turns,
            "avg_ctx": r.avg_ctx,
            "output": r.usage.output,
            "cache_read": r.usage.read,
            "cache_write_5m": r.usage.cw5m,
            "cache_write_1h": r.usage.cw1h,
            "input": r.usage.input,
            "cost": round(r.cost(price), 4),
            "image_reads": r.image_reads,
            "job_polls": r.job_polls,
            "sleeps": r.sleeps,
            "ledger_bash": r.ledger_bash,
            "read_bytes": dict(r.read_bytes),
        }

    return {
        "run": data["run"],
        "session": data["session"],
        "manager": d(data["manager"]),
        "workers": [d(r) for r in data["workers"]],
        "reviewers": [d(r) for r in data["reviewers"]],
        "spawns_per_section": data["spawns_per_section"],
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="lp-tokens", description="Token and dollar accounting for a build-landing-page run.")
    p.add_argument("run", help="run name, e.g. live-5")
    p.add_argument("--session", type=Path, help="session .jsonl (default: newest mentioning runs/<run>/)")
    p.add_argument("--model", default=DEFAULT_MODEL, help="pricing model (default: %(default)s)")
    p.add_argument("--json", action="store_true", help="emit JSON instead of the Markdown table")
    a = p.parse_args(argv)

    session = a.session
    if session is None:
        session = locate_session(a.run, project_dir(Path.cwd()))
        if session is None:
            print(f"no session transcript mentions runs/{a.run}/", file=sys.stderr)
            return 1
    price = PRICING.get(a.model, PRICING[DEFAULT_MODEL])
    data = analyse(a.run, session, price)
    if a.json:
        print(json.dumps(_to_json(data), indent=2))
    else:
        print(render_markdown(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
