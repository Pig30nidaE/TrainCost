# Review-driven upgrade validation, historical

The [release-readiness record](release_readiness.md) supersedes this snapshot.
The work below is now committed with additional fixes in candidate
`20af5724ed292066d79c8e47557baf5dd3e14a43`; its new hosted evidence is recorded there.
The following text preserves the scope and state at the time of the earlier checks.

Recorded: 2026-11-07. Local regression result: PASS. Release decision: HOLD.

This record covers the uncommitted worktree on `codex/hf-distilbert-validation`,
based on `fa687ad297b8a9b488255bc4e304297494f76fa9`. That commit alone does not
contain these fixes. No commit, remote push, tag, release, merge, visibility change,
or Action access-policy change was performed for this upgrade.

Existing Mac validation changes and both training evidence bundles were preserved.
No new model download or training run was needed for this review-driven work.

## Implemented priorities

| Priority | Implementation and acceptance |
| --- | --- |
| P1: unsupported training changes looked safe | Known unmodeled training fields emit `unsupported_training_settings`; their values are not copied into diagnostics. Regression cases no longer say that no major cost risk was detected. |
| P1: reused epoch time remained trusted | Model, data, hardware, precision, batch, and other recognized runtime-condition changes with unchanged minutes emit `stale_runtime_assumption`. Epoch-only and equivalent normalized aliases do not spuriously invalidate epoch time. |
| Small monetary amounts | Nonzero subcent costs remain visible; unequal costs and budgets that round to the same cents use distinguishable precision. JSON keeps unrounded numeric values. |
| Bounded HF adapter | Explicit `huggingface` adapter translates epoch, microbatch, accumulation, world size, and precision inputs. Positive `max_steps`, unsupported distributed engines, automatic batch finding, ambiguous containers, and conflicting aliases are rejected. No Python or training code is executed. |
| Local CLI and JSON | The wheel installs `traincost-ci`; CLI and Action share JSON schema version `1.0`. Action adds `config-adapter`, `report-json-path` input/output without removing existing interfaces. |
| Consumer installation | An unrelated temporary Git repository exercises normal and fork-style payloads through direct and isolated-bootstrap paths. A separate hosted-consumer workflow template is ready but has not run on GitHub. |
| Upstream-derived evaluation | 50 labeled minimized cases derive from SHA-pinned Transformers, PEFT, and TRL examples, with license links and explicit mutations. All pass; these are constructed boundary tests, not a production accuracy benchmark. |
| Open-source contribution path | Added CONTRIBUTING, SECURITY, bug/feature issue templates, and a PR template. No unverified contact address, response guarantee, or support promise was invented. |

The cost formula has not changed. Warnings identify unsupported assumptions; they do
not invent new runtimes. Changing the numeric minutes value is not proof that it was
remeasured. Confidence describes input completeness, not cloud-bill or runtime accuracy.
The adapter supports documented fields, not every Transformers/PEFT/TRL configuration.

## Reproduced outcomes

With a $1/hour illustrative price, a one-epoch, six-minute baseline costs $0.10.
Increasing dataset size tenfold or halving batch size without changing the supplied
minutes still computes $0.10, but now explicitly warns that the runtime assumption
is stale. A canonical config containing changed HF epoch/stopping fields warns that
those settings are not modeled. An explicit HF adapter rejects positive `max_steps`
instead of calculating an epoch-based result that ignores its stopping precedence.

The subcent case reports base $0.001, PR $0.003, and a budget of $0.002. The budget
warning therefore remains readable. Another regression distinguishes $1.234 from
$1.233 instead of displaying a misleading $1.23-versus-$1.23 comparison.

QAReview's independent acceptance tests also found and covered root/nested HF
setting bypasses, equivalent and case-colliding aliases, input/output path collisions
(including symlinks and hardlinks), invalid CLI arguments, and aggregate overflow.
Outputs cannot overwrite selected input configs; syntax errors do not write fallback
artifacts into an arbitrary current-directory input. Synthetic secrets stay out of
reports and diagnostics in the covered scenarios.

## Local evidence

All four interpreter runs used the same 75-file code/configuration fingerprint:

`a90117ea44833de005025b3bb1785c579fef1cfbc61d5bb68a3062738f68a0ae`

The fingerprint includes tracked and untracked code/configuration files. It excludes
Markdown, images, and the evidence directory; it is not a hash of the entire repository.
Each run confirmed that this fingerprint stayed unchanged during its checks.

