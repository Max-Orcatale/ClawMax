#!/usr/bin/env python3
"""Sync ClawMax project-local skills into Hermes runtime skills.

Source:
  <project>/skills/<skill-name>/SKILL.md

Destination:
  ~/.hermes/skills/clawmax/<skill-name>/SKILL.md

This mirrors the current project skill directories into the Hermes runtime
location so `hermes -s <skill>` / `/skill <skill>` / cron `skills:` can load
project skills directly.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def sync_dir(src_root: Path, dst_root: Path) -> list[str]:
    if not src_root.exists():
        raise FileNotFoundError(f"source skills dir not found: {src_root}")
    dst_root.mkdir(parents=True, exist_ok=True)

    src_dirs = sorted(p for p in src_root.iterdir() if p.is_dir())
    synced: list[str] = []

    # Remove stale skill dirs in destination that no longer exist in source.
    src_names = {p.name for p in src_dirs}
    for child in sorted(dst_root.iterdir()):
        if child.is_dir() and child.name not in src_names:
            shutil.rmtree(child)

    for skill_dir in src_dirs:
        src_skill = skill_dir / "SKILL.md"
        if not src_skill.exists():
            continue
        dst_skill_dir = dst_root / skill_dir.name
        if dst_skill_dir.exists():
            shutil.rmtree(dst_skill_dir)
        shutil.copytree(skill_dir, dst_skill_dir)
        synced.append(skill_dir.name)

    return synced


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=None, help="ClawMax project root (default: script parent)")
    parser.add_argument("--hermes-home", default=None, help="Hermes home directory (default: ~/.hermes)")
    parser.add_argument("--namespace", default="clawmax", help="Destination namespace under Hermes skills")
    args = parser.parse_args()

    script_path = Path(__file__).resolve()
    project_root = Path(args.project_root).expanduser().resolve() if args.project_root else script_path.parents[1]
    hermes_home = Path(args.hermes_home).expanduser().resolve() if args.hermes_home else Path.home() / ".hermes"

    src_root = project_root / "skills"
    dst_root = hermes_home / "skills" / args.namespace

    synced = sync_dir(src_root, dst_root)
    for name in synced:
        print(name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
