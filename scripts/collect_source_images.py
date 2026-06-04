#!/usr/bin/env python3
"""Collect source-derived visual assets for a ClawMax report.

This script is intentionally conservative. It reads reports/<label>/sources.json,
fetches source pages, extracts OpenGraph/Twitter image URLs, downloads usable images,
and writes reports/<label>/image-assets.json. It does not invent images and does not
call AI image generation.
"""

from __future__ import annotations

import argparse
from html.parser import HTMLParser
import json
import mimetypes
from pathlib import Path
import re
import sys
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = REPO_ROOT / "reports"
IMAGE_ASSETS_FILENAME = "image-assets.json"
IMAGES_DIRNAME = "images"
USER_AGENT = "Mozilla/5.0 (compatible; ClawMaxSourceImageCollector/0.1)"
MAX_BYTES = 8 * 1024 * 1024
TIMEOUT = 20


class CollectFailure(RuntimeError):
    pass


class MetaImageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.images: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {k.lower(): (v or "") for k, v in attrs}
        if tag.lower() == "meta":
            key = (attrs_dict.get("property") or attrs_dict.get("name") or "").lower()
            content = attrs_dict.get("content") or ""
            if key in {"og:image", "og:image:url", "twitter:image", "twitter:image:src"} and content:
                self.images.append((key, content.strip()))
        if tag.lower() == "link":
            rel = attrs_dict.get("rel", "").lower()
            href = attrs_dict.get("href") or ""
            if href and any(token in rel for token in ("image_src", "preload")):
                self.images.append((f"link:{rel}", href.strip()))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CollectFailure(message)


def safe_label(label: str) -> str:
    safe = re.sub(r"[^0-9A-Za-z_.-]+", "-", label.strip()).strip("-._")
    require(bool(safe), "label must not be empty")
    return safe[:120]


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CollectFailure(f"Missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CollectFailure(f"Invalid JSON in {path}: {exc}") from exc


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fetch_bytes(url: str, *, accept: str) -> tuple[bytes, str]:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    with urlopen(req, timeout=TIMEOUT) as response:  # noqa: S310 - user-controlled source URLs are project inputs.
        content_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = response.read(65536)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_BYTES:
                raise CollectFailure(f"Downloaded image exceeds {MAX_BYTES} bytes: {url}")
            chunks.append(chunk)
        return b"".join(chunks), content_type


def extract_meta_images(page_url: str) -> list[tuple[str, str]]:
    try:
        html_bytes, _ = fetch_bytes(page_url, accept="text/html,application/xhtml+xml")
    except Exception as exc:  # noqa: BLE001 - keep collector best-effort per source.
        print(f"WARN: failed to fetch page {page_url}: {exc}", file=sys.stderr)
        return []
    parser = MetaImageParser()
    parser.feed(html_bytes.decode("utf-8", errors="ignore"))
    resolved: list[tuple[str, str]] = []
    seen: set[str] = set()
    for kind, image_url in parser.images:
        absolute = urljoin(page_url, image_url)
        if absolute not in seen:
            seen.add(absolute)
            resolved.append((kind, absolute))
    return resolved


def filename_for(source_id: str, image_url: str, index: int, content_type: str) -> str:
    parsed = urlparse(image_url)
    suffix = Path(parsed.path).suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        suffix = mimetypes.guess_extension(content_type or "") or ".jpg"
    if suffix == ".jpe":
        suffix = ".jpg"
    slug = re.sub(r"[^0-9A-Za-z_.-]+", "-", source_id or "source").strip("-._")[:60] or "source"
    return f"{index:02d}-{slug}{suffix}"


def collect_source_images(report_label: str, *, max_images: int = 8) -> list[dict[str, Any]]:
    report_label = safe_label(report_label)
    report_dir = REPORTS_DIR / report_label
    sources_path = report_dir / "sources.json"
    require(report_dir.is_dir(), f"Missing report directory: {report_dir}")
    sources = load_json(sources_path)
    require(isinstance(sources, list), "sources.json must be an array")
    images_dir = report_dir / IMAGES_DIRNAME
    images_dir.mkdir(parents=True, exist_ok=True)

    assets: list[dict[str, Any]] = []
    seen_image_urls: set[str] = set()
    for source in sources:
        if len(assets) >= max_images:
            break
        if not isinstance(source, dict):
            continue
        page_url = str(source.get("url") or "").strip()
        if not page_url.startswith(("http://", "https://")):
            continue
        source_id = str(source.get("id") or source.get("title") or f"source-{len(assets)+1}")
        for meta_kind, image_url in extract_meta_images(page_url):
            if len(assets) >= max_images:
                break
            if image_url in seen_image_urls:
                continue
            seen_image_urls.add(image_url)
            try:
                image_bytes, content_type = fetch_bytes(image_url, accept="image/avif,image/webp,image/png,image/jpeg,image/*")
            except Exception as exc:  # noqa: BLE001
                print(f"WARN: failed to download image {image_url}: {exc}", file=sys.stderr)
                continue
            if not image_bytes or not (content_type.startswith("image/") or Path(urlparse(image_url).path).suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif"}):
                continue
            filename = filename_for(source_id, image_url, len(assets) + 1, content_type)
            local_file = images_dir / filename
            local_file.write_bytes(image_bytes)
            rel = local_file.relative_to(REPO_ROOT).as_posix()
            caption = str(source.get("title") or "信源配图").strip()
            assets.append(
                {
                    "id": Path(filename).stem,
                    "kind": "og_image" if "og:" in meta_kind else "source_image",
                    "purpose": "source_illustration",
                    "local_path": rel,
                    "markdown_ref": f"![{caption}](./{IMAGES_DIRNAME}/{filename})",
                    "caption": caption,
                    "source_url": page_url,
                    "source_image_url": image_url,
                    "source_title": str(source.get("title") or ""),
                    "license_or_usage_note": "Source-derived image captured from page metadata; review rights before publishing.",
                    "generation_prompt": "",
                    "status": "saved",
                    "notes": f"Collected from {meta_kind} metadata by collect_source_images.py.",
                }
            )

    write_json(report_dir / IMAGE_ASSETS_FILENAME, assets)
    return assets


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect source-derived image assets for a ClawMax report.")
    parser.add_argument("--report-label", required=True, help="Report directory under reports/.")
    parser.add_argument("--max-images", type=int, default=8, help="Maximum source-derived images to save. Default: 8.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    assets = collect_source_images(args.report_label, max_images=args.max_images)
    print(f"PASS: collected {len(assets)} source-derived images")
    print(f"Manifest: reports/{safe_label(args.report_label)}/{IMAGE_ASSETS_FILENAME}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except CollectFailure as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
