import json, py_compile, subprocess
from pathlib import Path
import pytest
from conftest import (REPO, SKILLS_ROOT, ALLOWED_KEYS, REQUIRED_SECTIONS, SCHEDULED_SKILLS,
                      skill_dirs, load_skill, h2_titles)

@pytest.mark.parametrize("skill", skill_dirs(), ids=lambda p: p.name)
def test_frontmatter(skill):
    fm, body = load_skill(skill)
    assert set(fm) <= ALLOWED_KEYS, f"unknown keys: {set(fm) - ALLOWED_KEYS}"
    assert fm["name"] == skill.name
    assert 0 < len(fm["description"]) <= 1536
    assert fm.get("license") == "MIT"
    md = fm["metadata"]
    assert md["source"] == f"https://scalably.io/skills/{skill.name}"
    assert {"path", "commit", "date"} <= set(md["derived_from"])
    assert isinstance(md["triggers"], list) and isinstance(md["not_for"], list)

@pytest.mark.parametrize("skill", skill_dirs(), ids=lambda p: p.name)
def test_required_sections_in_order(skill):
    _, body = load_skill(skill)
    titles = h2_titles(body)
    idx = [titles.index(s) for s in REQUIRED_SECTIONS]  # raises ValueError if missing
    assert idx == sorted(idx), f"sections out of order: {titles}"
    if skill.name in SCHEDULED_SKILLS:
        assert "How to schedule this" in titles

@pytest.mark.parametrize("skill", skill_dirs(), ids=lambda p: p.name)
def test_worked_example_has_code(skill):
    _, body = load_skill(skill)
    section = body.split("## Worked example", 1)[1].split("\n## ", 1)[0]
    assert "```" in section, "worked example needs a pasteable fenced block"

@pytest.mark.parametrize("skill", skill_dirs(), ids=lambda p: p.name)
def test_relative_links_resolve(skill):
    import re
    _, body = load_skill(skill)
    for target in re.findall(r"\]\((?!https?://|#|mailto:)([^)]+)\)", body):
        assert (skill / target.split("#")[0]).exists(), f"broken link {target}"

@pytest.mark.parametrize("script", sorted(SKILLS_ROOT.glob("*/scripts/*")) if SKILLS_ROOT.exists() else [], ids=lambda p: f"{p.parent.parent.name}/{p.name}")
def test_scripts_compile(script):
    if script.suffix == ".py":
        py_compile.compile(str(script), doraise=True)
    elif script.suffix == ".sh":
        subprocess.run(["bash", "-n", str(script)], check=True)
    elif script.suffix == ".mjs":
        subprocess.run(["node", "--check", str(script)], check=True)
    assert script.read_text().startswith("#!") or script.suffix == ".mjs", "scripts need a shebang"

def test_marketplace_lists_exactly_the_skill_dirs():
    m = json.loads((REPO / ".claude-plugin/marketplace.json").read_text())
    listed = {Path(s).name for p in m["plugins"] for s in p["skills"]}
    present = {p.name for p in skill_dirs()}
    assert listed == present, f"manifest/dir mismatch: {listed ^ present}"
