"""Check archived branch and fork run identities and reports, without network access."""
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


def verify(*, fork=False):
    directory = ROOT / "fork" if fork else ROOT
    run_id = 42405161652 if fork else 42403549313
    pr_number = 2 if fork else 1
    head_repository = "anyhogs/TrainCost-consumer-validation" if fork else CONSUMER
    head_id = 1449662675 if fork else 1449646378

    def read(path):
        return json.loads((directory / path).read_text())

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
    assert run["id"] == run_id and run["event"] == "pull_request"
    assert run["status"] == "completed" and run["conclusion"] == "success"
    assert run["head_sha"] == pr["head"]["sha"] == evidence["head_sha"] == HEAD
    assert pr["base"]["sha"] == evidence["base_sha"] == BASE
    assert pr["number"] == evidence["pr_number"] == pr_number
    assert run["repository"]["full_name"] == evidence["consumer_repository"] == CONSUMER
    assert pr["base"]["repository"] == evidence["pr_base_repository"] == CONSUMER
    assert pr["head"]["repository"] == evidence["pr_head_repository"] == head_repository
    assert pr["base"]["id"] == run["repository"]["id"] == 1449646378
    assert pr["head"]["id"] == head_id
    assert (pr["head"]["id"] != pr["base"]["id"]) is fork
    assert evidence["source_repository"] == "Pig30nidaE/TrainCost" != CONSUMER
    assert evidence["candidate_sha"] == CANDIDATE
    assert evidence["event"] == "pull_request" and evidence["passed"] is True
    assert pr["head"]["fork"] is fork and evidence["head_is_fork"] is fork
    assert evidence["distinct_head_repository"] is fork
    assert pr["merged"] is False and pr["draft"] is (not fork)
    if fork:
        assert run["run_attempt"] == 2
        assert run["head_repository"] == {"full_name": head_repository, "id": head_id, "fork": True}
        permissions = read("permissions.json")
        assert permissions["run_id"] == run_id and permissions["run_attempt"] == 2
        assert permissions["job_id"] == 128501877714
        assert permissions["permissions"] == {"Contents": "read", "Metadata": "read"}
        assert read("workflow.json")["sha"] == hashlib.sha1(blob).hexdigest()
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
            assert (directory / f"reports/{name}.{suffix}").stat().st_size > 0
    modified = read("reports/modified.json")
    assert math.isclose(modified["analyses"][0]["increase_percent"], 200, rel_tol=1e-12)
    assert "Budget limit exceeded" in (directory / "reports/modified.md").read_text()
    added = read("reports/added.json")
    assert added["analyses"][0]["pr"]["adapter"] == "huggingface"
    assert added["analyses"][0]["confidence"]["level"] == "Low"
    assert any("no base file exists" in item for item in added["diagnostics"])
    assert not read("reports/invalid.json")["analyses"]


if __name__ == "__main__":
    verify()
    verify(fork=True)
    print("Archived branch and real fork identities/reports: PASS. Not a fresh hosted run.")