| Python | Core | Action | HF demo | Corpus evaluator | Labeled cases | Record |
| --- | --- | --- | --- | --- | --- | --- |
| 3.11.14 | 89 pass | 48 pass | 46 pass, 1 skip | 6 pass | 50/50 | [JSON](evidence/upgrade-2026-11-07/python311.json) |
| 3.12.8 | 89 pass | 48 pass | 46 pass, 1 skip | 6 pass | 50/50 | [JSON](evidence/upgrade-2026-11-07/python312.json) |
| 3.13.12 | 89 pass | 48 pass | 46 pass, 1 skip | 6 pass | 50/50 | [JSON](evidence/upgrade-2026-11-07/python313.json) |
| 3.14.0 | 89 pass | 48 pass | 46 pass, 1 skip | 6 pass | 50/50 | [JSON](evidence/upgrade-2026-11-07/python314.json) |

Environment: macOS Darwin 25.6.0, arm64, PyYAML 6.0.3. This is 190 unittest methods
per interpreter: 189 pass and one Linux-specific process-cleanup test is skipped on
macOS. Repeating the suite across versions does not create additional distinct tests.
The matrix also checks the three existing report fixtures, HF static arithmetic,
normal/fork local consumers, and the explicit missing-PyYAML error path.

Additional final-worktree checks on Python 3.12.8:

- Built the wheel, installed it into a fresh environment outside the checkout,
  imported the package, and ran its installed console command with the HF adapter.
  JSON reported `complete` and $0.001/$0.003; Markdown retained the subcent value.
- `scripts/verify_external_consumer.py` passed normal-direct, normal-bootstrap,
  fork-direct, and fork-bootstrap. Each verified `complete`, `comment-posted=false`,
  report paths, JSON costs, Summary equality, and no synthetic-token disclosure.
- All three report fixtures remained byte-identical: 4101, 2583, and 247 bytes.
- Final known-pattern secret scan covered 260 reachable Git blobs and 142 worktree
  entries with zero findings. This is not proof that arbitrary credentials or
  confidential content are absent; confidentiality review remains a separate gate.
- Coverage.py 7.17.1, branches enabled, tests excluded: 85% combined coverage.
  CLI subprocesses are exercised by integration tests but are not traced by this
  coverage command, so CLI modules show 0% in that measurement. No coverage-only
  approval is inferred.

Final local wheel SHA-256:
`ecf8cc2ee9146a7b529821fb78680a35c797d5e9e4cb936b342adbb2f4a551f7`.
This identifies the tested local build, not a published distribution.

## Reproduce

Install `requirements-dev.txt` in a separate environment, then run from the repository root:

```bash
python scripts/verify_upgrade.py --output /tmp/traincost-upgrade-evidence.json
python scripts/verify_external_consumer.py
python -m build packages/core --no-isolation --outdir /tmp/traincost-upgrade-dist
python scripts/verify_wheel.py /tmp/traincost-upgrade-dist
python scripts/audit_secrets.py
```

Use an empty distribution directory for each build. The first command is offline
after dependencies are installed; the isolated bootstrap and wheel-install checks
may download pinned PyYAML. Matrix reruns can use `--python /path/to/python`.
The verifier saves structured outcomes, not arbitrary stdout or environment dumps.

## Unpassed gates and next owners

1. **GithubAction:** run the committed candidate by full SHA from an independent
   GitHub-hosted consumer, including an actual fork PR. The current source repository
   is private and its API reports Action access level `none`. No access settings were
   changed and no hosted run is claimed. The template deliberately retains a
   `REVIEWED_UPGRADE_COMMIT_SHA` placeholder until there is a reviewed candidate.
2. **QAReview:** inspect new Linux/Python 3.11-3.14 CI, including the Linux-only cleanup
   test, plus real consumer outputs and rendered Summary. Historical runs for earlier
   commits are not evidence for this worktree.
3. **PM:** review those records and confidentiality before any new release decision.
   Publication, tag push, and public visibility continue to require separate approval.

Live comment creation/update remains experimental and unverified. RTX 3060 repeated
calibration remains deferred. The earlier Mac smoke proves limited compatibility,
not predictive accuracy; its 42.965% and 7.496% extrapolation errors remain recorded.
The private-repository permission gate cannot be replaced by local fork simulations.
