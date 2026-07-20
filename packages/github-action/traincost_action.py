#!/usr/bin/env python3
"""GitHub Action entrypoint for TrainCost CI."""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Mapping


ACTION_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = ACTION_DIR.parents[1]
CORE_SRC = PROJECT_ROOT / "packages" / "core" / "src"
if CORE_SRC.exists():
    sys.path.insert(0, str(CORE_SRC))

from traincost_ci_core import analyze_configs, normalize_training_config, parse_config_text  # noqa: E402


SUPPORTED_SUFFIXES = {".yaml", ".yml", ".json", ".py"}
COMMENT_MARKER = "<!-- traincost-ci-report -->"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = Path(args.repo_root).resolve()

    try:
        gpu_prices = parse_gpu_prices(args.gpu_prices)
        budget_limit = parse_budget_limit(args.budget_limit)
    except ValueError as exc:
        print(f"TrainCost CI input error: {exc}", file=sys.stderr)
        return 2

    report_path = Path(args.report_path)
    if not report_path.is_absolute():
        report_path = repo_root / report_path

    if args.base_config and args.head_config:
        report = run_local_pair(
            Path(args.base_config),
            Path(args.head_config),
            default_budget_limit_usd=budget_limit,
            gpu_hourly_prices=gpu_prices,
        )
    else:
        event = load_event(args.event_path)
        report = run_pull_request_analysis(
            repo_root=repo_root,
            event=event,
            event_name=args.event_name,
            config_path_input=args.config_path,
            default_budget_limit_usd=budget_limit,
            gpu_hourly_prices=gpu_prices,
        )

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    print(f"TrainCost CI wrote report to {report_path}")

    comment_posted = False
    if parse_bool(args.comment_mode):
        event = load_event(args.event_path)
        comment_posted = post_or_update_pr_comment(event, report)
        if not comment_posted:
            print("TrainCost CI saved the report but did not post a PR comment.")

    write_output("report-path", str(report_path))
    write_output("comment-posted", "true" if comment_posted else "false")
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run TrainCost CI cost analysis.")
    parser.add_argument("--config-path", default=os.getenv("INPUT_CONFIG_PATH", "config.yaml"))
    parser.add_argument("--gpu-prices", default=os.getenv("INPUT_GPU_PRICES", ""))
    parser.add_argument("--budget-limit", default=os.getenv("INPUT_BUDGET_LIMIT", ""))
    parser.add_argument("--comment-mode", default=os.getenv("INPUT_COMMENT_MODE", "false"))
    parser.add_argument("--report-path", default=os.getenv("INPUT_REPORT_PATH", "report.md"))
    parser.add_argument("--event-path", default=os.getenv("GITHUB_EVENT_PATH", ""))
    parser.add_argument("--event-name", default=os.getenv("GITHUB_EVENT_NAME", ""))
    parser.add_argument("--repo-root", default=os.getenv("GITHUB_WORKSPACE", os.getcwd()))
    parser.add_argument("--base-config", default="")
    parser.add_argument("--head-config", default="")
    return parser.parse_args(argv)


def parse_gpu_prices(value: str | None) -> dict[str, float]:
    """Parse T4=0.5,A100=3.5 style GPU hourly prices."""

    prices: dict[str, float] = {}
    if not value or not value.strip():
        return prices

    for raw_part in value.split(","):
        part = raw_part.strip()
        if not part:
            continue
        if "=" not in part:
            raise ValueError(f"invalid gpu-prices entry {part!r}; expected NAME=PRICE")
        gpu_type, price_text = part.split("=", 1)
        gpu_type = gpu_type.strip()
        if not gpu_type:
            raise ValueError("gpu-prices contains an empty GPU type")
        try:
            price = float(price_text.strip())
        except ValueError as exc:
            raise ValueError(f"invalid hourly price for {gpu_type!r}") from exc
        if price < 0:
            raise ValueError(f"invalid negative hourly price for {gpu_type!r}")
        prices[gpu_type] = price
    return prices


