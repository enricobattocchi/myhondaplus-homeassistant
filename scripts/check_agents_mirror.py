#!/usr/bin/env python3
"""Check consumer AGENTS.md mirrored sections against pymyhondaplus."""

from __future__ import annotations

import difflib
import os
import re
import sys
import urllib.request
from pathlib import Path

CANONICAL_URL = (
    "https://raw.githubusercontent.com/enricobattocchi/pymyhondaplus/main/AGENTS.md"
)
MIRRORED_HEADINGS = (
    "## 2. Naming",
    "## 3. The three-repo ecosystem",
    "## 5. Cross-repo workflows",
)
MIRROR_MARKER_RE = re.compile(r"^\*Mirrored from `pymyhondaplus/AGENTS\.md` .*")


def _read_canonical(repo_root: Path) -> str:
    override = os.environ.get("AGENTS_CANONICAL_PATH")
    candidates = []
    if override:
        candidates.append(Path(override))
    candidates.append(repo_root.parent / "pymyhondaplus" / "AGENTS.md")

    for candidate in candidates:
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")

    with urllib.request.urlopen(CANONICAL_URL, timeout=30) as response:
        return response.read().decode("utf-8")


def _extract_section(text: str, heading: str) -> str:
    lines = text.splitlines()
    try:
        start = lines.index(heading)
    except ValueError:
        raise SystemExit(f"Missing heading: {heading}") from None

    end = len(lines)
    for index in range(start + 1, len(lines)):
        if lines[index].startswith("## "):
            end = index
            break

    return "\n".join(lines[start:end])


def _normalize(section: str) -> str:
    lines = []
    for line in section.splitlines():
        if MIRROR_MARKER_RE.match(line):
            continue
        lines.append(line.rstrip())
    compacted = []
    for line in lines:
        if line == "" and compacted and compacted[-1] == "":
            continue
        compacted.append(line)
    return "\n".join(compacted).strip() + "\n"


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    local_text = (repo_root / "AGENTS.md").read_text(encoding="utf-8")
    canonical_text = _read_canonical(repo_root)

    failed = False
    for heading in MIRRORED_HEADINGS:
        local_section = _normalize(_extract_section(local_text, heading))
        canonical_section = _normalize(_extract_section(canonical_text, heading))
        if local_section == canonical_section:
            continue

        failed = True
        print(f"Mirrored AGENTS.md section drifted: {heading}", file=sys.stderr)
        diff = difflib.unified_diff(
            canonical_section.splitlines(),
            local_section.splitlines(),
            fromfile="pymyhondaplus/AGENTS.md",
            tofile="AGENTS.md",
            lineterm="",
        )
        print("\n".join(diff), file=sys.stderr)

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
