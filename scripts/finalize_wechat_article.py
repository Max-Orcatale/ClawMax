#!/usr/bin/env python3
"""Finalize a ClawMax WeChat article bundle.

This script is intentionally small: it does not publish to WeChat or apply complex
layout. It takes the structured article.json produced by WeChatArticleAgent,
writes a reader-facing final Markdown article, creates a lightweight local HTML
preview, copies any report-side image assets into the article bundle, and keeps
article.json, image-assets.json, and metadata.json in sync.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = REPO_ROOT / "reports"
ARTICLES_DIR = REPO_ROOT / "articles"
FINAL_ARTICLE_FILENAME = "final-wechat-article.md"
HTML_PREVIEW_FILENAME = "wechat-preview.html"
DRAFT_FILENAME = "wechat-draft.md"
ARTICLE_JSON_FILENAME = "article.json"
METADATA_FILENAME = "metadata.json"
IMAGE_ASSETS_FILENAME = "image-assets.json"
IMAGES_DIRNAME = "images"
PROFILE_NAME = "wechatarticleagent"
REQUIRED_SECTION_TYPES = {"intro", "frontier", "gold_rush", "references"}
MIN_ARTICLE_IMAGES = 5
MIN_AI_GENERATED_IMAGES = 1
MIN_SOURCE_DERIVED_IMAGES = 3
MAX_COVER_IMAGES = 1
MAX_GENERATED_SVG_IMAGES = 0
SOURCE_DERIVED_IMAGE_KINDS = {
    "source_image",
    "source_screenshot",
    "official_image",
    "official_screenshot",
    "paper_figure",
    "github_screenshot",
    "product_screenshot",
    "webpage_screenshot",
    "og_image",
    "web_source",
}
BITMAP_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
FORBIDDEN_PUBLIC_BODY_PHRASES = (
    "技术报告里",
    "这份技术报告",
    "本次未",
    "本文未",
    "当前环境",
    "style corpus",
    "source_attribution_note",
    "auto_publish",
    "结构化数据",
    "生成流程",
    "ClawMax TechnicalReportAgent",
    "ClawMax sources",
    "ClawMax brief",
)



class FinalizeFailure(Exception):
    """Raised when a final article bundle cannot be produced safely."""


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def safe_label(label: str) -> str:
    safe = re.sub(r"[^0-9A-Za-z_.-]+", "-", label.strip()).strip("-._")
    if not safe:
        raise FinalizeFailure("label must not be empty")
    return safe[:120]


def rel_path(path: Path, *, repo_root: Path) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FinalizeFailure(f"Missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise FinalizeFailure(f"Invalid JSON in {path}: {exc}") from exc


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def require(condition: bool, message: str) -> None:
    if not condition:
        raise FinalizeFailure(message)


def normalize_markdown_ref(markdown_ref: str, filename: str, caption: str) -> str:
    alt = caption.strip() or "配图"
    if markdown_ref and markdown_ref.startswith("!["):
        return re.sub(r"\]\([^)]*\)", f"](./{IMAGES_DIRNAME}/{filename})", markdown_ref, count=1)
    return f"![{alt}](./{IMAGES_DIRNAME}/{filename})"


def resolve_asset_source_path(asset: dict[str, Any], *, report_dir: Path, repo_root: Path) -> Path | None:
    for key in ("local_path", "path", "file", "source_local_path"):
        value = str(asset.get(key) or "").strip()
        if not value:
            continue
        candidates = []
        raw = Path(value)
        if raw.is_absolute():
            candidates.append(raw)
        else:
            candidates.append(repo_root / raw)
            candidates.append(report_dir / raw)
        for candidate in candidates:
            if candidate.is_file():
                return candidate
    return None


def load_report_image_assets(*, report_dir: Path) -> list[dict[str, Any]]:
    manifest_path = report_dir / IMAGE_ASSETS_FILENAME
    if manifest_path.is_file():
        data = load_json(manifest_path)
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            assets = data.get("assets") or data.get("images") or []
            if isinstance(assets, list):
                return [item for item in assets if isinstance(item, dict)]
    return []


def asset_kind(asset: dict[str, Any]) -> str:
    return str(asset.get("kind") or asset.get("source_type") or asset.get("origin") or "").strip().lower()


def is_source_derived_asset(asset: dict[str, Any]) -> bool:
    kind = asset_kind(asset)
    source_url = str(asset.get("source_url") or asset.get("url") or "").strip()
    return bool(source_url) and (kind in SOURCE_DERIVED_IMAGE_KINDS or any(token in kind for token in ("source", "official", "screenshot", "figure", "og_image")))


def is_ai_generated_asset(asset: dict[str, Any]) -> bool:
    kind = asset_kind(asset)
    status = str(asset.get("status") or "").lower()
    prompt = str(asset.get("generation_prompt") or asset.get("prompt") or "").strip()
    model = str(asset.get("model") or asset.get("provider") or "").lower()
    return (
        "generated" in kind
        or "ai_generated" in kind
        or "ai-generated" in kind
        or "image_generate" in kind
        or "generated" in status
        or bool(prompt)
        or "gpt-image" in model
    )


def is_generated_svg_asset(asset: dict[str, Any]) -> bool:
    local_path = str(asset.get("local_path") or "").strip().lower()
    return is_ai_generated_asset(asset) and local_path.endswith(".svg")


def is_valid_ai_bitmap_asset(asset: dict[str, Any]) -> bool:
    local_path = str(asset.get("local_path") or "").strip()
    suffix = Path(local_path).suffix.lower()
    prompt = str(asset.get("generation_prompt") or asset.get("prompt") or "").strip()
    tool = str(asset.get("tool") or "").strip()
    model = str(asset.get("model") or "").strip()
    provider = str(asset.get("provider") or "").strip()
    serialized = json.dumps(asset, ensure_ascii=False).lower()
    return (
        is_ai_generated_asset(asset)
        and suffix in BITMAP_IMAGE_SUFFIXES
        and bool(prompt)
        and bool(model)
        and bool(provider)
        and tool == "image_generate"
        and not any(marker in serialized for marker in ["fallback", "compatible", "pillow", "local bitmap rendering"])
    )


def normalize_article_image_assets(*, article: dict[str, Any], article_dir: Path, repo_root: Path, max_images: int) -> list[dict[str, Any]]:
    image_dir = article_dir / IMAGES_DIRNAME
    image_dir.mkdir(parents=True, exist_ok=True)
    normalized: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for index, asset in enumerate(as_list(article.get("image_assets")), start=1):
        if not isinstance(asset, dict) or len(normalized) >= max_images:
            continue
        local_path_value = str(asset.get("local_path") or asset.get("path") or "").strip()
        if not local_path_value:
            continue
        raw_path = Path(local_path_value)
        candidates = [raw_path] if raw_path.is_absolute() else [repo_root / raw_path, article_dir / raw_path]
        source_path = next((candidate for candidate in candidates if candidate.is_file()), None)
        if source_path is None:
            normalized.append({**asset, "status": "missing_source", "notes": "Article image asset file was not found while finalizing article bundle."})
            continue
        destination = image_dir / source_path.name
        if source_path.resolve() != destination.resolve():
            destination = image_dir / source_path.name
            if destination.exists():
                destination = image_dir / f"{source_path.stem}-{index}{source_path.suffix or '.png'}"
            shutil.copy2(source_path, destination)
        rel = rel_path(destination, repo_root=repo_root)
        if rel in seen_paths:
            continue
        seen_paths.add(rel)
        caption = str(asset.get("caption") or asset.get("alt") or asset.get("purpose") or f"配图 {index}")
        markdown_ref = normalize_markdown_ref(str(asset.get("markdown_ref") or ""), destination.name, caption)
        normalized.append({
            **asset,
            "local_path": rel,
            "markdown_ref": markdown_ref,
            "caption": caption,
            "status": "saved",
            "kind": asset.get("kind") or ("generated" if is_ai_generated_asset(asset) else "article_asset"),
        })
    return normalized


def merge_image_assets(*, article_assets: list[dict[str, Any]], report_assets: list[dict[str, Any]], max_images: int) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for asset in article_assets + report_assets:
        if len(merged) >= max_images:
            break
        if not isinstance(asset, dict):
            continue
        local_path = str(asset.get("local_path") or "")
        if local_path in seen_paths:
            continue
        seen_paths.add(local_path)
        merged.append(asset)
    return merged


def insert_image_refs_after_sections(text: str, image_assets: list[dict[str, Any]]) -> str:
    saved_refs = [str(asset.get("markdown_ref") or "").strip() for asset in image_assets if isinstance(asset, dict) and asset.get("status") == "saved" and str(asset.get("markdown_ref") or "").strip()]
    missing_refs = [ref for ref in saved_refs if ref not in text]
    if not missing_refs:
        return text
    gallery = "\n".join(missing_refs)
    return text.rstrip() + "\n\n## 配图预览\n\n" + gallery + "\n"


def validate_public_body_text(text: str, *, label: str) -> None:
    for phrase in FORBIDDEN_PUBLIC_BODY_PHRASES:
        require(phrase not in text, f"{label} contains forbidden internal/AI-process phrase: {phrase}")


def copy_report_images(
    *,
    report_dir: Path,
    article_dir: Path,
    repo_root: Path,
    max_images: int = 5,
) -> list[dict[str, Any]]:
    image_dir = article_dir / IMAGES_DIRNAME
    image_dir.mkdir(parents=True, exist_ok=True)
    copied_assets: list[dict[str, Any]] = []
    seen_destinations: set[Path] = set()

    for index, asset in enumerate(load_report_image_assets(report_dir=report_dir), start=1):
        if len(copied_assets) >= max_images:
            break
        source_path = resolve_asset_source_path(asset, report_dir=report_dir, repo_root=repo_root)
        if source_path is None:
            copied_assets.append(
                {
                    **asset,
                    "status": "missing_source",
                    "notes": "Referenced report image was not found while finalizing article bundle.",
                }
            )
            continue

        filename = source_path.name
        destination = image_dir / filename
        if destination in seen_destinations:
            stem = source_path.stem or f"image-{index}"
            suffix = source_path.suffix or ".png"
            destination = image_dir / f"{stem}-{index}{suffix}"
            filename = destination.name
        shutil.copy2(source_path, destination)
        seen_destinations.add(destination)

        caption = str(asset.get("caption") or asset.get("alt") or asset.get("purpose") or "配图")
        markdown_ref = normalize_markdown_ref(str(asset.get("markdown_ref") or ""), filename, caption)
        copied_assets.append(
            {
                **asset,
                "local_path": rel_path(destination, repo_root=repo_root),
                "markdown_ref": markdown_ref,
                "caption": caption,
                "status": "saved",
                "copied_from": rel_path(source_path, repo_root=repo_root) if source_path.is_relative_to(repo_root) else str(source_path),
            }
        )
    return copied_assets


def validate_article_contract(article: dict[str, Any]) -> None:
    for key in (
        "title",
        "title_candidates",
        "digest",
        "sections",
        "sources",
        "risk_flags",
        "style_references",
        "external_reference_accounts",
        "source_attribution_note",
        "auto_publish_eligible",
    ):
        require(key in article, f"article.json missing key: {key}")
    require(isinstance(article["title"], str) and article["title"].strip(), "article.json title must be non-empty")
    require(isinstance(article["sections"], list) and article["sections"], "article.json sections must be a non-empty array")
    section_types = {str(section.get("type")) for section in article["sections"] if isinstance(section, dict)}
    missing = REQUIRED_SECTION_TYPES - section_types
    require(not missing, f"article.json missing required section types: {sorted(missing)}")
    require(article["auto_publish_eligible"] is False, "auto_publish_eligible must remain false before automated QA/publishing exists")


def build_final_markdown(article: dict[str, Any], image_assets: list[dict[str, Any]]) -> str:
    title = str(article.get("title") or "未命名公众号文章").strip()
    digest = str(article.get("digest") or "").strip()
    parts: list[str] = [f"# {title}", ""]

    if digest:
        parts.extend([f"> {digest}", ""])

    lead_image = next(
        (
            asset
            for asset in image_assets
            if str(asset.get("status")) == "saved" and str(asset.get("markdown_ref") or "").strip()
        ),
        None,
    )
    if lead_image is not None:
        parts.extend([str(lead_image["markdown_ref"]).strip(), ""])

    for section in as_list(article.get("sections")):
        if not isinstance(section, dict):
            continue
        heading = str(section.get("heading") or "").strip()
        content = str(section.get("content_md") or "").strip()
        if not heading or not content:
            continue
        parts.extend([f"## {heading}", "", content, ""])

    final_text = "\n".join(parts).rstrip() + "\n"
    return insert_image_refs_after_sections(final_text, image_assets)


def inline_markdown_to_html(text: str) -> str:
    escaped = html.escape(text, quote=True)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2">\1</a>', escaped)
    escaped = re.sub(r"(?<![\"'=])(https?://[^\s<)]+)", r'<a href="\1">\1</a>', escaped)
    return escaped


def markdown_block_to_html(markdown: str) -> str:
    blocks: list[str] = []
    list_items: list[str] = []

    def flush_list() -> None:
        nonlocal list_items
        if list_items:
            blocks.append("<ul>" + "".join(list_items) + "</ul>")
            list_items = []

    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            flush_list()
            continue
        image_match = re.match(r"!\[([^\]]*)\]\(([^)]+)\)", stripped)
        if image_match:
            flush_list()
            alt = html.escape(image_match.group(1) or "配图", quote=True)
            src = html.escape(image_match.group(2), quote=True)
            blocks.append(f'<figure><img src="{src}" alt="{alt}"><figcaption>{alt}</figcaption></figure>')
            continue
        heading_match = re.match(r"^(#{3,6})\s+(.+)$", stripped)
        if heading_match:
            flush_list()
            level = min(len(heading_match.group(1)) + 1, 6)
            blocks.append(f"<h{level}>{inline_markdown_to_html(heading_match.group(2))}</h{level}>")
            continue
        bullet_match = re.match(r"^[-*]\s+(.+)$", stripped)
        if bullet_match:
            list_items.append(f"<li>{inline_markdown_to_html(bullet_match.group(1))}</li>")
            continue
        flush_list()
        blocks.append(f"<p>{inline_markdown_to_html(stripped)}</p>")

    flush_list()
    return "\n".join(blocks)


def build_html_preview(article: dict[str, Any], image_assets: list[dict[str, Any]]) -> str:
    title = str(article.get("title") or "未命名公众号文章").strip()
    digest = str(article.get("digest") or "").strip()
    title_html = html.escape(title, quote=True)
    digest_html = inline_markdown_to_html(digest)
    updated_at = html.escape(str(article.get("updated_at") or now_iso()), quote=True)

    lead_image = next(
        (
            asset
            for asset in image_assets
            if str(asset.get("status")) == "saved" and str(asset.get("markdown_ref") or "").strip()
        ),
        None,
    )

    body_parts: list[str] = []
    if lead_image is not None:
        markdown_ref = str(lead_image.get("markdown_ref") or "").strip()
        if markdown_ref:
            body_parts.append(markdown_block_to_html(markdown_ref))

    for section in as_list(article.get("sections")):
        if not isinstance(section, dict):
            continue
        heading = str(section.get("heading") or "").strip()
        content = str(section.get("content_md") or "").strip()
        if not heading or not content:
            continue
        body_parts.append(
            "\n".join(
                [
                    '<section class="wechat-preview-section">',
                    f"<h2>{html.escape(heading, quote=True)}</h2>",
                    markdown_block_to_html(content),
                    "</section>",
                ]
            )
        )

    existing_html = "\n".join(body_parts)
    gallery_refs = []
    for asset in image_assets:
        if not isinstance(asset, dict) or asset.get("status") != "saved":
            continue
        markdown_ref = str(asset.get("markdown_ref") or "").strip()
        local_path = str(asset.get("local_path") or "").strip()
        filename = Path(local_path).name if local_path else ""
        if markdown_ref and filename and filename not in existing_html:
            gallery_refs.append(markdown_ref)
    if gallery_refs:
        body_parts.append(
            "\n".join(
                [
                    '<section class="wechat-preview-section wechat-preview-gallery">',
                    "<h2>配图预览</h2>",
                    markdown_block_to_html("\n".join(gallery_refs)),
                    "</section>",
                ]
            )
        )

    body_html = "\n".join(body_parts)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title_html}</title>
  <style>
    :root {{ color-scheme: light; --ink: #172033; --muted: #667085; --accent: #3b82f6; --soft: #eef5ff; }}
    body {{ margin: 0; background: #f5f7fb; color: var(--ink); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif; }}
    .wechat-preview-shell {{ max-width: 760px; margin: 0 auto; padding: 32px 16px 48px; }}
    article.wechat-preview {{ background: #ffffff; border-radius: 24px; box-shadow: 0 18px 50px rgba(15, 23, 42, 0.08); padding: 38px 34px; line-height: 1.85; }}
    .eyebrow {{ color: var(--accent); font-size: 14px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }}
    h1 {{ font-size: 30px; line-height: 1.28; margin: 10px 0 18px; }}
    .digest {{ margin: 0 0 26px; padding: 16px 18px; background: var(--soft); border-left: 4px solid var(--accent); border-radius: 14px; color: #344054; }}
    h2 {{ margin-top: 34px; padding-top: 8px; font-size: 22px; line-height: 1.35; }}
    h3, h4, h5, h6 {{ margin-top: 24px; line-height: 1.45; }}
    p {{ margin: 12px 0; }}
    a {{ color: #2563eb; text-decoration: none; border-bottom: 1px solid rgba(37, 99, 235, .28); word-break: break-all; }}
    ul {{ padding-left: 1.2em; }}
    li {{ margin: 8px 0; }}
    figure {{ margin: 26px 0; }}
    img {{ display: block; max-width: 100%; border-radius: 18px; box-shadow: 0 10px 32px rgba(15, 23, 42, 0.10); }}
    figcaption {{ margin-top: 8px; color: var(--muted); font-size: 13px; text-align: center; }}
    code {{ background: #f2f4f7; padding: .12em .36em; border-radius: 6px; font-family: "SFMono-Regular", Consolas, monospace; font-size: .92em; }}
    .footer-note {{ margin-top: 36px; color: var(--muted); font-size: 13px; }}
    @media (max-width: 640px) {{ article.wechat-preview {{ padding: 28px 20px; border-radius: 18px; }} h1 {{ font-size: 25px; }} }}
  </style>
</head>
<body>
  <main class="wechat-preview-shell">
    <article class="wechat-preview">
      <div class="eyebrow">ClawMax WeChat Preview</div>
      <h1>{title_html}</h1>
      <div class="digest">{digest_html}</div>
      {body_html}
      <div class="footer-note">本 HTML 为本地预览/人工审阅排版稿，不代表已发布到公众号后台。Generated at {updated_at}</div>
    </article>
  </main>
</body>
</html>
"""


