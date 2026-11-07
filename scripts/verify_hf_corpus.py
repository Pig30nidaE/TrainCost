#!/usr/bin/env python3
"""Evaluate labeled, minimized HF config scenarios without network or HF packages."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "examples/hf-config-corpus/corpus.json"
sys.path.insert(0, str(ROOT / "packages/core/src"))

from traincost_ci_core import analyze_config_dicts, normalize_training_config
from traincost_ci_core.serialization import analysis_to_dict


def load_corpus():
    with CORPUS.open(encoding="utf-8") as stream:
        corpus = json.load(stream)
    if corpus.get("schema_version") != 1:
        raise ValueError("unsupported corpus schema")
    sources, cases = corpus["sources"], corpus["cases"]
    if len(sources) < 3 or not 30 <= len(cases) <= 50:
        raise ValueError("corpus requires three sources and 30 to 50 cases")
    if len({source["repository"] for source in sources.values()}) < 3:
        raise ValueError("source repositories must be distinct")
    for source in sources.values():
        repo, revision = source["repository"], source["revision"]
        if (not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo) or
                not re.fullmatch(r"[0-9a-f]{40}", revision) or source["license"] != "Apache-2.0" or
                source["source_url"] != f"https://github.com/{repo}/blob/{revision}/{source['path']}" or
                source["license_url"] != f"https://github.com/{repo}/blob/{revision}/LICENSE"):
            raise ValueError("invalid source provenance")
    ids = [case["id"] for case in cases]
    if len(ids) != len(set(ids)) or not all(re.fullmatch(r"[a-z0-9-]+", item) for item in ids):
        raise ValueError("invalid or duplicate case ID")
    if any(case["source"] not in sources or case["label"] not in {"accept", "reject", "stale", "redact", "unsupported"}
           for case in cases):
        raise ValueError("invalid source or label")
    if len({case["source"] for case in cases}) < 3:
        raise ValueError("cases must cover at least three sources")
    return corpus


def pair_for(case, source):
    base = deepcopy(source["template"])
    base.update(case.get("base_top", {}))
    base["training_args"].update(case.get("base_set", {}))
    head = deepcopy(base)
    head["training_args"].update(case.get("set", {}))
    head.update(case.get("top", {}))
    for key in case.get("remove_top", []):
        head.pop(key)
    if "replace" in case:
        head = deepcopy(case["replace"])
    if case.get("shape") == "flat":
        for item in (base, head):
            args = item.pop("training_args")
            if set(item) & set(args):
                raise ValueError("ambiguous flat fixture")
            item.update(args)
    secret = None
    if case.get("synthetic_secret"):
        secret = "hf_" + "A" * 36
        target = case.get("secret_target", "api_key")
        if target == "api_key":
            head["api_key"] = secret
        elif target == "model_name":
            head["model_name"] = secret
        elif target in {"dataset_name", "max_steps"}:
            head["training_args"][target] = secret
        else:
            raise ValueError("invalid synthetic secret target")
    return base, head, secret


def evaluate(case, source):
    base, head, secret = pair_for(case, source)
    try:
        normalized = normalize_training_config(head, adapter="huggingface")
        result = analyze_config_dicts(base, head, adapter="huggingface")
    except ValueError as exc:
        message = str(exc)
        if secret and secret in message:
            return "sensitive value appeared in error"
        if case["label"] != "reject":
            return "unexpected config rejection"
        if not all(word.lower() in message.lower() for word in case.get("error_contains", [])):
            return "rejection did not explain the required constraint"
        return None
    if case["label"] == "reject":
        return "expected rejection, but analysis succeeded"
    for key, value in case.get("fields", {}).items():
        if getattr(normalized, key, None) != value or getattr(result.pr_config, key, None) != value:
            return "normalized field mismatch"
    if case.get("confidence") and result.confidence.level != case["confidence"]:
        return "confidence mismatch"
    if case.get("no_stale") and any("stale" in warning.code.lower() for warning in result.warnings):
        return "unexpected stale-runtime warning"
    if case["label"] == "stale":
        if not any("stale" in warning.code.lower() for warning in result.warnings):
            return "missing stale-runtime warning"
        if "No major cost risk detected." in result.markdown_report:
            return "stale report has a clean headline"
    if case["label"] == "unsupported":
        warnings = [warning for warning in result.warnings if warning.code == "unsupported_training_settings"]
        if not warnings or case["notice"] not in warnings[0].what_changed:
            return "missing unsupported-setting warning"
    if case["label"] == "redact":
        if (secret in repr(normalized) or secret in repr(result) or secret in result.markdown_report
                or secret in json.dumps(analysis_to_dict(result))):
            return "sensitive value appeared in output"
        if not any(warning.code == "sensitive_config_value" for warning in result.warnings):
            return "missing sensitive-config warning"
    return None


def main():
    try:
        corpus = load_corpus()
    except (ValueError, KeyError, OSError, TypeError):
        print("FAIL: invalid corpus or provenance", file=sys.stderr)
        return 1
    counts, failures = Counter(), []
    for case in corpus["cases"]:
        counts[case["label"]] += 1
        try:
            problem = evaluate(case, corpus["sources"][case["source"]])
        except Exception:
            # Do not print exception text: it may contain untrusted config values.
            problem = "unexpected evaluator or adapter error"
        if problem:
            failures.append((case["id"], problem))
    for case_id, problem in failures:
        print(f"FAIL {case_id}: {problem}", file=sys.stderr)
    print(f"HF corpus: {len(corpus['cases']) - len(failures)}/{len(corpus['cases'])} labeled cases passed")
    print("Labels: " + ", ".join(f"{key}={counts[key]}" for key in sorted(counts)))
    print("Derived examples and synthetic mutations only; not adoption or prediction-accuracy metrics.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
