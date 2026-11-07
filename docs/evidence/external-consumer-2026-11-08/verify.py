"""Check this archived external run's identity and reports, without network access."""
import hashlib
import json
import math
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
CANDIDATE = "28b4c541ab98a840a814f6bed8d3b205ece3d4ca"
CONSUMER = "Pig30nidaE/TrainCost-consumer-validation"
BASE = "bb0b5b974e7e702a9232ea3434dfb62da30b3c70"
HEAD = "01e73957f09b473cc0d133e7bc67c333530030f0"


def read(path):
    return json.loads((ROOT / path).read_text())


def verify():
    workflow_bytes = (ROOT / "workflow.yml").read_bytes()
    blob = f"blob {len(workflow_bytes)}\0".encode() + workflow_bytes
    # Git blob at the reviewed consumer head, not an artifact's self-reported pin.
    assert hashlib.sha1(blob).hexdigest() == "35475fa0a4f5d2dfcef5f1817de9c89259b39bb9"
    workflow = yaml.safe_load(workflow_bytes)
    assert workflow["permissions"] == {"contents": "read"}
    calls = {step["id"]: step["uses"] for step in workflow["jobs"]["consumer"]["steps"]
             if step.get("uses", "").startswith("Pig30nidaE/TrainCost")}
    assert calls == {
        name: f"Pig30nidaE/TrainCost{path}@{CANDIDATE}"
        for name, path in (("modified", ""), ("added", "/packages/github-action"),
                           ("partial", ""), ("invalid", ""), ("unsafe", ""))}
    run, pr, evidence = read("run.json"), read("pr.json"), read("reports/verification.json")
    assert run["id"] == 42403549313 and run["event"] == "pull_request"
    assert run["status"] == "completed" and run["conclusion"] == "success"
    assert run["head_sha"] == pr["head"]["sha"] == evidence["head_sha"] == HEAD
    assert pr["base"]["sha"] == evidence["base_sha"] == BASE
    assert pr["number"] == evidence["pr_number"] == 1
    assert run["repository"]["full_name"] == evidence["consumer_repository"] == CONSUMER
    assert pr["base"]["repository"] == evidence["pr_base_repository"] == CONSUMER
    assert pr["head"]["repository"] == evidence["pr_head_repository"] == CONSUMER
    assert pr["base"]["id"] == pr["head"]["id"] == run["repository"]["id"] == 1449646378
    assert evidence["source_repository"] == "Pig30nidaE/TrainCost" != CONSUMER
    assert evidence["candidate_sha"] == CANDIDATE
    assert evidence["event"] == "pull_request" and evidence["passed"] is True
    assert pr["head"]["fork"] is False and evidence["head_is_fork"] is False
    assert evidence["distinct_head_repository"] is False
    assert pr["merged"] is False and pr["draft"] is True
    assert evidence["unsafe_output_preserved"] is True
    assert evidence["step_summary_matches_reports"] is True
    assert evidence["platform"] == "Linux" and evidence["python"] == "3.12.16"
    expected = {"modified": ("complete", 1, 0, .1, .3), "added": ("complete", 1, 0, .5, .3),
                "partial": ("partial", 1, 1, .5, .3), "invalid": ("error", 0, 1, None, None)}
    assert set(evidence["outputs"]) == set(expected)
    for name, (status, analyzed, excluded, base, head) in expected.items():
        output = evidence["outputs"][name]
        report = read(f"reports/{name}.json")
        assert output["analysis_status"] == report["analysis_status"] == status
        assert output["comment_posted"] == "false"
        assert report["schema_version"] == "1.0"
        assert report["summary"] == output["summary"] == {
            "analyzed_count": analyzed, "excluded_count": excluded,
            "base_cost_usd": base, "pr_cost_usd": head, "scope": "analyzed_configs_only"}
        for field, suffix in (("report_path", "md"), ("report_json_path", "json")):
            assert output[field] == f"/home/runner/work/_temp/traincost-release-evidence/{name}.{suffix}"
            assert (ROOT / f"reports/{name}.{suffix}").stat().st_size > 0
    modified = read("reports/modified.json")
    assert math.isclose(modified["analyses"][0]["increase_percent"], 200, rel_tol=1e-12)
    assert "Budget limit exceeded" in (ROOT / "reports/modified.md").read_text()
    added = read("reports/added.json")
    assert added["analyses"][0]["pr"]["adapter"] == "huggingface"
    assert added["analyses"][0]["confidence"]["level"] == "Low"
    assert any("no base file exists" in item for item in added["diagnostics"])
    assert not read("reports/invalid.json")["analyses"]


if __name__ == "__main__":
    verify()
    print("Archived identity and reports: PASS. Not a fresh hosted run or a real fork test.")
