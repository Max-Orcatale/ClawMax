#!/usr/bin/env python3
"""Create a WeChat Official Account draft from a ClawMax article bundle.

This is the first publishing adapter for ClawMax. It intentionally supports
only draft creation, not automatic publishing or mass sending.

Input:
  articles/<label>/article.json
  articles/<label>/image-assets.json
  articles/<label>/images/*

Output:
  articles/<label>/wechat-publish.json

Secrets:
  WECHAT_MP_APPID and WECHAT_MP_APPSECRET must come from the local runtime
  environment, normally synced from ~/.hermes/.env by
  scripts/install_hermes_profiles.py --configure-from-default.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import mimetypes
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
ARTICLES_DIR = REPO_ROOT / "articles"
PROJECT_CONFIG = REPO_ROOT / "config.yaml"
DEFAULT_MANIFEST_FILENAME = "wechat-publish.json"
WECHAT_API_BASE = "https://api.weixin.qq.com/cgi-bin"
SUPPORTED_MODES = {"draft"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
DEFAULT_HERMES_ENV = Path.home() / ".hermes" / ".env"


class PublishError(RuntimeError):
    pass


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PublishError(message)


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PublishError(f"Invalid JSON in {path}: {exc}") from exc


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_default_hermes_env(path: Path | None = None) -> None:
    """Load missing env vars from the user's default Hermes .env.

    Real secrets stay in local runtime files. Existing process env values win.
    """
    path = path or DEFAULT_HERMES_ENV
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def redacted_appid(appid: str) -> str:
    if len(appid) <= 6:
        return "***"
    return appid[:3] + "***" + appid[-3:]


def redact_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    redacted = []
    for key, value in query:
        lower = key.lower()
        if lower in {"secret", "access_token"}:
            value = "[REDACTED]"
        elif lower == "appid" and value:
            value = redacted_appid(value)
        redacted.append((key, value))
    return urllib.parse.urlunsplit(parsed._replace(query=urllib.parse.urlencode(redacted)))


def safe_label(label: str) -> str:
    require(label and "/" not in label and ".." not in label, f"Unsafe article label: {label!r}")
    return label


def load_credentials() -> tuple[str, str]:
    load_default_hermes_env()
    appid = os.environ.get("WECHAT_MP_APPID", "").strip()
    secret = os.environ.get("WECHAT_MP_APPSECRET", "").strip()
    missing = [name for name, value in (("WECHAT_MP_APPID", appid), ("WECHAT_MP_APPSECRET", secret)) if not value]
    if missing:
        raise PublishError(
            "Missing WeChat Official Account credentials: "
            + ", ".join(missing)
            + ". Put them in ~/.hermes/.env and run "
            + "python scripts/install_hermes_profiles.py --configure-from-default."
        )
    return appid, secret


def load_article_bundle(article_label: str) -> dict[str, Any]:
    article_dir = ARTICLES_DIR / safe_label(article_label)
    require(article_dir.is_dir(), f"Article directory not found: {article_dir}")

    article_json_path = article_dir / "article.json"
    image_assets_path = article_dir / "image-assets.json"
    final_article_path = article_dir / "final-wechat-article.md"

    for path in (article_json_path, image_assets_path, final_article_path):
        require(path.is_file(), f"Required article bundle file missing: {path}")

    article = load_json(article_json_path)
    image_assets = load_json(image_assets_path)
    require(isinstance(article, dict), "article.json must be a JSON object")
    require(isinstance(image_assets, list), "image-assets.json must be a JSON array")
    require(article.get("auto_publish_eligible") is False, "article.json auto_publish_eligible must be false")

    return {
        "article_label": article_label,
        "article_dir": article_dir,
        "article_json_path": article_json_path,
        "image_assets_path": image_assets_path,
        "final_article_path": final_article_path,
        "article": article,
        "image_assets": image_assets,
    }


def article_image_path(article_dir: Path, asset: dict[str, Any]) -> Path | None:
    raw = asset.get("local_path") or ""
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = REPO_ROOT / path
    if not path.exists():
        alt = article_dir / raw
        if alt.exists():
            path = alt
    return path


def markdown_ref_to_src(ref: str) -> str:
    match = re.match(r"!\[[^\]]*\]\(([^)]+)\)", ref.strip())
    if match:
        return match.group(1).strip()
    return ref.strip()


def image_ref_for_path(article_dir: Path, path: Path) -> str:
    try:
        return "./" + path.relative_to(article_dir).as_posix()
    except ValueError:
        try:
            return "./" + path.relative_to(article_dir / "images").as_posix()
        except ValueError:
            return path.as_posix()


def select_publish_images(article_dir: Path, image_assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for asset in image_assets:
        if not isinstance(asset, dict):
            continue
        path = article_image_path(article_dir, asset)
        if path is None or not path.is_file():
            continue
        if path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        if path in seen:
            continue
        seen.add(path)
        copied = dict(asset)
        copied["_local_file"] = path
        copied["_markdown_ref"] = markdown_ref_to_src(str(asset.get("markdown_ref") or "")) or image_ref_for_path(article_dir, path)
        selected.append(copied)
    require(selected, f"No local article images found under {article_dir}")
    return selected


def pick_thumb_image(images: list[dict[str, Any]]) -> dict[str, Any]:
    for asset in images:
        purpose = str(asset.get("purpose", "")).lower()
        if purpose == "cover" or "cover" in purpose:
            return asset
    return images[0]


def paragraphize_markdown(content_md: str) -> str:
    """Small conservative Markdown-to-HTML renderer for WeChat content.

    We intentionally avoid heavy CSS and complex Markdown features because the
    WeChat editor/API sanitizes aggressively. The generated local preview HTML is
    still useful for humans, but draft/add needs a compact official-account HTML
    body with uploaded image URLs.
    """
    lines = content_md.splitlines()
    out: list[str] = []
    in_ul = False

    def close_ul() -> None:
        nonlocal in_ul
        if in_ul:
            out.append("</ul>")
            in_ul = False

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            close_ul()
            continue
        image_match = re.match(r"!\[([^\]]*)\]\(([^)]+)\)", line)
        if image_match:
            close_ul()
            alt = html.escape(image_match.group(1))
            src = html.escape(image_match.group(2))
            out.append(
                '<p style="margin: 20px 0; text-align: center;">'
                f'<img src="{src}" alt="{alt}" style="max-width: 100%; height: auto; border-radius: 8px;" />'
                '</p>'
            )
            if alt:
                out.append(f'<p style="margin: -8px 0 20px; color: #888; font-size: 13px; text-align: center;">{alt}</p>')
            continue
        if line.startswith("### "):
            close_ul()
            out.append(f'<h3 style="margin: 24px 0 12px; font-size: 17px; line-height: 1.55; color: #222;">{html.escape(line[4:])}</h3>')
            continue
        if line.startswith("## "):
            close_ul()
            out.append(f'<h2 style="margin: 32px 0 16px; padding-left: 10px; border-left: 4px solid #2f6feb; font-size: 20px; line-height: 1.5; color: #111;">{html.escape(line[3:])}</h2>')
            continue
        if line.startswith("- "):
            if not in_ul:
                out.append('<ul style="margin: 12px 0 18px; padding-left: 22px; color: #333; line-height: 1.85;">')
                in_ul = True
            out.append(f'<li style="margin: 6px 0;">{inline_markdown_to_html(line[2:])}</li>')
            continue
        close_ul()
        out.append(f'<p style="margin: 14px 0; font-size: 16px; line-height: 1.9; color: #333;">{inline_markdown_to_html(line)}</p>')
    close_ul()
    return "\n".join(out)


def inline_markdown_to_html(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2">\1</a>', escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    return escaped


def render_wechat_html(article: dict[str, Any]) -> str:
    sections = article.get("sections") or []
    require(isinstance(sections, list) and sections, "article.json sections must be a non-empty array")
    chunks: list[str] = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        heading = str(section.get("heading") or "").strip()
        content_md = str(section.get("content_md") or "").strip()
        if heading:
            chunks.append(f'<h2 style="margin: 32px 0 16px; padding-left: 10px; border-left: 4px solid #2f6feb; font-size: 20px; line-height: 1.5; color: #111;">{html.escape(heading)}</h2>')
        if content_md:
            chunks.append(paragraphize_markdown(content_md))
    content = "\n".join(chunks).strip()
    require(content, "Rendered WeChat HTML content is empty")
    return f'<section style="font-size: 16px; line-height: 1.9; color: #333;">\n{content}\n</section>'


def replace_local_image_refs(html_body: str, upload_map: dict[str, str]) -> str:
    rendered = html_body
    for local_ref, wechat_url in sorted(upload_map.items(), key=lambda item: len(item[0]), reverse=True):
        rendered = rendered.replace(local_ref, wechat_url)
        rendered = rendered.replace(html.escape(local_ref), wechat_url)
    return rendered


def api_json_request(url: str, payload: dict[str, Any] | None = None, *, timeout: int = 30) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    request = urllib.request.Request(url, data=data, headers=headers)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise PublishError(f"WeChat API request failed: {redact_url(url)}: {exc}") from exc
    try:
        result = json.loads(body)
    except json.JSONDecodeError as exc:
        raise PublishError(f"WeChat API returned non-JSON response from {redact_url(url)}: {body[:200]}") from exc
    errcode = result.get("errcode")
    if errcode not in (None, 0):
        raise PublishError(f"WeChat API error from {redact_url(url)}: errcode={errcode}, errmsg={result.get('errmsg')}")
    return result


def encode_multipart_file(field_name: str, file_path: Path) -> tuple[bytes, str]:
    boundary = "clawmax-wechat-boundary"
    mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    file_bytes = file_path.read_bytes()
    parts = [
        f"--{boundary}\r\n".encode(),
        (
            f'Content-Disposition: form-data; name="{field_name}"; '
            f'filename="{file_path.name}"\r\n'
        ).encode(),
        f"Content-Type: {mime_type}\r\n\r\n".encode(),
        file_bytes,
        b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ]
    return b"".join(parts), boundary


def api_upload_file(url: str, file_path: Path, field_name: str = "media", *, timeout: int = 60) -> dict[str, Any]:
    body, boundary = encode_multipart_file(field_name, file_path)
    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Accept": "application/json",
    }
    request = urllib.request.Request(url, data=body, headers=headers)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise PublishError(f"WeChat file upload failed: {redact_url(url)}: {exc}") from exc
    try:
        result = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PublishError(f"WeChat upload returned non-JSON response from {redact_url(url)}: {raw[:200]}") from exc
    errcode = result.get("errcode")
    if errcode not in (None, 0):
        raise PublishError(f"WeChat upload error from {redact_url(url)}: errcode={errcode}, errmsg={result.get('errmsg')}")
    return result


def get_access_token(appid: str, secret: str) -> str:
    query = urllib.parse.urlencode({"grant_type": "client_credential", "appid": appid, "secret": secret})
    result = api_json_request(f"{WECHAT_API_BASE}/token?{query}")
    token = result.get("access_token")
    require(bool(token), "WeChat token response did not include access_token")
    return str(token)


def upload_content_image(access_token: str, image_path: Path) -> str:
    query = urllib.parse.urlencode({"access_token": access_token})
    result = api_upload_file(f"{WECHAT_API_BASE}/media/uploadimg?{query}", image_path)
    url = result.get("url")
    require(bool(url), f"WeChat uploadimg response did not include url for {image_path}")
    return str(url)


def upload_thumb_material(access_token: str, image_path: Path) -> str:
    query = urllib.parse.urlencode({"access_token": access_token, "type": "image"})
    result = api_upload_file(f"{WECHAT_API_BASE}/material/add_material?{query}", image_path)
    media_id = result.get("media_id")
    require(bool(media_id), f"WeChat add_material response did not include media_id for {image_path}")
    return str(media_id)


def add_draft(access_token: str, payload: dict[str, Any]) -> str:
    query = urllib.parse.urlencode({"access_token": access_token})
    result = api_json_request(f"{WECHAT_API_BASE}/draft/add?{query}", payload)
    media_id = result.get("media_id")
    require(bool(media_id), "WeChat draft/add response did not include media_id")
    return str(media_id)


def build_draft_payload(article: dict[str, Any], content_html: str, thumb_media_id: str, *, author: str, digest_max_chars: int) -> dict[str, Any]:
    title = str(article.get("title") or "").strip()
    digest = str(article.get("digest") or "").strip()
    require(title, "article.json title is required")
    if len(digest) > digest_max_chars:
        digest = digest[: digest_max_chars - 1] + "…"
    return {
        "articles": [
            {
                "title": title[:64],
                "author": author,
                "digest": digest,
                "content": content_html,
                "content_source_url": "",
                "thumb_media_id": thumb_media_id,
                "need_open_comment": 0,
                "only_fans_can_comment": 0,
            }
        ]
    }


def build_manifest(
    *,
    article_label: str,
    mode: str,
    status: str,
    appid: str | None,
    draft_media_id: str | None,
    uploaded_images: list[dict[str, Any]],
    thumb: dict[str, Any] | None,
    draft_payload_preview: dict[str, Any],
    errors: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "mode": mode,
        "article_label": article_label,
        "created_at": now_iso(),
        "auto_publish": False,
        "appid_hint": redacted_appid(appid) if appid else "",
        "draft_media_id": draft_media_id or "",
        "uploaded_images": uploaded_images,
        "thumb": thumb or {},
        "draft_payload_preview": {
            "title": draft_payload_preview.get("articles", [{}])[0].get("title", ""),
            "author": draft_payload_preview.get("articles", [{}])[0].get("author", ""),
            "digest": draft_payload_preview.get("articles", [{}])[0].get("digest", ""),
            "content_chars": len(draft_payload_preview.get("articles", [{}])[0].get("content", "")),
        },
        "errors": errors or [],
    }


def create_wechat_draft(article_label: str, *, dry_run: bool, author: str, digest_max_chars: int, manifest_filename: str) -> Path:
    bundle = load_article_bundle(article_label)
    article_dir: Path = bundle["article_dir"]
    article = bundle["article"]
    image_assets = bundle["image_assets"]
    images = select_publish_images(article_dir, image_assets)
    thumb_asset = pick_thumb_image(images)
    content_html = render_wechat_html(article)

    placeholder_thumb = "DRY_RUN_THUMB_MEDIA_ID"
    draft_payload = build_draft_payload(article, content_html, placeholder_thumb, author=author, digest_max_chars=digest_max_chars)
    manifest_path = article_dir / manifest_filename

    if dry_run:
        uploaded_images = []
        upload_map = {}
        for asset in images:
            local_path: Path = asset["_local_file"]
            local_ref = asset["_markdown_ref"]
            fake_url = f"https://mmbiz.example.invalid/{urllib.parse.quote(local_path.name)}"
            upload_map[local_ref] = fake_url
            uploaded_images.append(
                {
                    "local_path": str(local_path.relative_to(REPO_ROOT)),
                    "local_ref": local_ref,
                    "wechat_url": fake_url,
                    "usage": "content",
                }
            )
        dry_content = replace_local_image_refs(content_html, upload_map)
        dry_payload = build_draft_payload(article, dry_content, placeholder_thumb, author=author, digest_max_chars=digest_max_chars)
        manifest = build_manifest(
            article_label=article_label,
            mode="draft",
            status="dry_run",
            appid=None,
            draft_media_id=None,
            uploaded_images=uploaded_images,
            thumb={
                "local_path": str(thumb_asset["_local_file"].relative_to(REPO_ROOT)),
                "thumb_media_id": placeholder_thumb,
            },
            draft_payload_preview=dry_payload,
        )
        write_json(manifest_path, manifest)
        return manifest_path

    appid, secret = load_credentials()
    access_token = get_access_token(appid, secret)

    uploaded_images = []
    upload_map: dict[str, str] = {}
    for asset in images:
        local_path: Path = asset["_local_file"]
        local_ref = asset["_markdown_ref"]
        wechat_url = upload_content_image(access_token, local_path)
        upload_map[local_ref] = wechat_url
        uploaded_images.append(
            {
                "local_path": str(local_path.relative_to(REPO_ROOT)),
                "local_ref": local_ref,
                "wechat_url": wechat_url,
                "usage": "content",
            }
        )

    thumb_path: Path = thumb_asset["_local_file"]
    thumb_media_id = upload_thumb_material(access_token, thumb_path)
    final_content = replace_local_image_refs(content_html, upload_map)
    draft_payload = build_draft_payload(article, final_content, thumb_media_id, author=author, digest_max_chars=digest_max_chars)
    draft_media_id = add_draft(access_token, draft_payload)

    manifest = build_manifest(
        article_label=article_label,
        mode="draft",
        status="draft_created",
        appid=appid,
        draft_media_id=draft_media_id,
        uploaded_images=uploaded_images,
        thumb={
            "local_path": str(thumb_path.relative_to(REPO_ROOT)),
            "thumb_media_id": thumb_media_id,
        },
        draft_payload_preview=draft_payload,
    )
    write_json(manifest_path, manifest)
    return manifest_path


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a WeChat Official Account draft from a ClawMax article bundle.")
    parser.add_argument("--article-label", required=True, help="Directory name under articles/.")
    parser.add_argument("--mode", default="draft", help="Only 'draft' is supported in this version.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and write a dry-run manifest without calling WeChat APIs.")
    parser.add_argument("--author", default="ClawMax", help="WeChat article author field. Default: ClawMax.")
    parser.add_argument("--digest-max-chars", type=int, default=120, help="Max digest characters. Default: 120.")
    parser.add_argument("--manifest-filename", default=DEFAULT_MANIFEST_FILENAME, help="Output manifest filename under article dir.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.mode not in SUPPORTED_MODES:
        raise PublishError("Only draft mode is supported in this version. Automatic publishing is intentionally disabled.")
    manifest_path = create_wechat_draft(
        args.article_label,
        dry_run=args.dry_run,
        author=args.author,
        digest_max_chars=args.digest_max_chars,
        manifest_filename=args.manifest_filename,
    )
    if args.dry_run:
        print(f"PASS: dry-run WeChat draft manifest written: {manifest_path}")
    else:
        print(f"PASS: WeChat draft created; manifest written: {manifest_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PublishError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
