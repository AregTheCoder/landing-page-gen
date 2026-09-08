"""Validate corpus/references/<family>.yaml and write the **References:**
line of each family block in style-families.md.

    uv run python .claude/skills/collect-references/apply.py
"""
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
DOC = ROOT / ".claude/skills/picsart-workflows/style-families.md"
REFS = ROOT / "corpus/references"
REQUIRED = ("family", "collected", "by", "photography", "examples", "creators", "picsart_specific", "prompt_guidance", "open")
HOSTS = ("pexels.com", "unsplash.com")


def check(path):
    d = yaml.safe_load(path.read_text()) or {}
    errors = [f"missing {k}" for k in REQUIRED if k not in d]
    if d.get("family") != path.stem:
        errors.append(f"family {d.get('family')!r} != file {path.stem}")
    ex = d.get("examples") or []
    if len(ex) < 5:
        errors.append(f"{len(ex)} examples, need 5")
    for e in ex:
        for k in ("url", "creator", "platform", "licence", "matches"):
            if not e.get(k):
                errors.append(f"example without {k}: {e.get('url')}")
        if not any(h in (e.get("url") or "") for h in HOSTS):
            errors.append(f"url off Pexels/Unsplash: {e.get('url')}")
    for c in d.get("creators") or []:
        if not c.get("name") or not c.get("profile_url"):
            errors.append(f"creator without name or profile_url: {c}")
    return d, errors


def main():
    doc = DOC.read_text()
    failed = 0
    for path in sorted(REFS.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        d, errors = check(path)
        if errors:
            failed += 1
            print(f"{path}: " + "; ".join(errors))
            continue
        creators = ", ".join(c["name"] for c in d["creators"][:4])
        line = f"**References:** {path.relative_to(ROOT)} ({len(d['examples'])} examples; {creators})."
        head = f"\n## {d['family']}\n"
        if head not in doc:
            print(f"{path}: no `## {d['family']}` block in {DOC.name}")
            failed += 1
            continue
        start = doc.index(head) + len(head)
        end = doc.find("\n## ", start)
        block = doc[start:end if end > 0 else None]
        if "**References:**" in block:
            block = re.sub(r"\*\*References:\*\*.*\n", line + "\n", block, count=1)
        else:
            block = re.sub(r"(\*\*Examples:\*\*.*\n)", r"\1" + line.replace("\\", "\\\\") + "\n", block, count=1)
        doc = doc[:start] + block + (doc[end:] if end > 0 else "")
        print(f"{path.name}: ok, {len(d['examples'])} examples")
    DOC.write_text(doc)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
