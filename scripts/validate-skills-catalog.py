#!/usr/bin/env python3
"""Check that every in-repo skill is indexed in the tap catalog and docs."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / "skills"
CATALOG_PATH = ROOT / "skills.sh.json"


def main() -> int:
    skill_files = sorted(SKILLS_DIR.glob("*/SKILL.md"))
    skill_names = {path.parent.name for path in skill_files}
    errors: list[str] = []

    try:
        catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Cannot read {CATALOG_PATH.relative_to(ROOT)}: {exc}", file=sys.stderr)
        return 1

    groups = catalog.get("groupings")
    if not isinstance(groups, list):
        print("skills.sh.json must contain a groupings list", file=sys.stderr)
        return 1

    catalog_entries: list[str] = []
    for group in groups:
        if not isinstance(group, dict) or not isinstance(group.get("skills"), list):
            errors.append(f"Invalid catalog grouping: {group!r}")
            continue
        catalog_entries.extend(
            skill for skill in group["skills"] if isinstance(skill, str)
        )

    catalog_names = set(catalog_entries)
    duplicates = sorted(
        name for name in catalog_names if catalog_entries.count(name) > 1
    )
    missing_from_catalog = sorted(skill_names - catalog_names)
    missing_from_repo = sorted(catalog_names - skill_names)
    if duplicates:
        errors.append(f"Duplicate catalog entries: {', '.join(duplicates)}")
    if missing_from_catalog:
        errors.append(
            "Skills missing from skills.sh.json: " + ", ".join(missing_from_catalog)
        )
    if missing_from_repo:
        errors.append(
            "Catalog entries without skills/<name>/SKILL.md: "
            + ", ".join(missing_from_repo)
        )

    for doc_name in ("README.md", "AGENTS.md"):
        doc_path = ROOT / doc_name
        try:
            document = doc_path.read_text(encoding="utf-8")
        except OSError as exc:
            errors.append(f"Cannot read {doc_name}: {exc}")
            continue
        missing = sorted(name for name in skill_names if name not in document)
        if missing:
            errors.append(f"Skills missing from {doc_name}: " + ", ".join(missing))

    for path in skill_files:
        lines = path.read_text(encoding="utf-8").splitlines()
        if not lines or lines[0] != "---":
            errors.append(f"{path.relative_to(ROOT)}: frontmatter must start at line 1")
            continue
        try:
            end = lines.index("---", 1)
        except ValueError:
            errors.append(f"{path.relative_to(ROOT)}: frontmatter closing --- missing")
            continue
        declared_name = next(
            (line.partition(":")[2].strip().strip('"')
             for line in lines[1:end] if line.startswith("name:")),
            None,
        )
        if declared_name != path.parent.name:
            errors.append(
                f"{path.relative_to(ROOT)}: name is {declared_name!r}, "
                f"directory is {path.parent.name!r}"
            )

    if errors:
        print("Skill inventory validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"OK: {len(skill_names)} skills match the catalog, README, and AGENTS.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
