#!/usr/bin/env python3
"""GitHub and CLI boundaries for deterministic TrainCost reports."""

from __future__ import annotations

import argparse
import fnmatch
import json
import math
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

ACTION_DIR = Path(__file__).resolve().parent
CORE_SRC = ACTION_DIR.parents[1] / "packages" / "core" / "src"
if CORE_SRC.exists():
    sys.path.insert(0, str(CORE_SRC))

from traincost_ci_core import analyze_configs, normalize_training_config, parse_config_text
from traincost_ci_core.models import AnalysisResult
from traincost_ci_core.safety import ConfigError, MAX_CONFIG_BYTES, looks_sensitive, markdown, number, safe_text

SUPPORTED_SUFFIXES = {".yaml", ".yml", ".json", ".py"}
COMMENT_MARKER = "<!-- traincost-ci-report -->"


@dataclass(frozen=True)
class ChangedFile:
    path: str
    base_path: str | None
    deleted: bool = False


@dataclass(frozen=True)
class ConfigReport:
    path: str
    report: str
    result: AnalysisResult


@dataclass(frozen=True)
class AnalysisRun:
    report: str
    status: str


def main(argv=None):
    args = parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    report_path = Path(args.report_path)
    if not report_path.is_absolute():
        report_path = repo_root / report_path
    try:
        if any(c in str(report_path) for c in "\r\n") or looks_sensitive(str(report_path)):
            report_path = repo_root / "report.md"
            raise ConfigError("Invalid report-path; diagnostics were written to report.md.")
        prices = parse_gpu_prices(args.gpu_prices)
        budget = parse_budget_limit(args.budget_limit)
        threshold = parse_warn_increase_percent(args.warn_increase_percent)
        if args.comment_mode.lower() not in {"true", "false"}:
            raise ConfigError("comment-mode must be true or false.")
        if bool(args.base_config) != bool(args.head_config):
            raise ConfigError("Provide both base-config and head-config.")
        if args.base_config:
            outcome = run_local_pair(Path(args.base_config), Path(args.head_config),
                default_budget_limit_usd=budget, gpu_hourly_prices=prices,
                cost_increase_threshold_percent=threshold)
        else:
            outcome = run_pull_request_analysis(repo_root=repo_root, event=load_event(args.event_path),
                event_name=args.event_name, config_path_input=args.config_path,
                default_budget_limit_usd=budget, gpu_hourly_prices=prices,
                cost_increase_threshold_percent=threshold)
    except ConfigError as exc:
        outcome = AnalysisRun(render_no_config_report([], [str(exc)]), "error")
    except (OSError, UnicodeError, ValueError, RecursionError):
        outcome = AnalysisRun(render_no_config_report([], ["Analysis failed: unreadable or invalid input."]), "error")
    comment_posted = False
    try:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(outcome.report, encoding="utf-8")
        if args.comment_mode.lower() == "true" and outcome.status != "error":
            comment_posted = post_or_update_pr_comment(load_event(args.event_path), outcome.report)
        publish_report(outcome, report_path, comment_posted=comment_posted)
    except (OSError, ValueError):
        print("TrainCost CI could not write its report or runner outputs.", file=sys.stderr)
        return 2
    print(f"TrainCost CI analysis-status: {outcome.status}")
    return 2 if outcome.status == "error" else 0


def publish_report(outcome, report_path, *, comment_posted=False):
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(outcome.report, encoding="utf-8")
    write_output("report-path", str(report_path))
    write_output("comment-posted", "true" if comment_posted else "false")
    write_output("analysis-status", outcome.status)
    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with Path(summary).open("a", encoding="utf-8") as stream:
            stream.write(outcome.report)


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Run TrainCost CI cost analysis.")
    for name, default in (("config-path", "config.yaml"), ("gpu-prices", ""), ("budget-limit", ""),
        ("warn-increase-percent", "50"), ("comment-mode", "false"), ("report-path", "report.md")):
        parser.add_argument("--" + name, default=os.getenv("INPUT_" + name.upper().replace("-", "_"), default))
    parser.add_argument("--event-path", default=os.getenv("GITHUB_EVENT_PATH", ""))
    parser.add_argument("--event-name", default=os.getenv("GITHUB_EVENT_NAME", ""))
    parser.add_argument("--repo-root", default=os.getenv("GITHUB_WORKSPACE", os.getcwd()))
    parser.add_argument("--base-config", default="")
    parser.add_argument("--head-config", default="")
    return parser.parse_args(argv)


