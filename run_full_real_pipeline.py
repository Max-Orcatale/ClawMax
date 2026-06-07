#!/usr/bin/env python3
"""
Run the complete ClawMax real production pipeline.

This script intentionally does not support mock mode or dry-run publishing. It
runs real interfaces end to end:

1. TechnicalReportAgent real-source report generation.
2. WeChatArticleAgent real article bundle generation.
3. Local article QA gate.
4. WeChat Official Account draft creation via live API.
5. ProductStrategyAgent opportunity-card generation.

It creates a WeChat backend draft, but it does not mass-send or free-publish.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent
RUNS_DIR = REPO_ROOT / "runs"
REPORTS_DIR = REPO_ROOT / "reports"
ARTICLES_DIR = REPO_ROOT / "articles"
PRODUCTS_DIR = REPO_ROOT / "products"

DEFAULT_REPORT_TIMEOUT = 1800
DEFAULT_WECHAT_TIMEOUT = 2400


class PipelineError(RuntimeError):
    pass


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def today_label() -> str:
    return dt.date.today().isoformat()


def safe_label(value: str) -> str:
    value = value.strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", value):
        raise PipelineError(f"Unsafe label: {value!r}. Use only letters, numbers, dot, underscore, and dash.")
    if value in {".", ".."} or "/" in value or "\\" in value:
        raise PipelineError(f"Unsafe label: {value!r}")
    return value


def default_label() -> str:
    stamp = dt.datetime.now().strftime("%H%M%S")
    return f"{today_label()}-real-full-{stamp}"


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def command_text(command: list[str]) -> str:
    import shlex

    return " ".join(shlex.quote(part) for part in command)


def run_command(step: str, command: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
    print(f"\n==> {step}")
    print(command_text(command))
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=os.environ.copy(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
    )
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if result.returncode != 0:
        raise PipelineError(f"{step} failed with exit code {result.returncode}")
    return result


def require_file(path: Path, message: str) -> None:
    if not path.is_file():
        raise PipelineError(f"{message}: {path}")


def require_env(name: str) -> None:
    if not os.environ.get(name):
        raise PipelineError(f"Missing required environment variable: {name}")


def parse_report_label(output: str, fallback: str) -> str:
    match = re.search(r"Output label:\s*([^\s]+)", output)
    if match:
        return safe_label(match.group(1))
    match = re.search(r"Report bundle:\s*.*/reports/([^\s/]+)", output)
    if match:
        return safe_label(match.group(1))
    return fallback


def build_commands(args: argparse.Namespace, *, report_label: str, article_label: str) -> dict[str, list[str]]:
    report_command = [
        sys.executable,
        "tests/test_technical_report_agent_run.py",
        "--output-label",
        report_label,
        "--timeout",
        str(args.report_timeout),
    ]
    if args.force:
        report_command.append("--force")

    wechat_command = [
        sys.executable,
        "tests/test_wechat_article_agent_run.py",
        "--report-label",
        report_label,
        "--output-label",
        article_label,
        "--timeout",
        str(args.wechat_timeout),
    ]
    if args.force:
        wechat_command.append("--force")

    publish_command = [
        sys.executable,
        "scripts/publish_wechat_article.py",
        "--article-label",
        article_label,
        "--mode",
        "draft",
        "--author",
        args.author,
    ]

    product_command = [
        sys.executable,
        "scripts/run_product_strategy_agent.py",
        "--report-label",
        report_label,
        "--article-label",
        article_label,
    ]

    return {
        "technical_report": report_command,
        "wechat_article": wechat_command,
        "wechat_draft": publish_command,
        "product_strategy": product_command,
    }


def validate_outputs(report_label: str, article_label: str) -> dict[str, Any]:
    report_dir = REPORTS_DIR / report_label
    article_dir = ARTICLES_DIR / article_label
    product_dir = PRODUCTS_DIR / report_label
    publish_manifest = article_dir / "wechat-publish.json"
    qa_report_path = article_dir / "qa-report.json"
    product_metadata_path = product_dir / "metadata.json"

    require_file(report_dir / "technical-report.md", "Missing technical report")
    require_file(article_dir / "final-wechat-article.md", "Missing final WeChat article")
    require_file(article_dir / "wechat-preview.html", "Missing WeChat preview")
    require_file(qa_report_path, "Missing QA report")
    require_file(publish_manifest, "Missing WeChat publish manifest")
    require_file(product_dir / "opportunity-cards.md", "Missing product opportunity cards")

    qa_report = load_json(qa_report_path)
    if qa_report.get("status") == "failed":
        raise PipelineError(f"Article QA failed: {qa_report_path}")

    publish_data = load_json(publish_manifest)
    if publish_data.get("status") != "draft_created":
        raise PipelineError(f"WeChat draft was not created. Manifest status: {publish_data.get('status')!r}")
    if not publish_data.get("draft_media_id"):
        raise PipelineError("WeChat draft manifest does not include draft_media_id")

    product_metadata = load_json(product_metadata_path)
    return {
        "report_dir": str(report_dir.relative_to(REPO_ROOT)),
        "article_dir": str(article_dir.relative_to(REPO_ROOT)),
        "product_dir": str(product_dir.relative_to(REPO_ROOT)),
        "qa_status": qa_report.get("status"),
        "qa_issue_count": len(qa_report.get("issues") or []),
        "draft_media_id": publish_data.get("draft_media_id"),
        "uploaded_image_count": len(publish_data.get("uploaded_images") or []),
        "product_opportunity_count": product_metadata.get("opportunity_count"),
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the full real ClawMax pipeline, including live WeChat draft creation.")
    parser.add_argument("--label", default=None, help="Base label for reports/<label>. Default: YYYY-MM-DD-real-full-HHMMSS.")
    parser.add_argument("--article-label", default=None, help="Article output label. Default: <label>-wechat.")
    parser.add_argument("--force", action="store_true", help="Allow existing report/article outputs to be overwritten by the underlying runners.")
    parser.add_argument("--author", default="ClawMax", help="WeChat article author field. Default: ClawMax.")
    parser.add_argument("--report-timeout", type=int, default=DEFAULT_REPORT_TIMEOUT, help=f"Technical report timeout seconds. Default: {DEFAULT_REPORT_TIMEOUT}.")
    parser.add_argument("--wechat-timeout", type=int, default=DEFAULT_WECHAT_TIMEOUT, help=f"WeChat article timeout seconds. Default: {DEFAULT_WECHAT_TIMEOUT}.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    report_label = safe_label(args.label or default_label())
    article_label = safe_label(args.article_label or f"{report_label}-wechat")
    run_id = f"{report_label}-full-real-pipeline"
    run_log_path = RUNS_DIR / f"{run_id}.json"
    started_at = now_iso()
    commands = build_commands(args, report_label=report_label, article_label=article_label)

    require_env("WECHAT_MP_APPID")
    require_env("WECHAT_MP_APPSECRET")

    run_log: dict[str, Any] = {
        "run_id": run_id,
        "status": "running",
        "mode": "full_real_pipeline",
        "started_at": started_at,
        "report_label": report_label,
        "article_label": article_label,
        "steps": [],
        "commands": {name: command_text(command) for name, command in commands.items()},
        "outputs": {},
    }
    write_json(run_log_path, run_log)

    try:
        report_result = run_command("1/4 real TechnicalReportAgent", commands["technical_report"], timeout=args.report_timeout + 120)
        report_label = parse_report_label(report_result.stdout, report_label)
        if article_label == f"{args.label or report_label}-wechat":
            article_label = safe_label(args.article_label or f"{report_label}-wechat")
        commands = build_commands(args, report_label=report_label, article_label=article_label)
        run_log["report_label"] = report_label
        run_log["article_label"] = article_label
        run_log["steps"].append({"name": "technical_report", "status": "completed", "finished_at": now_iso()})
        write_json(run_log_path, run_log)

        run_command("2/4 real WeChatArticleAgent + QA", commands["wechat_article"], timeout=args.wechat_timeout + 120)
        run_log["steps"].append({"name": "wechat_article_and_qa", "status": "completed", "finished_at": now_iso()})
        write_json(run_log_path, run_log)

        run_command("3/4 live WeChat backend draft creation", commands["wechat_draft"], timeout=900)
        run_log["steps"].append({"name": "wechat_draft", "status": "completed", "finished_at": now_iso()})
        write_json(run_log_path, run_log)

        run_command("4/4 ProductStrategyAgent", commands["product_strategy"], timeout=300)
        run_log["steps"].append({"name": "product_strategy", "status": "completed", "finished_at": now_iso()})

        outputs = validate_outputs(report_label, article_label)
        run_log["status"] = "completed"
        run_log["finished_at"] = now_iso()
        run_log["outputs"] = outputs
        write_json(run_log_path, run_log)

        print("\nPASS: full real pipeline completed.")
        print(f"Run log: {run_log_path}")
        print(f"Report: {REPORTS_DIR / report_label / 'technical-report.md'}")
        print(f"Article: {ARTICLES_DIR / article_label / 'final-wechat-article.md'}")
        print(f"WeChat manifest: {ARTICLES_DIR / article_label / 'wechat-publish.json'}")
        print(f"Product cards: {PRODUCTS_DIR / report_label / 'opportunity-cards.md'}")
        print(f"WeChat draft media_id: {outputs['draft_media_id']}")
        return 0
    except Exception as exc:
        run_log["status"] = "failed"
        run_log["finished_at"] = now_iso()
        run_log["error"] = str(exc)
        write_json(run_log_path, run_log)
        print(f"FAIL: {exc}", file=sys.stderr)
        print(f"Run log: {run_log_path}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
