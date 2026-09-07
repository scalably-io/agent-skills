import re
from pathlib import Path
import yaml

REPO = Path(__file__).resolve().parents[1]
SKILLS_ROOT = REPO / "skills"
ALLOWED_KEYS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
REQUIRED_SECTIONS = ["What it does", "Requirements", "Inputs and outputs", "Worked example", "Procedure"]
SCHEDULED_SKILLS = {"daily-log", "dream", "weekly-memory-cleanup", "friday-feedback"}

def skill_dirs():
    return sorted(p for p in SKILLS_ROOT.iterdir() if p.is_dir()) if SKILLS_ROOT.exists() else []

def load_skill(path: Path):
    text = (path / "SKILL.md").read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    assert m, f"{path.name}: missing frontmatter block"
    return yaml.safe_load(m.group(1)) or {}, m.group(2)

def h2_titles(body: str):
    return re.findall(r"^## (.+?)\s*$", body, re.M)