def parse_gpu_prices(value):
    prices, names = {}, set()
    for part in (value or "").split(","):
        if not part.strip():
            continue
        name, separator, price = part.partition("=")
        name = name.strip()
        normalized = re.sub(r"[^a-z0-9]", "", name.lower())
        if not separator or not normalized:
            raise ConfigError("Invalid gpu-prices: expected NAME=PRICE entries.")
        if normalized in names:
            raise ConfigError("Duplicate GPU price entry.")
        names.add(normalized)
        prices[name] = number(price, "gpu price", allow_zero=True)
    return prices


def parse_budget_limit(value):
    return None if value is None or not value.strip() else number(value, "budget-limit", allow_zero=True)


def parse_warn_increase_percent(value):
    return 50.0 if value is None or not value.strip() else number(value, "warn-increase-percent", allow_zero=True)


def load_event(event_path):
    if not event_path:
        return {}
    try:
        with Path(event_path).open("rb") as stream:
            data = stream.read(10_000_001)
        if len(data) > 10_000_000:
            raise ConfigError("GitHub event payload exceeds size limit.")
        event = json.loads(data)
        if not isinstance(event, dict):
            raise ValueError
        return event
    except (OSError, ValueError):
        raise ConfigError("Cannot read a valid GitHub event payload.") from None


def _decode_config(data):
    if len(data) > MAX_CONFIG_BYTES:
        raise ConfigError("Config exceeds the 1MB byte limit.")
    try:
        return data.decode("utf-8")
    except UnicodeError:
        raise ConfigError("Config must be UTF-8.") from None


def _read_local(path):
    try:
        with path.open("rb") as stream:
            return _decode_config(stream.read(MAX_CONFIG_BYTES + 1))
    except OSError:
        raise ConfigError("Config file is unreadable.") from None


def run_local_pair(base_path, head_path, *, default_budget_limit_usd, gpu_hourly_prices,
                   cost_increase_threshold_percent=50.0):
    try:
        base = normalize_training_config(parse_config_text(_read_local(base_path), base_path.suffix))
        head = normalize_training_config(parse_config_text(_read_local(head_path), head_path.suffix))
        result = analyze_configs(base, head, default_budget_limit_usd=default_budget_limit_usd,
            gpu_hourly_prices=gpu_hourly_prices, cost_increase_threshold_percent=cost_increase_threshold_percent)
        return AnalysisRun(result.markdown_report, "complete")
    except ConfigError as exc:
        return AnalysisRun(render_no_config_report([str(head_path)], [str(exc)]), "error")


def get_nested(value, *keys):
    current = value
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current if isinstance(current, str) and current else None


def run_pull_request_analysis(*, repo_root, event, event_name, config_path_input,
                              default_budget_limit_usd, gpu_hourly_prices,
                              cost_increase_threshold_percent=50.0):
    if event_name != "pull_request":
        return AnalysisRun(render_no_config_report([], ["Skipped: this action requires a pull_request event."]), "skipped")
    pr = event.get("pull_request")
    base_sha, head_sha = get_nested(pr, "base", "sha"), get_nested(pr, "head", "sha")
    try:
        changes = changed_supported_files(repo_root, base_sha, head_sha)
        selected = resolve_candidate_paths(config_path_input, changes)
    except ConfigError as exc:
        return AnalysisRun(render_no_config_report([], [str(exc)]), "error")
    reports, notes = [], []
    failed = deleted = 0
    for change in selected:
        if change.deleted:
            deleted += 1
            notes.append(f"Deleted config excluded: {safe_text(change.path)}.")
            continue
        try:
            base_text = read_git_file(repo_root, base_sha, change.base_path) if change.base_path else None
            head_text = read_git_file(repo_root, head_sha, change.path)
            base = normalize_training_config({}) if base_text is None else normalize_training_config(
                parse_config_text(base_text, Path(change.base_path).suffix))
            head = normalize_training_config(parse_config_text(head_text, Path(change.path).suffix))
            result = analyze_configs(base, head, default_budget_limit_usd=default_budget_limit_usd,
                gpu_hourly_prices=gpu_hourly_prices, cost_increase_threshold_percent=cost_increase_threshold_percent)
            if change.base_path is None:
                notes.append(f"Added config: {safe_text(change.path)}; no base file exists, so base defaults are illustrative.")
            elif change.base_path != change.path:
                notes.append(f"Detected rename: {safe_text(change.base_path)} -> {safe_text(change.path)}.")
            reports.append(ConfigReport(change.path, result.markdown_report, result))
        except ConfigError as exc:
            failed += 1
            notes.append(f"Skipped {safe_text(change.path)}: {exc}")
    status = ("partial" if reports else "error") if failed else ("complete" if reports else "skipped")
    if not selected:
        notes.append("No changed supported config files matched the configured path.")
    try:
        report = render_action_report(reports, notes, [c.path for c in selected], excluded=failed + deleted)
    except ConfigError as exc:
        return AnalysisRun(render_no_config_report([], [str(exc)]), "error")
    return AnalysisRun(report, status)


