#!/usr/bin/env python3
"""Install/sync ClawMax project Hermes profiles into local Hermes runtime.

Project source of truth:
  profiles/profiles.yaml
  profiles/*.md
  skills/*/SKILL.md

Runtime destinations:
  ~/.hermes/profiles/<profile>/SOUL.md
  ~/.hermes/skills/clawmax/<skill>/SKILL.md

This script is intentionally one-way:
  project files -> local Hermes runtime

It does not copy local secrets back into the repository. Real API keys belong in
local Hermes `.env` files or auth stores. The project manifest may contain only
placeholder values.

Common usage:

  python scripts/install_hermes_profiles.py --dry-run
  python scripts/install_hermes_profiles.py --configure-from-default
  python scripts/install_hermes_profiles.py --provider custom --model gpt-5.5 --base-url https://example.com/v1 --api-key <local-key>

After installing, run:

  hermes -p technicalreportagent status --all
  python tests/test_technical_report_agent_run.py
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover - fallback is for minimal Python envs
    yaml = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PROJECT_ROOT / "profiles" / "profiles.yaml"
SKILLS_SOURCE_DIR = PROJECT_ROOT / "skills"
SKILLS_NAMESPACE = "clawmax"


class InstallError(RuntimeError):
    pass


def info(message: str) -> None:
    print(message)


def fail(message: str) -> None:
    raise InstallError(message)


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        fail(f"Manifest not found: {path}")
    text = path.read_text(encoding="utf-8")
    if yaml is None:
        fail("PyYAML is required to read profiles/profiles.yaml. Install it or run inside Hermes Python env.")
    data = yaml.safe_load(text)
    if not isinstance(data, dict) or not isinstance(data.get("profiles"), dict):
        fail("profiles/profiles.yaml must contain a top-level `profiles:` mapping")
    return data


def hermes_home(profile: str | None = None) -> Path:
    if profile and profile != "default":
        return Path.home() / ".hermes" / "profiles" / profile
    return Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")).expanduser()


def runtime_profile_dir(profile_name: str) -> Path:
    return Path.home() / ".hermes" / "profiles" / profile_name


def run(command: list[str], *, dry_run: bool, check: bool = True) -> subprocess.CompletedProcess[str] | None:
    printable = " ".join(command)
    if dry_run:
        info(f"DRY-RUN: {printable}")
        return None
    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if check and result.returncode != 0:
        fail(f"Command failed ({result.returncode}): {printable}\n{result.stdout}")
    if result.stdout.strip():
        info(result.stdout.rstrip())
    return result


def hermes_profile_exists(profile_name: str) -> bool:
    result = subprocess.run(
        ["hermes", "profile", "show", profile_name],
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return result.returncode == 0


def create_profile_if_needed(profile_name: str, clone_from: str | None, *, dry_run: bool) -> None:
    if hermes_profile_exists(profile_name):
        info(f"Profile exists: {profile_name}")
        return

    command = ["hermes", "profile", "create", profile_name]
    if clone_from:
        # `--clone-all` is preferred because project agent profiles should be
        # runnable on the local machine without duplicating secret values in the
        # repository. If Hermes version does not support it, the command failure
        # will tell the user to use their installed CLI's equivalent.
        command.extend(["--clone-all", clone_from])
    run(command, dry_run=dry_run, check=True)


def copy_default_runtime_config_if_needed(profile_name: str, *, dry_run: bool, overwrite: bool = False) -> None:
    """Copy local default Hermes config into a runtime profile.

    This is a local install step, not a project-source step. The default Hermes
    config may contain local credentials, so the destination must stay under
    ~/.hermes/profiles/<profile>/ and must never be copied back into the repo.
    """

    src = Path.home() / ".hermes" / "config.yaml"
    dst = runtime_profile_dir(profile_name) / "config.yaml"
    if not src.is_file():
        info(f"WARNING: default Hermes config not found, cannot seed runtime config: {src}")
        return
    if dst.exists() and not overwrite:
        info(f"Runtime config already exists, not overwritten: {dst}")
        return
    if dry_run:
        action = "overwrite" if dst.exists() else "copy"
        info(f"DRY-RUN: {action} local runtime config {src} -> {dst}")
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    info(f"Seeded local runtime config for {profile_name}: {dst}")


def copy_file(src: Path, dst: Path, *, dry_run: bool) -> None:
    if not src.is_file():
        fail(f"Source file not found: {src}")
    if dry_run:
        info(f"DRY-RUN: copy {src} -> {dst}")
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    info(f"Copied {src.relative_to(PROJECT_ROOT)} -> {dst}")


def sync_skills_to(src_root: Path, dst_root: Path, *, dry_run: bool, label: str) -> None:
    if not src_root.is_dir():
        fail(f"Skills source directory not found: {src_root}")
    if dry_run:
        info(f"DRY-RUN: sync skills {src_root} -> {dst_root} ({label})")
        return

    dst_root.mkdir(parents=True, exist_ok=True)
    src_dirs = sorted(path for path in src_root.iterdir() if path.is_dir())
    src_names = {path.name for path in src_dirs}

    for child in sorted(dst_root.iterdir()) if dst_root.exists() else []:
        if child.is_dir() and child.name not in src_names:
            shutil.rmtree(child)
            info(f"Removed stale runtime skill from {label}: {child}")

    for src_dir in src_dirs:
        if not (src_dir / "SKILL.md").is_file():
            continue
        dst_dir = dst_root / src_dir.name
        if dst_dir.exists():
            shutil.rmtree(dst_dir)
        shutil.copytree(src_dir, dst_dir)
        info(f"Synced skill to {label}: {SKILLS_NAMESPACE}:{src_dir.name}")


def sync_skills(*, dry_run: bool) -> None:
    sync_skills_to(
        SKILLS_SOURCE_DIR,
        hermes_home() / "skills" / SKILLS_NAMESPACE,
        dry_run=dry_run,
        label="default Hermes home",
    )


def sync_profile_skills(profile_name: str, *, dry_run: bool) -> None:
    sync_skills_to(
        SKILLS_SOURCE_DIR,
        runtime_profile_dir(profile_name) / "skills" / SKILLS_NAMESPACE,
        dry_run=dry_run,
        label=f"profile {profile_name}",
    )


def write_env_placeholders(profile_name: str, env_template: dict[str, str], *, dry_run: bool) -> None:
    if not env_template:
        return
    env_path = runtime_profile_dir(profile_name) / ".env"

    existing = ""
    if env_path.exists():
        existing = env_path.read_text(encoding="utf-8")

    lines_to_add: list[str] = []
    for key, placeholder in env_template.items():
        prefix = f"{key}="
        if any(line.startswith(prefix) for line in existing.splitlines()):
            continue
        lines_to_add.append(f"{key}={placeholder}")

    if not lines_to_add:
        info(f"No .env placeholders needed for {profile_name}")
        return

    if dry_run:
        info(f"DRY-RUN: append placeholders to {env_path}: {', '.join(line.split('=')[0] for line in lines_to_add)}")
        return

    env_path.parent.mkdir(parents=True, exist_ok=True)
    with env_path.open("a", encoding="utf-8") as handle:
        if existing and not existing.endswith("\n"):
            handle.write("\n")
        if not existing:
            handle.write("# Local secrets for this Hermes profile. Do not commit.\n")
        for line in lines_to_add:
            handle.write(line + "\n")
    info(f"Updated local placeholder .env: {env_path}")


def inspect_profile_config(profile_name: str) -> str:
    result = subprocess.run(
        ["hermes", "-p", profile_name, "status", "--all"],
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return result.stdout


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_yaml_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    if yaml is None:
        fail("PyYAML is required to read/write Hermes runtime config")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def write_yaml_file(path: Path, data: dict[str, Any], *, dry_run: bool) -> None:
    if yaml is None:
        fail("PyYAML is required to read/write Hermes runtime config")
    if dry_run:
        info(f"DRY-RUN: write YAML config {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    info(f"Wrote local runtime config: {path}")


def is_placeholder(value: Any) -> bool:
    return isinstance(value, str) and value.startswith("<") and value.endswith(">")


def runtime_model_from_manifest(manifest: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    defaults = manifest.get("runtime_defaults", {})
    if not isinstance(defaults, dict):
        defaults = {}
    default_model = defaults.get("model", {})
    if not isinstance(default_model, dict):
        default_model = {}

    runtime_config = spec.get("runtime_config", {})
    if not isinstance(runtime_config, dict):
        runtime_config = {}
    model = dict(default_model)
    explicit_model = runtime_config.get("model", {})
    if isinstance(explicit_model, dict):
        model.update(explicit_model)
    return model


def configure_runtime_model(
    profile_name: str,
    manifest: dict[str, Any],
    spec: dict[str, Any],
    *,
    dry_run: bool,
    configure_from_default: bool,
    provider: str | None,
    model: str | None,
    base_url: str | None,
    api_key: str | None,
) -> None:
    dst = runtime_profile_dir(profile_name) / "config.yaml"
    config: dict[str, Any] = {}

    if configure_from_default:
        default_config_path = Path.home() / ".hermes" / "config.yaml"
        config = load_yaml_file(default_config_path)
        if config:
            info(f"Using local default Hermes config as base for {profile_name}: {default_config_path}")
    else:
        config = load_yaml_file(dst)

    desired_model = runtime_model_from_manifest(manifest, spec)
    if provider is not None:
        desired_model["provider"] = provider
    if model is not None:
        desired_model["default"] = model
    if base_url is not None:
        desired_model["base_url"] = base_url
    if api_key is not None:
        desired_model["api_key"] = api_key

    if not desired_model and not config:
        info(f"WARNING: no runtime model config available for {profile_name}")
        return

    # If using defaults from manifest, do not overwrite usable local values with placeholders.
    current_model = config.get("model", {}) if isinstance(config.get("model"), dict) else {}
    cleaned_model: dict[str, Any] = {}
    for key, value in desired_model.items():
        if is_placeholder(value):
            if key in current_model and current_model[key]:
                continue
            cleaned_model[key] = value
        else:
            cleaned_model[key] = value

    if cleaned_model:
        config["model"] = deep_merge(current_model, cleaned_model)

    write_yaml_file(dst, config, dry_run=dry_run)


def install_profiles(
    manifest: dict[str, Any],
    *,
    dry_run: bool,
    configure_from_default: bool,
    provider: str | None,
    model: str | None,
    base_url: str | None,
    api_key: str | None,
) -> None:
    profiles = manifest["profiles"]
    for profile_name, spec in profiles.items():
        if not isinstance(spec, dict):
            fail(f"Profile spec must be a mapping: {profile_name}")

        source = PROJECT_ROOT / str(spec.get("source", ""))
        runtime_soul = str(spec.get("runtime_soul", "SOUL.md"))

        info(f"\n== Installing profile: {profile_name} ==")
        create_profile_if_needed(profile_name, clone_from=None, dry_run=dry_run)
        configure_runtime_model(
            profile_name,
            manifest,
            spec,
            dry_run=dry_run,
            configure_from_default=configure_from_default,
            provider=provider,
            model=model,
            base_url=base_url,
            api_key=api_key,
        )
        sync_profile_skills(profile_name, dry_run=dry_run)
        copy_file(source, runtime_profile_dir(profile_name) / runtime_soul, dry_run=dry_run)

        if not dry_run:
            status = inspect_profile_config(profile_name)
            if "Model:        (not set)" in status or "Provider:     Auto" in status:
                info(
                    f"WARNING: {profile_name} may still lack model/provider configuration. "
                    f"Run this installer with --configure-from-default or explicit --provider/--model/--base-url/--api-key."
                )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=str(MANIFEST_PATH), help="Profiles manifest path. Default: profiles/profiles.yaml")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without changing local Hermes runtime")
    parser.add_argument(
        "--configure-from-default",
        action="store_true",
        help="Seed each project runtime profile config from local ~/.hermes/config.yaml, preserving provider/model/base_url/api_key locally only.",
    )
    parser.add_argument("--provider", default=None, help="Override local runtime model.provider for all project profiles")
    parser.add_argument("--model", default=None, help="Override local runtime model.default for all project profiles")
    parser.add_argument("--base-url", default=None, help="Override local runtime model.base_url for all project profiles")
    parser.add_argument("--api-key", default=None, help="Override local runtime model.api_key for all project profiles. Writes only to ~/.hermes/profiles/<profile>/config.yaml")
    parser.add_argument(
        "--skip-skills",
        action="store_true",
        help="Do not sync project skills into ~/.hermes/skills/clawmax/.",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    manifest = load_manifest(Path(args.manifest).expanduser().resolve())

    info(f"Project root: {PROJECT_ROOT}")
    info(f"Manifest: {Path(args.manifest).expanduser().resolve()}")

    if not args.skip_skills:
        info("\n== Syncing project skills ==")
        sync_skills(dry_run=args.dry_run)

    install_profiles(
        manifest,
        dry_run=args.dry_run,
        configure_from_default=args.configure_from_default,
        provider=args.provider,
        model=args.model,
        base_url=args.base_url,
        api_key=args.api_key,
    )

    info("\nDone.")
    info("Next checks:")
    info("  hermes -p technicalreportagent status --all")
    info("  python tests/test_technical_report_agent_run.py")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except InstallError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
