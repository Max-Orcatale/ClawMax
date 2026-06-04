#!/usr/bin/env python3
"""
Integration test for running ClawMax TechnicalReportAgent through Hermes.

Default mode: generate a real-source daily AI technical report.

Purpose:
- Verify Hermes can run with the `technicalreportagent` profile.
- Verify the run uses the project profile source and loaded skills.
- Verify the agent automatically searches for real sources in normal daily-report mode.
- Verify the generated report is a professional technical report, not a workflow-test writeup.

Usage from repo root:

    python tests/test_technical_report_agent_run.py --dry-run
    python tests/test_technical_report_agent_run.py

Useful options:

    python tests/test_technical_report_agent_run.py --date 2026-05-24
    python tests/test_technical_report_agent_run.py --official-today-output
    python tests/test_technical_report_agent_run.py --force
    python tests/test_technical_report_agent_run.py --mock-smoke

Notes:
- This is an integration test. It calls the real `hermes` CLI and may use model/API quota.
- Default mode uses real source search. It must not use mock sources.
- Mock mode is only for engineering smoke tests and must be explicitly requested with `--mock-smoke`.
- By default it writes to a unique test date label such as
  reports/2026-05-24-test-143012 to avoid overwriting formal daily reports.
- Pass `--official-today-output` only if you intentionally want to write to
  reports/YYYY-MM-DD. The script will refuse to overwrite existing files unless
  `--force` is also passed.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Iterable
from urllib.parse import urlparse


REPO_ROOT = Path(__file__).resolve().parents[1]
PERSONA_FILE = REPO_ROOT / "profiles" / "technical-report-agent.md"
CONFIG_FILE = REPO_ROOT / "config.yaml"
REPORTS_DIR = REPO_ROOT / "reports"
RUNS_DIR = REPO_ROOT / "runs"
PROJECT_MEMORY_DIR = REPO_ROOT / "memory"
COVERED_TOPICS_FILE = PROJECT_MEMORY_DIR / "covered-topics.json"
SOURCE_QUALITY_FILE = PROJECT_MEMORY_DIR / "source-quality.json"

TECHNICAL_REPORT_SKILL = "clawmax:ai-technical-report"
PIPELINE_SKILL = "clawmax:daily-ai-media-pipeline"
PROFILE_NAME = "technicalreportagent"

REQUIRED_REPORT_SECTIONS = [
    "## 今日摘要",
    "## 重点新闻",
    "## 论文与研究进展",
    "## 公司与产品动态",
    "## 开源项目与开发者生态",
    "## 具身智能专题",
    "## 风险、争议与待确认信息",
    "## 来源链接",
]

FORBIDDEN_REPORT_PHRASES = [
    "对内容创作的可用素材",
    "本次最小实验",
    "集成测试说明",
    "报告目的不是判断真实产业动态",
    "是否具备固定章节",
    "是否保留可追溯字段",
    "是否能作为",
    "本次不生成图片，因为集成测试目标",
    "mock sources 生成",
    "模拟来源",
]

DEPTH_MARKERS = [
    "事实更新",
    "技术背景",
    "关键变化",
    "影响判断",
    "风险与不确定性",
    "后续观察",
]

MIN_REAL_REPORT_CHARS = 3500
MIN_SOURCE_IMAGES = 3
SOURCE_IMAGE_KINDS = {"official_image", "official_screenshot", "source_screenshot", "webpage_screenshot", "paper_figure", "github_screenshot", "product_screenshot", "og_image", "web_source", "source_image"}

REQUIRED_SOURCE_KEYS = {
    "title",
    "url",
    "source_type",
    "published_at",
    "retrieved_at",
    "summary",
    "confidence",
    "tags",
}

VALID_CONFIDENCE = {"high", "medium", "low"}

PROXY_ENV_KEYS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "no_proxy",
)


class TestFailure(RuntimeError):
    pass


def fail(message: str) -> None:
    raise TestFailure(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_jsonl(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(data, ensure_ascii=False, sort_keys=True) + "\n")


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def load_json_file(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(read_text(path))
    except json.JSONDecodeError:
        return default


def load_json(path: Path):
    try:
        return json.loads(read_text(path))
    except json.JSONDecodeError as exc:
        fail(f"Invalid JSON: {path} -> {exc}")


def run_readonly(command: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
    )


def check_prerequisites() -> None:
    require(PERSONA_FILE.is_file(), f"Missing persona file: {PERSONA_FILE}")
    require(CONFIG_FILE.is_file(), f"Missing config file: {CONFIG_FILE}")
    hermes_path = shutil.which("hermes")
    require(hermes_path is not None, "`hermes` CLI not found on PATH")

    profile_result = run_readonly(["hermes", "profile", "list"])
    require(profile_result.returncode == 0, "`hermes profile list` failed:\n" + profile_result.stdout)
    require(PROFILE_NAME in profile_result.stdout, f"Hermes profile `{PROFILE_NAME}` not found. Output:\n{profile_result.stdout}")

    skills_result = run_readonly(["hermes", "-p", PROFILE_NAME, "skills", "list"], timeout=90)
    require(skills_result.returncode == 0, "`hermes -p technicalreportagent skills list` failed:\n" + skills_result.stdout)
    require("ai-technical-report" in skills_result.stdout, "Skill `ai-technical-report` not visible in technicalreportagent profile")
    require("daily-ai-media-pipeline" in skills_result.stdout, "Skill `daily-ai-media-pipeline` not visible in technicalreportagent profile")

    tools_result = run_readonly(["hermes", "-p", PROFILE_NAME, "tools", "list"], timeout=90)
    require(tools_result.returncode == 0, "`hermes -p technicalreportagent tools list` failed:\n" + tools_result.stdout)
    require("enabled  web" in tools_result.stdout or "✓ enabled  web" in tools_result.stdout, "technicalreportagent profile must have web toolset enabled for real-source report generation")


def proxy_env_snapshot() -> dict[str, str]:
    return {key: os.environ[key] for key in PROXY_ENV_KEYS if os.environ.get(key)}


def build_subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    for key, value in proxy_env_snapshot().items():
        env[key] = value
    return env


def print_proxy_status() -> None:
    proxies = proxy_env_snapshot()
    if not proxies:
        print("Proxy env: none detected; Hermes will run without HTTP(S)/SOCKS proxy env vars.")
        return
    print("Proxy env inherited by Hermes:")
    for key in PROXY_ENV_KEYS:
        if key in proxies:
            print(f"- {key}={proxies[key]}")


def build_real_prompt(output_label: str) -> str:
    return f"""
