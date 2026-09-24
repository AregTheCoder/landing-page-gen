"""The page facts chrome blocks are chosen from and checked against
(`assets/roles.yaml`): the Picsart tools a block can stand for, the page's own
tool (and how its Before is made), the tools its copy names, the models it
presents and the model that generates its pictures. The blocks and their
rules are in compose/bank.py."""

import re
from functools import cache
from pathlib import Path

import yaml

ASSETS = Path(__file__).parent / "assets"


@cache
def vocab():
    return yaml.safe_load((ASSETS / "roles.yaml").read_text())


def tool(name):
    return (vocab()["tools"] or {}).get(name)


def page_tool(page):
    """{tool, degrade} for a corpus page slug, or {} when no rule names one."""
    for rule in vocab()["pages"]:
        if re.search(rule["match"], str(page or "")):
            return {k: v for k, v in rule.items() if k != "match"}
    return {}


_ICON_TOOL = None


def icon_tool(icon):
    """The tool an icon stands for (the first tool that draws it), or None."""
    global _ICON_TOOL
    if _ICON_TOOL is None:
        _ICON_TOOL = {}
        for name, t in vocab()["tools"].items():
            for icon_ in (t["icon"], *(t.get("glyphs") or ())):
                _ICON_TOOL.setdefault(icon_, name)
    return _ICON_TOOL.get(icon)


def named_tools(copy):
    """Tools the copy names in words ("remove the background", "upscale"), in
    the order they first appear."""
    words = {"enhance": r"enhanc", "upscale": r"upscal|enlarg|resolution", "remove-bg": r"remov\w* (the )?background",
             "change-bg": r"(chang|replac)\w* (the )?background", "vectorize": r"vector|svg",
             "edit": r"remove (an )?object|retouch", "crop": r"\bcrop|resize", "adjust": r"colou?r|lighting|brightness",
             "generate": r"generat|prompt", "video": r"\bvideo|animat", "voice": r"\bvoice|audio|narrat|speech"}
    text = str(copy or "").lower()
    hits = [(m.start(), name) for name, pat in words.items() if (m := re.search(pat, text))]
    return [name for _, name in sorted(hits)]


def facts_for(page, copy="", labels=(), models=(), generator=None, page_copy=""):
    """The facts a composition's blocks are chosen from and checked against:
    the page, its tool (and how its Before is made), the tools its section copy
    names, the models it presents, the model that generates its pictures (the
    page's model, else the run's default image model), the section copy, the
    page's other short strings (its tool's own labels) and the `> chrome:`
    strings."""
    pt = page_tool(page)
    tools = [t for t in [pt.get("tool"), *named_tools(copy)] if t]
    return {"page": page, "tool": pt.get("tool"), "degrade": pt.get("degrade"),
            "tools": list(dict.fromkeys(tools)), "models": list(models),
            "generator": (list(models) or [generator])[0], "copy": copy, "page_copy": page_copy,
            "labels": list(labels)}