def split_config_paths(value):
    parts, current, depth = [], [], 0
    for char in value:
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        if depth not in (0, 1):
            raise ConfigError("Invalid config-path brace pattern.")
        if char == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    if depth:
        raise ConfigError("Invalid config-path brace pattern.")
    parts.append("".join(current).strip())
    return [p for p in parts if p]


def expand_brace_pattern(pattern):
    if "{" not in pattern:
        return [pattern]
    start, end = pattern.index("{"), pattern.index("}")
    options = pattern[start + 1:end].split(",")
    if any(not option for option in options):
        raise ConfigError("Empty config-path brace option.")
    return [expanded for option in options for expanded in
            expand_brace_pattern(pattern[:start] + option + pattern[end + 1:])]


def resolve_candidate_paths(config_path_input, changes):
    patterns = [expanded.removeprefix("./") for p in split_config_paths(config_path_input)
                for expanded in expand_brace_pattern(p)]
    for pattern in patterns:
        if Path(pattern).is_absolute() or ".." in Path(pattern).parts:
            raise ConfigError("config-path must stay inside the repository.")
    def matches(pattern, path):
        return fnmatch.fnmatchcase(path, pattern) or (pattern.startswith("**/") and fnmatch.fnmatchcase(path, pattern[3:]))
    return [c for c in changes if not patterns or any(matches(p, c.path) for p in patterns)]