请生成一份真实来源的 ClawMax 每日 AI 技术报告。

运行参数：
- profile: technicalreportagent
- skills: {TECHNICAL_REPORT_SKILL}, {PIPELINE_SKILL}
- mode: real sources
- output_dir: reports/{output_label}/
- outputs: technical-report.md, sources.json, brief.json, image-assets.json, images/*
- source window: rolling recent window, not only today
- source budget: 8-12 high-quality sources, scope intentionally expanded for this run
- include source types: official updates, papers/benchmarks, GitHub projects/releases, developer ecosystem signals, product/tool demos, visual-friendly sources
- network timeout per request: 15 seconds
- visual asset requirement: collect source-derived images during or immediately after source collection

要求：
- 自动检索真实资料。
- 不使用 mock、模拟或 example.com。
- 不要自动发布。
- 本轮必须抓取信源图片，不允许以“图片不是必要”为由跳过。
- 必须在 reports/{output_label}/image-assets.json 记录 source-derived visual assets；优先官方图、网页/产品截图、论文图、GitHub/项目图、og:image。
- 如果 agent 自己无法抓够图片，必须明确说明失败原因；不要用 AI 生成图或手写 SVG 冒充信源图。
- 完成后只简要说明生成了哪些文件。
""".strip()


def build_mock_smoke_prompt(output_label: str) -> str:
    return f"""
请执行 ClawMax TechnicalReportAgent 的工程烟测。

运行参数：
- profile: technicalreportagent
- skills: {TECHNICAL_REPORT_SKILL}, {PIPELINE_SKILL}
- mode: mock smoke test
- output_dir: reports/{output_label}/
- outputs: technical-report.md, sources.json, brief.json

要求：
- 只验证 Hermes profile、skills 和文件写入链路。
- 明确标注这是工程烟测，不是专业日报。
- 不要自动发布。
""".strip()


def build_prompt(output_label: str, *, mock_smoke: bool) -> str:
    return build_mock_smoke_prompt(output_label) if mock_smoke else build_real_prompt(output_label)


def build_command(output_label: str, *, mock_smoke: bool) -> list[str]:
    return [
        "hermes",
        "-p",
        PROFILE_NAME,
        "-s",
        TECHNICAL_REPORT_SKILL,
        "-s",
        PIPELINE_SKILL,
        "chat",
        "-q",
        build_prompt(output_label, mock_smoke=mock_smoke),
    ]


def ensure_safe_output_dir(output_dir: Path, force: bool) -> None:
    if not output_dir.exists():
        return
    existing_files = sorted(p for p in output_dir.rglob("*") if p.is_file())
    if existing_files and not force:
        listed = "\n".join(f"- {p.relative_to(REPO_ROOT)}" for p in existing_files[:20])
        fail(
            f"Output directory already contains files and --force was not passed: {output_dir}\n"
            f"Existing files:\n{listed}"
        )
    if force:
        shutil.rmtree(output_dir)


def run_hermes(output_label: str, timeout_seconds: int, *, mock_smoke: bool) -> int:
    command = build_command(output_label, mock_smoke=mock_smoke)
    process = subprocess.Popen(
        command,
        cwd=REPO_ROOT,
        env=build_subprocess_env(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
    )
    assert process.stdout is not None
    output_chunks: list[str] = []
    deadline = dt.datetime.now() + dt.timedelta(seconds=timeout_seconds)
    try:
        while True:
            line = process.stdout.readline()
            if line:
                print(line, end="", flush=True)
                output_chunks.append(line)
            elif process.poll() is not None:
                break
            elif dt.datetime.now() > deadline:
                process.kill()
                remaining = process.communicate()[0] or ""
                if remaining:
                    print(remaining, end="", flush=True)
                    output_chunks.append(remaining)
                raise subprocess.TimeoutExpired(command, timeout_seconds, output="".join(output_chunks))
        remaining = process.stdout.read() or ""
        if remaining:
            print(remaining, end="", flush=True)
            output_chunks.append(remaining)
        return process.wait()
    finally:
        if process.poll() is None:
            process.kill()



def is_valid_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def validate_sources(path: Path, *, mock_smoke: bool) -> None:
    data = load_json(path)
    require(isinstance(data, list), "sources.json should be a JSON array")
    require(len(data) >= 3, "sources.json should contain at least 3 source records")

    serialized = json.dumps(data, ensure_ascii=False).lower()
    if mock_smoke:
        require("mock" in serialized or "模拟" in serialized, "mock smoke sources should explicitly indicate mock/simulated sources")
    else:
        require("example.com" not in serialized, "real-source report must not use example.com URLs")
        require("mock" not in serialized and "模拟" not in serialized, "real-source report must not use mock/simulated sources")

    for index, item in enumerate(data):
        require(isinstance(item, dict), f"sources.json item #{index} should be an object")
        missing = REQUIRED_SOURCE_KEYS - set(item)
        require(not missing, f"sources.json item #{index} missing keys: {sorted(missing)}")
        title = str(item.get("title", "")).strip()
        url = str(item.get("url", "")).strip()
        require(title, f"sources.json item #{index} has empty title")
        require(url, f"sources.json item #{index} has empty url")
        require(is_valid_url(url), f"sources.json item #{index} has invalid URL: {url!r}")
        require(item.get("confidence") in VALID_CONFIDENCE, f"sources.json item #{index} has invalid confidence: {item.get('confidence')!r}")
        require(isinstance(item.get("tags"), list), f"sources.json item #{index} tags should be a list")


def validate_brief(path: Path) -> None:
    data = load_json(path)
    require(isinstance(data, dict), "brief.json should be a JSON object")
    for key in ["date", "title", "summary", "top_items", "risks", "ready_for_wechat_drafting"]:
        require(key in data, f"brief.json missing key: {key}")
    require(isinstance(data["top_items"], list), "brief.json top_items should be a list")
    require(len(data["top_items"]) >= 1, "brief.json top_items should not be empty")
    require(isinstance(data["risks"], list), "brief.json risks should be a list")
    require(data["ready_for_wechat_drafting"] is True, "brief.json ready_for_wechat_drafting should be true")


def validate_report(path: Path, *, mock_smoke: bool) -> None:
    text = read_text(path)
    require("技术报告" in text or "工程烟测" in text, "technical-report.md should have an appropriate title")
    require("http://" in text or "https://" in text, "technical-report.md should include source links")
    require("待确认" in text or "不确定" in text or "风险" in text, "technical-report.md should include uncertainty/risk wording")

    if mock_smoke:
        require("工程烟测" in text, "mock smoke report should clearly identify itself as an engineering smoke test")
        return

    for section in REQUIRED_REPORT_SECTIONS:
        require(section in text, f"technical-report.md missing required section: {section}")
    for phrase in FORBIDDEN_REPORT_PHRASES:
        require(phrase not in text, f"technical-report.md contains forbidden test/downstream phrase: {phrase}")
    lower = text.lower()
    require("example.com" not in lower, "real-source report must not include example.com")
    require("mock sources" not in lower, "real-source report must not mention mock sources")
    require(len(text) >= MIN_REAL_REPORT_CHARS, f"real-source report is too short: {len(text)} chars < {MIN_REAL_REPORT_CHARS}")
    require(sum(1 for marker in DEPTH_MARKERS if marker in text) >= 4, "real-source report should show deeper analysis markers like 事实更新/技术背景/影响判断/后续观察")



def run_source_image_collector(output_label: str) -> None:
    collector = REPO_ROOT / "scripts" / "collect_source_images.py"
    require(collector.is_file(), f"Missing source image collector: {collector}")
    result = subprocess.run(
        [sys.executable, str(collector), "--report-label", output_label, "--max-images", "10"],
        cwd=REPO_ROOT,
        env=build_subprocess_env(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=180,
    )
    print(result.stdout)
    require(result.returncode == 0, "source image collector failed:\n" + result.stdout)


def validate_report_images(output_label: str) -> list[dict]:
    output_dir = REPORTS_DIR / output_label
    manifest_path = output_dir / "image-assets.json"
    require(manifest_path.is_file(), f"Missing report image manifest: {manifest_path}")
    assets = load_json(manifest_path)
    require(isinstance(assets, list), "report image-assets.json should be a JSON array")
    source_assets = []
    for index, asset in enumerate(assets):
        require(isinstance(asset, dict), f"image-assets.json item #{index} should be an object")
        kind = str(asset.get("kind") or "").strip()
        source_url = str(asset.get("source_url") or "").strip()
        local_path = str(asset.get("local_path") or "").strip()
        if kind in SOURCE_IMAGE_KINDS and source_url:
            source_assets.append(asset)
        require(local_path, f"image-assets.json item #{index} missing local_path")
        image_path = REPO_ROOT / local_path if not Path(local_path).is_absolute() else Path(local_path)
        require(image_path.is_file(), f"image asset file missing: {local_path}")
    require(
        len(source_assets) >= MIN_SOURCE_IMAGES,
        f"report must include at least {MIN_SOURCE_IMAGES} source-derived images with source_url; got {len(source_assets)}",
    )
    return assets

def validate_outputs(output_label: str, *, mock_smoke: bool) -> dict:
    output_dir = REPORTS_DIR / output_label
    report_path = output_dir / "technical-report.md"
    sources_path = output_dir / "sources.json"
    brief_path = output_dir / "brief.json"
    image_assets_path = output_dir / "image-assets.json"

    require(output_dir.is_dir(), f"Output directory missing: {output_dir}")
    require(report_path.is_file(), f"Missing file: {report_path}")
    require(sources_path.is_file(), f"Missing file: {sources_path}")
    require(brief_path.is_file(), f"Missing file: {brief_path}")

    validate_report(report_path, mock_smoke=mock_smoke)
    validate_sources(sources_path, mock_smoke=mock_smoke)
    validate_brief(brief_path)
    image_assets = [] if mock_smoke else validate_report_images(output_label)
    return {
        "output_dir": str(output_dir.relative_to(REPO_ROOT)),
        "report_path": str(report_path.relative_to(REPO_ROOT)),
        "sources_path": str(sources_path.relative_to(REPO_ROOT)),
        "brief_path": str(brief_path.relative_to(REPO_ROOT)),
        "brief": load_json(brief_path),
        "sources": load_json(sources_path),
        "image_assets_path": str(image_assets_path.relative_to(REPO_ROOT)) if image_assets_path.exists() else "",
        "image_assets": image_assets,
        "report_chars": len(read_text(report_path)),
    }


def normalize_topic_title(value: str) -> str:
    return " ".join(str(value).strip().split())[:160]


def update_covered_topics(run_id: str, output_label: str, validation: dict) -> int:
    brief = validation.get("brief") or {}
    existing = load_json_file(COVERED_TOPICS_FILE, [])
    if not isinstance(existing, list):
        existing = []
    by_topic = {normalize_topic_title(item.get("topic", "")): item for item in existing if isinstance(item, dict)}

    candidates: list[str] = []
    for item in brief.get("top_items", []):
        if isinstance(item, dict):
            candidates.append(item.get("title") or item.get("topic") or item.get("summary") or "")
        else:
            candidates.append(str(item))
    if not candidates and brief.get("title"):
        candidates.append(str(brief["title"]))

    updated_count = 0
    for raw_title in candidates:
        topic = normalize_topic_title(raw_title)
        if not topic:
            continue
        record = by_topic.get(topic, {"topic": topic, "first_covered_at": now_iso(), "covered_count": 0})
        record.update(
            {
                "last_covered_at": now_iso(),
                "last_output_label": output_label,
                "last_run_id": run_id,
                "last_summary": normalize_topic_title(brief.get("summary", "")),
                "repeat_policy": "Mention again only when there is a release, benchmark, adoption signal, GitHub activity change, pricing/business update, or controversy escalation.",
            }
        )
        record["covered_count"] = int(record.get("covered_count", 0)) + 1
        by_topic[topic] = record
        updated_count += 1

    write_json(COVERED_TOPICS_FILE, sorted(by_topic.values(), key=lambda item: item.get("topic", "")))
    return updated_count


def update_source_quality(run_id: str, output_label: str, validation: dict) -> int:
    data = load_json_file(SOURCE_QUALITY_FILE, {})
    if not isinstance(data, dict):
        data = {}
    updated_count = 0
    for source in validation.get("sources") or []:
        if not isinstance(source, dict):
            continue
        url = str(source.get("url", ""))
        host = urlparse(url).netloc.lower()
        if not host:
            continue
        record = data.get(host, {"host": host, "seen_count": 0, "confidence_counts": {}})
        record["seen_count"] = int(record.get("seen_count", 0)) + 1
        record["last_seen_at"] = now_iso()
        record["last_output_label"] = output_label
        record["last_run_id"] = run_id
        confidence = str(source.get("confidence", "unknown"))
        counts = record.setdefault("confidence_counts", {})
        counts[confidence] = int(counts.get(confidence, 0)) + 1
        tags = set(record.get("tags", []))
        for tag in source.get("tags", []):
            tags.add(str(tag))
        record["tags"] = sorted(tags)
        data[host] = record
        updated_count += 1
    write_json(SOURCE_QUALITY_FILE, dict(sorted(data.items())))
    return updated_count


def write_run_log(run_id: str, event: dict) -> None:
    append_jsonl(RUNS_DIR / "daily-report-runs.jsonl", {"run_id": run_id, **event})
    write_json(RUNS_DIR / f"{run_id}.json", {"run_id": run_id, **event})


def make_output_label(args: argparse.Namespace) -> str:
    base_date = args.date or dt.date.today().isoformat()
    if args.official_today_output:
        return base_date
    stamp = dt.datetime.now().strftime("%H%M%S")
    mode = "mock-smoke" if args.mock_smoke else "real-test"
    return f"{base_date}-{mode}-{stamp}"


def quote_command(command: Iterable[str]) -> str:
    import shlex

    return " ".join(shlex.quote(part) for part in command)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Hermes as ClawMax TechnicalReportAgent and validate generated report files.")
    parser.add_argument("--date", default=None, help="Base date to use, default: today, format YYYY-MM-DD.")
    parser.add_argument("--official-today-output", action="store_true", help="Write to reports/YYYY-MM-DD instead of a unique reports/YYYY-MM-DD-real-test-HHMMSS directory.")
    parser.add_argument("--force", action="store_true", help="Delete existing output directory before running.")
    parser.add_argument("--dry-run", action="store_true", help="Print the Hermes command without executing it.")
    parser.add_argument("--timeout", type=int, default=1200, help="Hermes run timeout in seconds. Default: 1200.")
    parser.add_argument("--mock-smoke", action="store_true", help="Run explicit mock engineering smoke test instead of real-source daily report test.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    started_at = now_iso()
    start_time = dt.datetime.now(dt.timezone.utc)
    output_label = make_output_label(args)
    run_id = output_label
    output_dir = REPORTS_DIR / output_label
    command = build_command(output_label, mock_smoke=args.mock_smoke)

    print(f"Repo root: {REPO_ROOT}")
    print(f"Mode: {'mock smoke' if args.mock_smoke else 'real sources'}")
    print(f"Output label: {output_label}")
    print(f"Output dir: {output_dir}")
    print_proxy_status()

    if args.dry_run:
        print("\nDry run command:\n")
        print(quote_command(command))
        return 0

    check_prerequisites()
    ensure_safe_output_dir(output_dir, force=args.force)

    print("\nRunning Hermes TechnicalReportAgent integration test...\n")
    exit_code = run_hermes(output_label=output_label, timeout_seconds=args.timeout, mock_smoke=args.mock_smoke)
    require(exit_code == 0, f"Hermes command failed with exit code {exit_code}")

    if not args.mock_smoke:
        print("\nCollecting/verifying report-side source images...\n")
        run_source_image_collector(output_label)

    print("\nValidating generated files...\n")
    validation = validate_outputs(output_label, mock_smoke=args.mock_smoke)
    topics_updated = 0
    sources_updated = 0
    if not args.mock_smoke:
        topics_updated = update_covered_topics(run_id, output_label, validation)
        sources_updated = update_source_quality(run_id, output_label, validation)

    finished_at = now_iso()
    duration_seconds = round((dt.datetime.now(dt.timezone.utc) - start_time).total_seconds(), 3)
    write_run_log(
        run_id,
        {
            "status": "completed",
            "mode": "mock_smoke" if args.mock_smoke else "real_sources",
            "profile": PROFILE_NAME,
            "skills": [TECHNICAL_REPORT_SKILL, PIPELINE_SKILL],
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_seconds": duration_seconds,
            "output_label": output_label,
            "output_dir": validation["output_dir"],
            "outputs": {
                "report": validation["report_path"],
                "sources": validation["sources_path"],
                "brief": validation["brief_path"],
                "image_assets": validation.get("image_assets_path", ""),
            },
            "metrics": {
                "report_chars": validation["report_chars"],
                "sources_used": len(validation.get("sources") or []),
                "source_images": len(validation.get("image_assets") or []),
                "covered_topics_updated": topics_updated,
                "source_hosts_updated": sources_updated,
            },
            "proxy_env_keys": sorted(proxy_env_snapshot().keys()),
        },
    )

    print("PASS: TechnicalReportAgent generated a valid report bundle.")
    print(f"Report bundle: {output_dir}")
    print(f"Run log: {RUNS_DIR / (run_id + '.json')}")
    if not args.mock_smoke:
        print(f"Project memory updated: {COVERED_TOPICS_FILE}, {SOURCE_QUALITY_FILE}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except TestFailure as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
    except subprocess.TimeoutExpired as exc:
        print(f"FAIL: command timed out after {exc.timeout} seconds", file=sys.stderr)
        if exc.stdout:
            print(exc.stdout, file=sys.stderr)
        raise SystemExit(1)
