import re
from pathlib import Path
import pytest
from conftest import REPO

# Literals are split so this file does not match itself or the private scanner.
FORBIDDEN = [
    "/" + "workspace" + "/",
    "/opt/" + "scalably",
    "/opt/" + "tools",
    "mcp__" + "scalably",
    "mcp__" + "sur" + "ge",
    "mcp__" + "gok" + "api",
    r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    r"[A-Za-z0-9]{30,}",
    "gserviceaccount" + r"\.com",
]
FILES = [
    p for p in REPO.rglob("*")
    if p.is_file()
    and ".git" not in p.parts
    and ".venv" not in p.parts
    and ".pytest_cache" not in p.parts
    and "__pycache__" not in p.parts
    and (p.suffix in {".md", ".py", ".sh", ".mjs", ".html", ".json", ".txt", ".yml", ".yaml"} or p.suffix == "")
]

@pytest.mark.parametrize("path", FILES, ids=lambda p: str(p.relative_to(REPO)))
def test_no_forbidden_patterns(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    for pat in FORBIDDEN:
        for m in re.finditer(pat, text):
            line = text.count("\n", 0, m.start()) + 1
            pytest.fail(f"{path.relative_to(REPO)}:{line} matches {pat!r}: {m.group(0)[:60]}")