def validate_final_bundle(
    *,
    article_dir: Path,
    article: dict[str, Any],
    image_assets: list[dict[str, Any]],
    final_article_path: Path,
    html_preview_path: Path,
) -> None:
    require(final_article_path.is_file(), f"Missing final article: {final_article_path}")
    require(html_preview_path.is_file(), f"Missing HTML preview: {html_preview_path}")
    text = final_article_path.read_text(encoding="utf-8")
    html_text = html_preview_path.read_text(encoding="utf-8")
    for marker in ("# ", "## AI 前沿", "## 浪里淘金", "## 参考与信息来源"):
        require(marker in text, f"final article missing marker: {marker}")
    for marker in ("<article", "wechat-preview", "AI 前沿", "浪里淘金"):
        require(marker in html_text, f"HTML preview missing marker: {marker}")
    require("http://" in text or "https://" in text, "final article should preserve at least one source link")
    require("http://" in html_text or "https://" in html_text, "HTML preview should preserve at least one source link")

    manifest_path = article_dir / IMAGE_ASSETS_FILENAME
    require(manifest_path.is_file(), f"Missing image manifest: {manifest_path}")
    require((article_dir / IMAGES_DIRNAME).is_dir(), f"Missing images directory: {article_dir / IMAGES_DIRNAME}")

    saved_assets = [asset for asset in image_assets if isinstance(asset, dict) and asset.get("status") == "saved"]
    source_assets = [asset for asset in saved_assets if is_source_derived_asset(asset)]
    ai_bitmap_assets = [asset for asset in saved_assets if is_valid_ai_bitmap_asset(asset)]
    generated_svg_assets = [asset for asset in saved_assets if is_generated_svg_asset(asset)]
    cover_assets = [asset for asset in saved_assets if str(asset.get("purpose") or "").lower() == "cover"]
    require(len(saved_assets) >= MIN_ARTICLE_IMAGES, f"final article bundle must include at least {MIN_ARTICLE_IMAGES} saved images")
    require(len(source_assets) >= MIN_SOURCE_DERIVED_IMAGES, f"final article bundle must include at least {MIN_SOURCE_DERIVED_IMAGES} source-derived images with non-empty source_url")
    require(len(ai_bitmap_assets) >= MIN_AI_GENERATED_IMAGES, f"final article bundle must include at least {MIN_AI_GENERATED_IMAGES} real AI-generated bitmap image created via image_generate/gpt-image with non-empty prompt")
    require(len(generated_svg_assets) <= MAX_GENERATED_SVG_IMAGES, "generated SVG placeholder images are not allowed; use source-derived images or real image_generate bitmap output")
    require(len(cover_assets) <= MAX_COVER_IMAGES, f"final article bundle must include at most {MAX_COVER_IMAGES} cover-like image")
    validate_public_body_text(text, label="final article")
    validate_public_body_text(html_text, label="HTML preview")
    for asset in saved_assets:
        local_path = str(asset.get("local_path") or "")
        require(local_path.startswith(f"articles/{article_dir.name}/{IMAGES_DIRNAME}/"), f"image asset local_path must be in article images dir: {local_path}")
        require((article_dir.parent.parent / local_path).is_file(), f"image asset file does not exist: {local_path}")
        markdown_ref = str(asset.get("markdown_ref") or "")
        require(markdown_ref.startswith("![") and f"./{IMAGES_DIRNAME}/" in markdown_ref, f"image asset markdown_ref must be relative: {markdown_ref}")
        rel_ref = re.search(r"\(([^)]+)\)", markdown_ref)
        if rel_ref:
            require(rel_ref.group(1) in text or rel_ref.group(1) in html_text, f"image asset is not referenced by final Markdown or HTML: {rel_ref.group(1)}")

    require(article.get("image_assets") == image_assets, "article.json image_assets must match image-assets.json")