def run_git(repo_root, args):
    try:
        return subprocess.run(["git", *args], cwd=repo_root, capture_output=True, check=False, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        raise ConfigError("Git operation unavailable or timed out.") from None


def _valid_commit(repo_root, sha):
    if not sha or not re.fullmatch(r"[0-9a-fA-F]{40,64}", sha):
        raise ConfigError("Missing or invalid base/head SHA.")
    result = run_git(repo_root, ["cat-file", "-t", sha])
    if result.returncode or result.stdout.strip() != b"commit":
        raise ConfigError("Base/head commit unavailable; use checkout with fetch-depth: 0.")


def changed_supported_files(repo_root, base_sha, head_sha):
    _valid_commit(repo_root, base_sha)
    _valid_commit(repo_root, head_sha)
    result = run_git(repo_root, ["diff", "--name-status", "-z", "--find-renames", base_sha, head_sha, "--"])
    if result.returncode:
        raise ConfigError("Git diff failed; use checkout with fetch-depth: 0.")
    parts = result.stdout.split(b"\0")
    changes, i = [], 0
    try:
        while i < len(parts) and parts[i]:
            status = parts[i].decode("ascii")
            old_path = parts[i + 1].decode("utf-8")
            i += 2
            path = old_path
            if status.startswith("R"):
                path = parts[i].decode("utf-8")
                i += 1
            if Path(path).suffix.lower() not in SUPPORTED_SUFFIXES:
                continue
            changes.append(ChangedFile(path, None if status.startswith("A") else old_path, status.startswith("D")))
    except (UnicodeError, IndexError):
        raise ConfigError("Git returned an unsupported file path or diff record.") from None
    return changes


def read_git_file(repo_root, sha, path):
    spec = f"{sha}:{path}"
    size = run_git(repo_root, ["cat-file", "-s", spec])
    if size.returncode:
        raise ConfigError("Config could not be read from the requested commit.")
    try:
        if int(size.stdout) > MAX_CONFIG_BYTES:
            raise ConfigError("Config exceeds the 1MB byte limit.")
    except ValueError:
        raise ConfigError("Config is unavailable or exceeds the 1MB byte limit.") from None
    content = run_git(repo_root, ["cat-file", "blob", spec])
    if content.returncode:
        raise ConfigError("Config is not a readable Git blob.")
    return _decode_config(content.stdout)


def analyze_config_texts(*, display_path, base_text, head_text, file_suffix,
                         default_budget_limit_usd, gpu_hourly_prices, cost_increase_threshold_percent=50.0):
    try:
        base = normalize_training_config(parse_config_text(base_text, file_suffix) if base_text is not None else {})
        head = normalize_training_config(parse_config_text(head_text, file_suffix) if head_text is not None else {})
        result = analyze_configs(base, head, default_budget_limit_usd=default_budget_limit_usd,
            gpu_hourly_prices=gpu_hourly_prices, cost_increase_threshold_percent=cost_increase_threshold_percent)
        return {"report": result.markdown_report, "result": result, "notes": []}
    except ConfigError as exc:
        return {"report": "", "result": None, "notes": [f"Skipped {safe_text(display_path)}: {exc}"]}


def render_action_report(reports, notes, checked_paths, *, excluded=0):
    if not reports:
        return render_no_config_report(checked_paths, notes)
    if len(reports) == 1:
        report = insert_config_path(reports[0].report, reports[0].path)
    else:
        lines = ["## TrainCost CI Report", "", f"Analyzed {len(reports)} config files.", ""]
        lines.extend(render_combined_totals(reports))
        for item in reports:
            lines.extend([f"### {markdown(item.path)}", "", "\n".join(item.report.splitlines()[1:]).strip(), ""])
        report = "\n".join(lines) + "\n"
    if excluded:
        notes = [*notes, f"Excluded configs: {excluded}. Costs cover analyzed configs only."]
    if notes:
        report += "\n### Action notes\n\n" + "\n".join("- " + markdown(n) for n in notes) + "\n"
    return report


def render_combined_totals(reports):
    base = sum(r.result.base_estimate.estimated_cost_usd for r in reports)
    head = sum(r.result.pr_estimate.estimated_cost_usd for r in reports)
    if not math.isfinite(base) or not math.isfinite(head):
        raise ConfigError("Combined estimate arithmetic overflow.")
    return ["### Combined estimated cost", "", "- Sum of analyzed configs only; this is not a scheduled workload forecast.",
            f"- Base branch total: {chr(36)}{base:,.2f}", f"- This PR total: {chr(36)}{head:,.2f}", ""]


def insert_config_path(report, path):
    display = safe_text(path).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace(chr(96), "&#96;")
    lines = report.splitlines()
    return "\n".join([lines[0], "", f"Config: {chr(96)}{display}{chr(96)}.", *lines[1:]]) + "\n"


def render_no_config_report(checked_paths, notes):
    lines = ["## TrainCost CI Report", "", "No supported training config file found or analyzed.",
             "", "No cost estimate was produced."]
    if checked_paths:
        lines.extend(["", "### Checked", ""])
        lines.extend("- " + markdown(p) for p in checked_paths)
    if notes:
        lines.extend(["", "### Action notes", ""])
        lines.extend("- " + markdown(note) for note in notes)
    return "\n".join(lines) + "\n"


def post_or_update_pr_comment(event, report):
    comments_url = get_nested(event.get("pull_request"), "comments_url")
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if not comments_url or not token:
        print("Experimental comment mode unavailable: missing PR URL or token.")
        return False
    try:
        existing = find_existing_comment(comments_url, token)
        github_json_request("PATCH" if existing else "POST", existing["url"] if existing else comments_url,
                            token, {"body": COMMENT_MARKER + "\n" + report})
        return True
    except (urllib.error.URLError, ValueError, OSError):
        print("Experimental comment request failed; the local report remains available.")
        return False


def find_existing_comment(comments_url, token):
    comments = github_json_request("GET", comments_url + "?per_page=100", token)
    if isinstance(comments, list):
        for comment in comments:
            if isinstance(comment, dict) and comment.get("user", {}).get("type") == "Bot" and COMMENT_MARKER in str(comment.get("body", "")):
                if isinstance(comment.get("url"), str):
                    return {"url": comment["url"]}
    return None


def github_json_request(method, url, token, payload=None):
    api_url = os.getenv("GITHUB_API_URL", "https://api.github.com").rstrip("/")
    if not url.startswith(api_url + "/"):
        raise ValueError("Untrusted GitHub API URL.")
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=data, method=method,
        headers={"Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}",
                 "Content-Type": "application/json", "X-GitHub-Api-Version": "2022-11-28"})
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    with urllib.request.build_opener(NoRedirect).open(request, timeout=20) as response:
        body = response.read()
    return json.loads(body) if body else None


def write_output(name, value):
    if "\n" in value or "\r" in value:
        raise ValueError("Runner output must be a single line.")
    path = os.getenv("GITHUB_OUTPUT")
    if path:
        with Path(path).open("a", encoding="utf-8") as stream:
            stream.write(f"{name}={value}\n")


if __name__ == "__main__":
    raise SystemExit(main())
