"""corpus/references/_manifest.yaml + examples/<family>/<id>.png: what a
reference-collector subagent needs to know and see about one family.

    uv run python .claude/skills/collect-references/manifest.py [family ...]
"""
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
DOC = ROOT / ".claude/skills/picsart-workflows/style-families.md"
OUT = ROOT / "corpus/references"
LINES = ("**Use:**", "**Slots:**", "**Ground:**", "**Panels (worker):**", "**Text:**", "**Never:**", "**Examples:**")


def blocks():
    doc = DOC.read_text()
    out = {}
    for part in doc.split("\n## ")[1:]:
        name, body = part.split("\n", 1)
        if name.strip() in ("Vocabulary and constants", "Slot classes"):
            continue
        out[name.strip()] = {k.strip("* :").lower(): next((l[len(k):].strip() for l in body.splitlines() if l.startswith(k)), "")
                             for k in LINES}
    return out


def main(argv):
    fams = blocks()
    wanted = [a for a in argv if not a.startswith("--")] or list(fams)
    con = sqlite3.connect(ROOT / "corpus/corpus.db")
    styles = yaml.safe_load((ROOT / "corpus/styles.yaml").read_text()) or {}
    pages, counts = defaultdict(Counter), Counter()
    for v in styles.values():
        if isinstance(v, dict) and v.get("style"):
            counts[v["style"]] += 1
            pages[v["style"]][v.get("page")] += 1
    manifest = {}
    for fam in wanted:
        b = fams[fam]
        ex_dir = OUT / "examples" / fam
        ex_dir.mkdir(parents=True, exist_ok=True)
        examples = []
        for aid in re.findall(r"\b[0-9a-f]{8}\b", b["examples"]):
            row = con.execute(
                "select p.slug, m.slot_id, m.local_path, m.alt, m.width, m.height from media m join sections s on s.id=m.section_id "
                "join pages p on p.id=s.page_id where m.local_path like ? or m.local_path like ? limit 1",
                (f"%/{aid}%", f"%-{aid}.%")).fetchone()
            if not row:
                continue
            slug, slot, local, alt, w, h = row
            png = ex_dir / f"{aid}.png"
            if not png.exists():
                try:
                    Image.open(ROOT / local).convert("RGB").save(png)
                except Exception as e:  # a video or an unreadable file: leave it out
                    print(f"{fam} {aid}: {e}", file=sys.stderr)
                    continue
            examples.append({"id": aid, "page": slug, "slot": slot, "size": f"{w}x{h}", "alt": alt or "", "png": str(png.relative_to(ROOT))})
        manifest[fam] = {
            "use": b["use"], "slots": b["slots"], "ground": b["ground"], "panels_worker": b["panels (worker)"], "text": b["text"],
            "never": b["never"], "tagged_assets": counts.get(fam, 0),
            "pages": [p for p, _ in pages[fam].most_common(12)], "examples": examples,
        }
    OUT.mkdir(exist_ok=True)
    (OUT / "_manifest.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True, width=110))
    print(f"{OUT / '_manifest.yaml'}: {len(manifest)} families, {sum(len(m['examples']) for m in manifest.values())} example PNGs")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