def parse_budget_limit(value: str | None) -> float | None:
    if value is None or value.strip() == "":
        return None
    try:
        budget = float(value.strip())
    except ValueError as exc:
        raise ValueError("budget-limit must be a number") from exc
    if budget < 0:
        raise ValueError("budget-limit must not be negative")
    return budget


def parse_bool(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def load_event(event_path: str | None) -> dict[str, Any]:
    if not event_path:
        return {}
    path = Path(event_path)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def run_local_pair(
    base_path: Path,
    head_path: Path,
    *,
    default_budget_limit_usd: float | None,
    gpu_hourly_prices: Mapping[str, float],
) -> str:
    base_text = base_path.read_text(encoding="utf-8")
    head_text = head_path.read_text(encoding="utf-8")
    item = analyze_config_texts(
        display_path=str(head_path),
        base_text=base_text,
        head_text=head_text,
        file_suffix=head_path.suffix,
        default_budget_limit_usd=default_budget_limit_usd,
        gpu_hourly_prices=gpu_hourly_prices,
    )
    if item["report"]:
        return item["report"]
    return render_no_config_report([str(head_path)], item["notes"])


def run_pull_request_analysis(
    *,
    repo_root: Path,
    event: Mapping[str, Any],
    event_name: str,
    config_path_input: str,
    default_budget_limit_usd: float | None,
    gpu_hourly_prices: Mapping[str, float],
) -> str:
    pull_request = event.get("pull_request") if isinstance(event, Mapping) else None
    if event_name and event_name != "pull_request":
        return render_no_config_report(
            [config_path_input],
            [f"Skipped analysis because this action is intended for pull_request events, not {event_name}."],
        )

    base_sha = get_nested(pull_request, "base", "sha")
    head_sha = get_nested(pull_request, "head", "sha")
    candidate_paths = resolve_candidate_paths(repo_root, config_path_input, base_sha, head_sha)
    if not candidate_paths:
        checked = split_config_paths(config_path_input)
        notes = ["No changed supported config files matched the configured path."]
        return render_no_config_report(checked, notes)

    reports: list[tuple[str, str]] = []
    notes: list[str] = []
    for config_path in candidate_paths:
        suffix = Path(config_path).suffix.lower()
        if suffix not in SUPPORTED_SUFFIXES:
            notes.append(f"Skipped {config_path}: unsupported config extension.")
            continue

        base_text = read_git_file(repo_root, base_sha, config_path)
        head_text = read_git_file(repo_root, head_sha, config_path)
        if head_text is None:
            head_text = read_worktree_file(repo_root, config_path)

        if base_text is None and head_text is None:
            notes.append(f"Skipped {config_path}: file was not found in the base or PR branch.")
            continue

        item = analyze_config_texts(
            display_path=config_path,
            base_text=base_text,
            head_text=head_text,
            file_suffix=suffix,
            default_budget_limit_usd=default_budget_limit_usd,
            gpu_hourly_prices=gpu_hourly_prices,
        )
        if item["report"]:
            reports.append((config_path, item["report"]))
        notes.extend(item["notes"])

    return render_action_report(reports, notes, candidate_paths)


def get_nested(value: Any, *keys: str) -> str | None:
    current = value
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current if isinstance(current, str) and current else None


def resolve_candidate_paths(
    repo_root: Path,
    config_path_input: str,
    base_sha: str | None,
    head_sha: str | None,
) -> list[str]:
    configured = split_config_paths(config_path_input)
    changed_paths = changed_supported_files(repo_root, base_sha, head_sha)

    if not configured:
        return changed_paths

    candidates: list[str] = []
    for pattern in configured:
        expanded_patterns = expand_brace_pattern(pattern)
        pattern_matches: list[str] = []
        for expanded in expanded_patterns:
            if has_glob_chars(expanded):
                pattern_matches.extend(match_known_paths(expanded, changed_paths))
                pattern_matches.extend(glob_worktree(repo_root, expanded))
            else:
                pattern_matches.append(expanded)
        candidates.extend(pattern_matches)

    return unique_preserving_order(normalize_repo_path(path) for path in candidates if path)


def split_config_paths(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def expand_brace_pattern(pattern: str) -> list[str]:
    start = pattern.find("{")
    end = pattern.find("}", start + 1)
    if start == -1 or end == -1:
        return [pattern]
    prefix = pattern[:start]
    suffix = pattern[end + 1 :]
    options = [option.strip() for option in pattern[start + 1 : end].split(",") if option.strip()]
    if not options:
        return [pattern]
    return [prefix + option + suffix for option in options]


def has_glob_chars(pattern: str) -> bool:
    return any(char in pattern for char in "*?[")


def match_known_paths(pattern: str, paths: list[str]) -> list[str]:
    return [path for path in paths if fnmatch.fnmatch(path, pattern)]


def glob_worktree(repo_root: Path, pattern: str) -> list[str]:
    matches: list[str] = []
    for path in repo_root.glob(pattern):
        if path.is_file():
            matches.append(path.relative_to(repo_root).as_posix())
    return matches


def normalize_repo_path(path: str) -> str:
    normalized = Path(path).as_posix()
    if normalized.startswith("./"):
        return normalized[2:]
    return normalized


def unique_preserving_order(values: Any) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def changed_supported_files(repo_root: Path, base_sha: str | None, head_sha: str | None) -> list[str]:
    if not base_sha or not head_sha:
        return []
    completed = run_git(repo_root, ["diff", "--name-only", base_sha, head_sha, "--"])
    if completed.returncode != 0:
        return []
    paths = [
        normalize_repo_path(line)
        for line in completed.stdout.splitlines()
        if Path(line).suffix.lower() in SUPPORTED_SUFFIXES
    ]
    return unique_preserving_order(paths)


def read_git_file(repo_root: Path, sha: str | None, path: str) -> str | None:
    if not sha:
        return None
    completed = run_git(repo_root, ["show", f"{sha}:{path}"])
    if completed.returncode != 0:
        return None
    return completed.stdout


def read_worktree_file(repo_root: Path, path: str) -> str | None:
    worktree_path = repo_root / path
    if not worktree_path.exists() or not worktree_path.is_file():
        return None
    return worktree_path.read_text(encoding="utf-8")


def run_git(repo_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )


def analyze_config_texts(
    *,
    display_path: str,
    base_text: str | None,
    head_text: str | None,
    file_suffix: str,
    default_budget_limit_usd: float | None,
    gpu_hourly_prices: Mapping[str, float],
) -> dict[str, Any]:
    notes: list[str] = []
    try:
        base_config = parse_config_side(base_text, file_suffix, display_path)
        head_config = parse_config_side(head_text, file_suffix, display_path)
    except (ValueError, SyntaxError, json.JSONDecodeError) as exc:
        return {"report": "", "notes": [f"Skipped {display_path}: {exc}"]}

    result = analyze_configs(
        base_config,
        head_config,
        default_budget_limit_usd=default_budget_limit_usd,
        gpu_hourly_prices=gpu_hourly_prices,
    )
    return {"report": result.markdown_report, "notes": notes}


def parse_config_side(text: str | None, file_suffix: str, source_path: str):
    if text is None:
        return normalize_training_config({}, source_path=source_path)
    raw_config = parse_config_text(text, file_suffix)
    return normalize_training_config(raw_config, source_path=source_path)


def render_action_report(
    reports: list[tuple[str, str]],
    notes: list[str],
    checked_paths: list[str],
) -> str:
    if not reports:
        return render_no_config_report(checked_paths, notes)

    if len(reports) == 1:
        config_path, report = reports[0]
        rendered = insert_config_path(report, config_path)
        if notes:
            rendered += "\n### Action notes\n\n" + "\n".join(f"- {note}" for note in notes) + "\n"
        return rendered

    lines = ["## TrainCost CI Report", "", f"Analyzed {len(reports)} config files.", ""]
    for config_path, report in reports:
        lines.extend([f"### `{config_path}`", ""])
        lines.append(strip_report_title(report).strip())
        lines.append("")
    if notes:
        lines.extend(["### Action notes", ""])
        lines.extend(f"- {note}" for note in notes)
        lines.append("")
    return "\n".join(lines)


def insert_config_path(report: str, config_path: str) -> str:
    lines = report.splitlines()
    if not lines:
        return report
    return "\n".join([lines[0], "", f"Config: `{config_path}`.", *lines[1:]]) + "\n"


def strip_report_title(report: str) -> str:
    lines = report.splitlines()
    if lines and lines[0].strip() == "## TrainCost CI Report":
        return "\n".join(lines[1:]).lstrip()
    return report


def render_no_config_report(checked_paths: list[str], notes: list[str]) -> str:
    lines = [
        "## TrainCost CI Report",
        "",
        "No supported training config file found.",
        "",
        "TrainCost CI skipped cost analysis because no readable YAML, JSON, or simple Python config was found.",
    ]
    if checked_paths:
        lines.extend(["", "### Checked", ""])
        lines.extend(f"- `{path}`" for path in checked_paths)
    if notes:
        lines.extend(["", "### Action notes", ""])
        lines.extend(f"- {note}" for note in notes)
    return "\n".join(lines) + "\n"


def post_or_update_pr_comment(event: Mapping[str, Any], report: str) -> bool:
    pull_request = event.get("pull_request") if isinstance(event, Mapping) else None
    comments_url = get_nested(pull_request, "comments_url")
    if not comments_url:
        print("Comment mode requested, but no pull request comment URL was available.")
        return False

    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if not token:
        print("Comment mode requested, but no GitHub token was available.")
        return False

    body = f"{COMMENT_MARKER}\n{report}"
    try:
        existing = find_existing_comment(comments_url, token)
        if existing:
            github_json_request("PATCH", existing["url"], token, {"body": body})
            print("TrainCost CI updated an existing PR comment.")
        else:
            github_json_request("POST", comments_url, token, {"body": body})
            print("TrainCost CI posted a PR comment.")
    except urllib.error.HTTPError as exc:
        print(f"Comment mode requested, but GitHub returned HTTP {exc.code}.")
        return False
    except urllib.error.URLError as exc:
        print(f"Comment mode requested, but GitHub comment request failed: {exc.reason}.")
        return False
    return True


def find_existing_comment(comments_url: str, token: str) -> dict[str, Any] | None:
    separator = "&" if "?" in comments_url else "?"
    comments = github_json_request("GET", f"{comments_url}{separator}per_page=100", token)
    if not isinstance(comments, list):
        return None
    for comment in comments:
        if isinstance(comment, Mapping) and COMMENT_MARKER in str(comment.get("body", "")):
            url = comment.get("url")
            if isinstance(url, str):
                return {"url": url}
    return None


def github_json_request(
    method: str,
    url: str,
    token: str,
    payload: Mapping[str, Any] | None = None,
) -> Any:
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Content-Type", "application/json")
    request.add_header("X-GitHub-Api-Version", "2022-11-28")

    with urllib.request.urlopen(request, timeout=20) as response:
        body = response.read()
    if not body:
        return None
    return json.loads(body.decode("utf-8"))


def write_output(name: str, value: str) -> None:
    output_path = os.getenv("GITHUB_OUTPUT")
    if not output_path:
        return
    with Path(output_path).open("a", encoding="utf-8") as output_file:
        output_file.write(f"{name}={value}\n")


if __name__ == "__main__":
    raise SystemExit(main())
