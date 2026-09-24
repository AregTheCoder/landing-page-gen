"""On-device text recognition for corpus media: macOS Vision, through a small
Swift helper (`ocr.swift`) compiled on first use. It reads each string and its
box off a picture the way Live Text does; nothing leaves the machine and
nothing is paid.

A reading is `{path, w, h, lines: [{text, conf, box, words: [{text, box}]}]}`,
boxes in pixels from the top left. `read()` batches paths through one helper
process."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).with_name("ocr.swift")
BIN_DIR = Path.home() / ".cache" / "landing-page-gen"
BATCH = 200


def binary():
    """The compiled helper, rebuilt when ocr.swift changes (swiftc ships with the
    Xcode command line tools)."""
    exe = BIN_DIR / f"lp-ocr-{hashlib.sha1(SRC.read_bytes()).hexdigest()[:12]}"
    if not exe.exists():
        BIN_DIR.mkdir(parents=True, exist_ok=True)
        print(f"ocr: compiling {SRC.name} (once, ~1 min)", file=sys.stderr)
        subprocess.run(["swiftc", "-O", str(SRC), "-o", str(exe)], check=True)
    return exe


def read(paths):
    """{path: reading} for image files, in batches through one helper each."""
    exe, out, paths = binary(), {}, [str(p) for p in paths]
    for i in range(0, len(paths), BATCH):
        chunk = paths[i:i + BATCH]
        proc = subprocess.run([str(exe)], input="\n".join(chunk) + "\n", capture_output=True, text=True, check=True)
        for line in proc.stdout.splitlines():
            r = json.loads(line)
            out[r["path"]] = r
    return out

