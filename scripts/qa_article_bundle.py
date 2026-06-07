#!/usr/bin/env python3
"""Automated QA for a finalized ClawMax WeChat article bundle.

This first-stage QA gate is intentionally deterministic and file-based. It checks
bundle completeness, structured JSON consistency, image requirements, local image
references, draft-only publishing safety, and a small set of content/style rules.
It does not call live WeChat APIs and does not publish anything.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
ARTICLES_DIRNAME = "articles"

ARTICLE_FILENAME = "article.json"
METADATA_FILENAME = "metadata.json"
IMAGE_ASSETS_FILENAME = "image-assets.json"
FINAL_ARTICLE_FILENAME = "final-wechat-article.md"
HTML_PREVIEW_FILENAME = "wechat-preview.html"
DRAFT_FILENAME = "wechat-draft.md"
QA_REPORT_FILENAME = "qa-report.json"
REVIEW_NOTES_FILENAME = "review-notes.md"

MIN_SAVED_IMAGES = 5
MIN_SOURCE_DERIVED_IMAGES = 3
MIN_AI_GENERATED_IMAGES = 1
MAX_COVER_IMAGES = 1
MAX_GENERATED_SVG_IMAGES = 0

SOURCE_DERIVED_KINDS = {
    "source_image",
    "official_image",
    "webpage_screenshot",
    "project_screenshot",
    "github_screenshot",
    "paper_figure",
    "paper_image",
    "og_image",
}
REQUIRED_ARTICLE_KEYS = {
    "date",
    "title",
    "title_candidates",
    "digest",
    "sections",
    "source_report",
    "sources",
    "risk_flags",
    "style_references",
    "external_reference_accounts",
    "source_attribution_note",
    "image_assets",
    "auto_publish_eligible",
}
REQUIRED_SECTION_TYPES = {"intro", "frontier", "gold_rush"}
REQUIRED_HEADINGS = ["AI 前沿", "浪里淘金", "参考与信息来源"]
REPORT_VOICE_TERMS = [
    "值得注意的是",
    "这一趋势表明",
    "标志着",
    "赋能",
    "生态",
    "深度融合",
    "范式转移",
    "全链路",
    "闭环",
]
OVERCLAIM_TERMS = ["彻底颠覆", "全网最强", "必然取代"]
INTERNAL_PROCESS_TERMS = ["当前环境", "style corpus unavailable", "结构化数据", "生成流程", "本文未"]


class QAIssue(dict):
    """Tiny typed marker for issue dictionaries."""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json_file(path: Path) -> tuple[Any | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, f"Missing file: {path}"
    except json.JSONDecodeError as exc:
        return None, f"Invalid JSON in {path}: {exc}"


def rel_path(path: Path, *, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def add_issue(issues: list[dict[str, Any]], severity: str, code: str, message: str, *, path: str = "", details: Any = None) -> None:
    issue: dict[str, Any] = {
        "severity": severity,
        "code": code,
        "message": message,
    }
    if path:
        issue["path"] = path
    if details is not None:
        issue["details"] = details
    issues.append(issue)


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def asset_kind(asset: dict[str, Any]) -> str:
    return str(asset.get("kind") or asset.get("source_type") or asset.get("origin") or "").strip().lower()


def is_saved_asset(asset: dict[str, Any]) -> bool:
    return str(asset.get("status") or "").strip().lower() == "saved"


def has_bitmap_suffix(local_path: str) -> bool:
    return Path(local_path).suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}


def is_source_derived_asset(asset: dict[str, Any]) -> bool:
    kind = asset_kind(asset)
    source_url = str(asset.get("source_url") or asset.get("url") or "").strip()
    return bool(source_url) and (kind in SOURCE_DERIVED_KINDS or any(token in kind for token in ("source", "official", "screenshot", "figure", "og_image")))


def is_ai_generated_bitmap_asset(asset: dict[str, Any]) -> bool:
    local_path = str(asset.get("local_path") or "").strip()
    return (
        is_saved_asset(asset)
        and has_bitmap_suffix(local_path)
        and str(asset.get("tool") or "").strip() == "image_generate"
        and bool(str(asset.get("generation_prompt") or asset.get("prompt") or "").strip())
        and bool(str(asset.get("model") or "").strip())
        and bool(str(asset.get("provider") or "").strip())
    )


def is_generated_svg_asset(asset: dict[str, Any]) -> bool:
    local_path = str(asset.get("local_path") or "").strip().lower()
    kind = asset_kind(asset)
    prompt = str(asset.get("generation_prompt") or asset.get("prompt") or "").strip()
    return local_path.endswith(".svg") and ("generated" in kind or bool(prompt))


def markdown_image_refs(text: str) -> list[str]:
    return re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text)


def referenced_local_image_paths(final_text: str, html_text: str) -> set[str]:
    refs = set(markdown_image_refs(final_text))
    refs.update(re.findall(r"<img[^>]+src=[\"']([^\"']+)[\"']", html_text, flags=re.IGNORECASE))
    return refs


def check_required_files(article_dir: Path, issues: list[dict[str, Any]], *, repo_root: Path) -> dict[str, Path]:
    files = {
        "article": article_dir / ARTICLE_FILENAME,
        "metadata": article_dir / METADATA_FILENAME,
        "image_assets": article_dir / IMAGE_ASSETS_FILENAME,
        "final_article": article_dir / FINAL_ARTICLE_FILENAME,
        "html_preview": article_dir / HTML_PREVIEW_FILENAME,
        "draft": article_dir / DRAFT_FILENAME,
    }
    for key, path in files.items():
        if not path.is_file():
            add_issue(issues, "error", f"files.missing_{key}", f"Missing required article bundle file: {path.name}", path=rel_path(path, repo_root=repo_root))
    images_dir = article_dir / "images"
    if not images_dir.is_dir():
        add_issue(issues, "error", "files.missing_images_dir", "Missing article images directory: images/", path=rel_path(images_dir, repo_root=repo_root))
    return files


def check_article_json(article: dict[str, Any], issues: list[dict[str, Any]], *, article_path: Path, repo_root: Path) -> None:
    missing = sorted(REQUIRED_ARTICLE_KEYS - set(article.keys()))
    if missing:
        add_issue(issues, "error", "article.missing_required_keys", "article.json is missing required keys.", path=rel_path(article_path, repo_root=repo_root), details=missing)
    if article.get("auto_publish_eligible") is not False:
        add_issue(issues, "error", "article.auto_publish_eligible_not_false", "article.json auto_publish_eligible must remain false until separate QA/publishing gates exist.", path=rel_path(article_path, repo_root=repo_root))
    sections = as_list(article.get("sections"))
    section_types = {str(as_dict(section).get("type") or "") for section in sections}
    missing_types = sorted(REQUIRED_SECTION_TYPES - section_types)
    if missing_types:
        add_issue(issues, "error", "article.missing_required_sections", "article.json.sections is missing required section types.", path=rel_path(article_path, repo_root=repo_root), details=missing_types)



def check_metadata(metadata: dict[str, Any], issues: list[dict[str, Any]], *, metadata_path: Path, article_dir: Path, repo_root: Path) -> None:
    if metadata.get("auto_publish") is not False:
        add_issue(issues, "error", "metadata.auto_publish_not_false", "metadata.json auto_publish must remain false.", path=rel_path(metadata_path, repo_root=repo_root))
    expected_outputs = {
        "output_final_article": rel_path(article_dir / FINAL_ARTICLE_FILENAME, repo_root=repo_root),
        "output_html_preview": rel_path(article_dir / HTML_PREVIEW_FILENAME, repo_root=repo_root),
        "output_image_assets": rel_path(article_dir / IMAGE_ASSETS_FILENAME, repo_root=repo_root),
        "output_images_dir": rel_path(article_dir / "images", repo_root=repo_root),
    }
    for key, expected in expected_outputs.items():
        if metadata.get(key) != expected:
            add_issue(issues, "error", f"metadata.{key}_mismatch", f"metadata.json {key} should point to {expected}.", path=rel_path(metadata_path, repo_root=repo_root), details={"actual": metadata.get(key), "expected": expected})



def check_image_assets(
    article: dict[str, Any],
    manifest_assets: list[Any],
    metadata: dict[str, Any],
    issues: list[dict[str, Any]],
    *,
    article_dir: Path,
    repo_root: Path,
) -> None:
    article_assets = article.get("image_assets")
    if article_assets != manifest_assets:
        add_issue(issues, "error", "image_assets.article_manifest_mismatch", "article.json image_assets must exactly match image-assets.json.", path=rel_path(article_dir / IMAGE_ASSETS_FILENAME, repo_root=repo_root))

    assets = [asset for asset in manifest_assets if isinstance(asset, dict)]
    saved_assets = [asset for asset in assets if is_saved_asset(asset)]
    source_assets = [asset for asset in saved_assets if is_source_derived_asset(asset)]
    ai_assets = [asset for asset in saved_assets if is_ai_generated_bitmap_asset(asset)]
    svg_assets = [asset for asset in saved_assets if is_generated_svg_asset(asset)]
    cover_assets = [asset for asset in saved_assets if str(asset.get("purpose") or "").strip().lower() == "cover"]

    if len(saved_assets) < MIN_SAVED_IMAGES:
        add_issue(issues, "error", "image_assets.too_few_saved", f"Article bundle must include at least {MIN_SAVED_IMAGES} saved local images.", path=rel_path(article_dir / IMAGE_ASSETS_FILENAME, repo_root=repo_root), details={"actual": len(saved_assets), "expected_min": MIN_SAVED_IMAGES})
    if len(source_assets) < MIN_SOURCE_DERIVED_IMAGES:
        add_issue(issues, "error", "image_assets.too_few_source_derived", f"Article bundle must include at least {MIN_SOURCE_DERIVED_IMAGES} source-derived images with source_url.", path=rel_path(article_dir / IMAGE_ASSETS_FILENAME, repo_root=repo_root), details={"actual": len(source_assets), "expected_min": MIN_SOURCE_DERIVED_IMAGES})
    if len(ai_assets) < MIN_AI_GENERATED_IMAGES:
        add_issue(issues, "error", "image_assets.missing_ai_generated_bitmap", "Article bundle must include at least one real image_generate AI bitmap with prompt/model/provider metadata.", path=rel_path(article_dir / IMAGE_ASSETS_FILENAME, repo_root=repo_root))
    if len(svg_assets) > MAX_GENERATED_SVG_IMAGES:
        add_issue(issues, "error", "image_assets.generated_svg_forbidden", "Generated SVG placeholder images are not allowed.", path=rel_path(article_dir / IMAGE_ASSETS_FILENAME, repo_root=repo_root), details=[asset.get("local_path") for asset in svg_assets])
    if len(cover_assets) > MAX_COVER_IMAGES:
        add_issue(issues, "error", "image_assets.too_many_cover_images", f"Article bundle may include at most {MAX_COVER_IMAGES} cover-like image.", path=rel_path(article_dir / IMAGE_ASSETS_FILENAME, repo_root=repo_root), details={"actual": len(cover_assets), "expected_max": MAX_COVER_IMAGES})

    generated_files = set(as_list(metadata.get("generated_files")))
    for asset in saved_assets:
        local_path = str(asset.get("local_path") or "").strip()
        markdown_ref = str(asset.get("markdown_ref") or "").strip()
        if not local_path:
            add_issue(issues, "error", "image_assets.missing_local_path", "Saved image asset is missing local_path.", path=rel_path(article_dir / IMAGE_ASSETS_FILENAME, repo_root=repo_root), details=asset.get("id"))
            continue
        image_path = repo_root / local_path
        if not image_path.is_file():
            add_issue(issues, "error", "image_assets.local_file_missing", "Image asset local_path does not exist.", path=local_path)
        expected_prefix = rel_path(article_dir / "images", repo_root=repo_root) + "/"
        if not local_path.startswith(expected_prefix):
            add_issue(issues, "error", "image_assets.outside_article_images_dir", "Image asset must be stored under the article images directory.", path=local_path)
        if markdown_ref and "./images/" not in markdown_ref:
            add_issue(issues, "error", "image_assets.markdown_ref_not_relative", "Image markdown_ref must use ./images/... relative path.", path=rel_path(article_dir / IMAGE_ASSETS_FILENAME, repo_root=repo_root), details=markdown_ref)
        if local_path not in generated_files:
            add_issue(issues, "error", "metadata.generated_files_missing_image", "metadata.json generated_files must include every saved local image file.", path=local_path)



def check_content(
    article: dict[str, Any],
    final_text: str,
    html_text: str,
    issues: list[dict[str, Any]],
    *,
    article_dir: Path,
    repo_root: Path,
) -> None:
    final_path = article_dir / FINAL_ARTICLE_FILENAME
    html_path = article_dir / HTML_PREVIEW_FILENAME
    for heading in REQUIRED_HEADINGS:
        if heading not in final_text:
            add_issue(issues, "error", "content.missing_required_heading", f"final-wechat-article.md is missing required heading: {heading}", path=rel_path(final_path, repo_root=repo_root))
        if heading not in html_text and heading != "参考与信息来源":
            add_issue(issues, "warning", "html.missing_required_heading", f"wechat-preview.html may be missing heading: {heading}", path=rel_path(html_path, repo_root=repo_root))
    if "http://" not in final_text and "https://" not in final_text:
        add_issue(issues, "error", "content.missing_source_links", "final-wechat-article.md should preserve source links.", path=rel_path(final_path, repo_root=repo_root))
    report_voice_hits = [term for term in REPORT_VOICE_TERMS if term in final_text]
    if report_voice_hits:
        add_issue(issues, "warning", "content.report_voice_terms", "Article contains report-voice terms; consider rewriting in a more conversational public-account style.", path=rel_path(final_path, repo_root=repo_root), details=report_voice_hits)
    overclaim_hits = [term for term in OVERCLAIM_TERMS if term in final_text]
    if overclaim_hits:
        add_issue(issues, "error", "content.overclaim_terms", "Article contains exaggerated claims that should be removed or grounded.", path=rel_path(final_path, repo_root=repo_root), details=overclaim_hits)
    internal_hits = [term for term in INTERNAL_PROCESS_TERMS if term in final_text]
    if internal_hits:
        add_issue(issues, "error", "content.internal_process_terms", "Public-facing article contains internal process phrases.", path=rel_path(final_path, repo_root=repo_root), details=internal_hits)

    refs = referenced_local_image_paths(final_text, html_text)
    for asset in as_list(article.get("image_assets")):
        if not isinstance(asset, dict) or not is_saved_asset(asset):
            continue
        markdown_ref = str(asset.get("markdown_ref") or "")
        local_path = str(asset.get("local_path") or "")
        image_name = Path(local_path).name
        expected_ref = f"./images/{image_name}"
        if expected_ref not in refs and expected_ref not in markdown_ref:
            add_issue(issues, "warning", "content.image_not_referenced", "Saved image asset is not referenced in final Markdown or HTML preview.", path=local_path)



def write_review_notes(article_dir: Path, report: dict[str, Any]) -> Path:
    path = article_dir / REVIEW_NOTES_FILENAME
    lines: list[str] = []
    status = report["status"]
    if status == "passed":
        lines.append("# 自动 QA 结果：QA 通过")
        lines.append("")
        lines.append("未发现阻断问题。仍建议人工审阅事实、语气和最终微信后台效果。")
    elif status == "passed_with_warnings":
        lines.append("# 自动 QA 结果：有警告但未阻断")
        lines.append("")
        lines.append("未发现阻断错误，但存在建议人工处理的警告。")
    else:
        lines.append("# 自动 QA 结果：未通过")
        lines.append("")
        lines.append("发现阻断问题，修复后再创建微信草稿或进入后续发布步骤。")
    lines.append("")
    lines.append(f"- errors: {report['summary']['errors']}")
    lines.append(f"- warnings: {report['summary']['warnings']}")
    lines.append("")
    if report["issues"]:
        lines.append("## 问题清单")
        lines.append("")
        for issue in report["issues"]:
            path_text = f" [{issue.get('path')}]" if issue.get("path") else ""
            lines.append(f"- {issue['severity'].upper()} {issue['code']}{path_text}: {issue['message']}")
            if "details" in issue:
                lines.append(f"  - details: {json.dumps(issue['details'], ensure_ascii=False)}")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path



def qa_article_bundle(article_label: str, *, repo_root: Path | None = None, write_outputs: bool = True) -> dict[str, Any]:
    repo_root = repo_root or REPO_ROOT
    article_dir = repo_root / ARTICLES_DIRNAME / article_label
    issues: list[dict[str, Any]] = []

    if not article_dir.is_dir():
        add_issue(issues, "error", "bundle.missing_article_dir", "Article bundle directory does not exist.", path=rel_path(article_dir, repo_root=repo_root))

    files = check_required_files(article_dir, issues, repo_root=repo_root)

    article_data, article_error = read_json_file(files["article"])
    metadata_data, metadata_error = read_json_file(files["metadata"])
    manifest_data, manifest_error = read_json_file(files["image_assets"])
    for code, error, path in [
        ("article.invalid_json", article_error, files["article"]),
        ("metadata.invalid_json", metadata_error, files["metadata"]),
        ("image_assets.invalid_json", manifest_error, files["image_assets"]),
    ]:
        if error:
            add_issue(issues, "error", code, error, path=rel_path(path, repo_root=repo_root))

    article = as_dict(article_data)
    metadata = as_dict(metadata_data)
    manifest_assets = as_list(manifest_data)

    final_text = files["final_article"].read_text(encoding="utf-8") if files["final_article"].is_file() else ""
    html_text = files["html_preview"].read_text(encoding="utf-8") if files["html_preview"].is_file() else ""

    if article:
        check_article_json(article, issues, article_path=files["article"], repo_root=repo_root)
    if metadata:
        check_metadata(metadata, issues, metadata_path=files["metadata"], article_dir=article_dir, repo_root=repo_root)
    if article and manifest_data is not None:
        check_image_assets(article, manifest_assets, metadata, issues, article_dir=article_dir, repo_root=repo_root)
    if article and final_text:
        check_content(article, final_text, html_text, issues, article_dir=article_dir, repo_root=repo_root)

    errors = sum(1 for issue in issues if issue.get("severity") == "error")
    warnings = sum(1 for issue in issues if issue.get("severity") == "warning")
    status = "failed" if errors else ("passed_with_warnings" if warnings else "passed")
    report: dict[str, Any] = {
        "status": status,
        "article_label": article_label,
        "article_dir": rel_path(article_dir, repo_root=repo_root),
        "generated_at": now_iso(),
        "summary": {
            "errors": errors,
            "warnings": warnings,
            "issues": len(issues),
        },
        "checks": {
            "min_saved_images": MIN_SAVED_IMAGES,
            "min_source_derived_images": MIN_SOURCE_DERIVED_IMAGES,
            "min_ai_generated_images": MIN_AI_GENERATED_IMAGES,
            "max_cover_images": MAX_COVER_IMAGES,
            "max_generated_svg_images": MAX_GENERATED_SVG_IMAGES,
        },
        "issues": issues,
    }

    if write_outputs:
        article_dir.mkdir(parents=True, exist_ok=True)
        report_path = article_dir / QA_REPORT_FILENAME
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        notes_path = write_review_notes(article_dir, report)
        report["output_qa_report"] = rel_path(report_path, repo_root=repo_root)
        report["output_review_notes"] = rel_path(notes_path, repo_root=repo_root)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report



def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--article-label", required=True, help="Article output label under articles/<label>/")
    parser.add_argument("--no-write", action="store_true", help="Run QA without writing qa-report.json or review-notes.md")
    return parser.parse_args(argv)



def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = qa_article_bundle(args.article_label, write_outputs=not args.no_write)
    print(json.dumps({"status": report["status"], "summary": report["summary"], "article_label": report["article_label"]}, ensure_ascii=False))
    return 1 if report["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