def finalize_wechat_article_bundle(
    *,
    repo_root: Path = REPO_ROOT,
    report_label: str,
    output_label: str | None = None,
    generator_profile: str = PROFILE_NAME,
    max_images: int = 5,
) -> dict[str, str | int]:
    repo_root = repo_root.resolve()
    report_label = safe_label(report_label)
    output_label = safe_label(output_label or report_label)
    report_dir = repo_root / "reports" / report_label
    article_dir = repo_root / "articles" / output_label
    article_path = article_dir / ARTICLE_JSON_FILENAME
    metadata_path = article_dir / METADATA_FILENAME
    final_article_path = article_dir / FINAL_ARTICLE_FILENAME
    html_preview_path = article_dir / HTML_PREVIEW_FILENAME
    image_assets_path = article_dir / IMAGE_ASSETS_FILENAME

    require(report_dir.is_dir(), f"Missing report directory: {report_dir}")
    require(article_dir.is_dir(), f"Missing article directory: {article_dir}")

    article = load_json(article_path)
    require(isinstance(article, dict), "article.json must be an object")
    validate_article_contract(article)

    article_image_assets = normalize_article_image_assets(article=article, article_dir=article_dir, repo_root=repo_root, max_images=max_images)
    report_image_assets = copy_report_images(report_dir=report_dir, article_dir=article_dir, repo_root=repo_root, max_images=max_images)
    image_assets = merge_image_assets(article_assets=article_image_assets, report_assets=report_image_assets, max_images=max_images)
    article["image_assets"] = image_assets
    article["final_article"] = rel_path(final_article_path, repo_root=repo_root)
    article["updated_at"] = now_iso()

    final_article = build_final_markdown(article, image_assets)
    html_preview = build_html_preview(article, image_assets)
    final_article_path.write_text(final_article, encoding="utf-8")
    html_preview_path.write_text(html_preview, encoding="utf-8")
    write_json(image_assets_path, image_assets)
    write_json(article_path, article)

    metadata = load_json(metadata_path) if metadata_path.is_file() else {}
    require(isinstance(metadata, dict), "metadata.json must be an object")
    metadata.update(
        {
            "source_report": rel_path(report_dir / "technical-report.md", repo_root=repo_root),
            "output_draft": rel_path(article_dir / DRAFT_FILENAME, repo_root=repo_root),
            "output_article_json": rel_path(article_path, repo_root=repo_root),
            "output_metadata": rel_path(metadata_path, repo_root=repo_root),
            "output_final_article": rel_path(final_article_path, repo_root=repo_root),
            "output_html_preview": rel_path(html_preview_path, repo_root=repo_root),
            "output_image_assets": rel_path(image_assets_path, repo_root=repo_root),
            "output_images_dir": rel_path(article_dir / IMAGES_DIRNAME, repo_root=repo_root),
            "finalized_at": article["updated_at"],
            "generator_profile": generator_profile,
            "auto_publish": False,
            "mode": "final_article_bundle",
        }
    )
    generated_files = []
    for path in (
        rel_path(article_dir / DRAFT_FILENAME, repo_root=repo_root),
        rel_path(article_path, repo_root=repo_root),
        rel_path(metadata_path, repo_root=repo_root),
        rel_path(final_article_path, repo_root=repo_root),
        rel_path(html_preview_path, repo_root=repo_root),
        rel_path(image_assets_path, repo_root=repo_root),
    ):
        generated_files.append(path)
    for asset in image_assets:
        if not isinstance(asset, dict) or asset.get("status") != "saved":
            continue
        local_path = str(asset.get("local_path") or "").strip()
        if local_path and local_path not in generated_files:
            generated_files.append(local_path)
    metadata["generated_files"] = generated_files
    write_json(metadata_path, metadata)

    validate_final_bundle(article_dir=article_dir, article=article, image_assets=image_assets, final_article_path=final_article_path, html_preview_path=html_preview_path)

    return {
        "article_dir": rel_path(article_dir, repo_root=repo_root),
        "final_article_path": rel_path(final_article_path, repo_root=repo_root),
        "html_preview_path": rel_path(html_preview_path, repo_root=repo_root),
        "image_assets_path": rel_path(image_assets_path, repo_root=repo_root),
        "image_count": len([asset for asset in image_assets if isinstance(asset, dict) and asset.get("status") == "saved"]),
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Finalize a ClawMax WeChat article bundle.")
    parser.add_argument("--report-label", required=True, help="Input report directory under reports/.")
    parser.add_argument("--output-label", default=None, help="Output article directory under articles/. Default: report label.")
    parser.add_argument("--max-images", type=int, default=5, help="Maximum report images to copy into the final article bundle.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    result = finalize_wechat_article_bundle(
        report_label=args.report_label,
        output_label=args.output_label,
        max_images=args.max_images,
    )
    print("PASS: finalized WeChat article bundle")
    print(f"Final article: {result['final_article_path']}")
    print(f"HTML preview: {result['html_preview_path']}")
    print(f"Image assets: {result['image_assets_path']}")
    print(f"Saved images: {result['image_count']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except FinalizeFailure as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
