# Portfolio walkthrough

TrainCost CI reviews ML training configuration changes before a pull request is
merged. Its contribution is an inspectable review of untrusted inputs and explicit
cost assumptions, with real-model checks of the configuration-to-training contract.
It is not a learned runtime predictor or a claim of guaranteed savings.

## A five-minute walkthrough

1. Show the [risky config report](../examples/pytorch-demo/expected-report.md):
   epochs 5 to 50, T4 to A100, and one GPU to two. Explain the supplied time and rate.
2. Show the [missing-input](../examples/pytorch-demo/expected-missing-report.md)
   and [invalid-input](../examples/pytorch-demo/expected-invalid-report.md) reports.
   A missing value is an assumption; an invalid value is not a trustworthy estimate.
3. Open the [real-model study](hf_model_matrix.md). DistilBERT, BERT, and ALBERT
   completed 27 MPS fine-tuning runs. Compare actual Trainer arguments, normalized
   fields, the independent Decimal calculation, and the generated reports.
4. Show the timing failures, not just successful training. All model/report checks
   passed, but DistilBERT and BERT failed the predefined repeatability test. Explain
   why input confidence does not establish billing or runtime accuracy.
5. Run the evidence replay below, then open a Git/output-safety regression test.
   Finish with the exact candidate's CI record and remaining distribution gates.

```bash
python scripts/verify_hf_evidence.py
python scripts/verify_hf_corpus.py
```

The first command performs no training or downloads. It rechecks recorded files,
all 27 executions, common dataset identity, reports, and the declared failed timing
outcome. It does not turn historical evidence into a fresh GPU run.

## Data flow and trust boundaries

```text
PR base/head Git objects
  -> changed-file selection
  -> bounded YAML / JSON / Python-literal parsing
  -> canonical or explicit HF normalization
  -> validated inputs + field provenance
  -> deterministic cost formula + risk rules
  -> Markdown / versioned JSON / GitHub Step Summary
```

The Action never executes training Python. Optional local measurement is a separate
process tree, with pinned public model revisions, no implicit Hub token, no remote
model code, and no weights or review text in shared evidence. Reports remain local
unless experimental comment mode is explicitly enabled.

## Engineering decisions to discuss

- Keep core analysis independent of GitHub to make it testable and installable.
- Parse configuration without executing PR code.
- Validate at input boundaries and report exact field paths.
- Treat missing values, invalid values, and Git failures as different states.
- Remove sensitive data before diffing rather than relying on masking after rendering.
- Make installation reproducible and isolate dependencies from the consumer repository.
- Preserve tests that reproduce specific mistakes instead of measuring progress by test count.

## Defects that shaped the design

| Failure found | Change | Inspectable proof |
| --- | --- | --- |
| Sensitive values could reach diff/error text | Redact before normalization; value-free parser errors | Core boundary and Action acceptance tests |
| Missing and invalid numeric input were conflated | Distinguish assumptions from invalid values; reject non-finite/overflow results | Core numerical boundary tests |
| Filesystem output links could overwrite inputs | Shared no-follow output boundary and protected paths | Action output-safety tests and real temporary Git repositories |
| Effective batch size hid a tiny HF microbatch | Use the actual per-device batch for utilization warnings | `test_microbatch_regression.py` |
| A two-decimal assertion rejected a valid short calibration | Compare independent Decimal values and complete display rows | `test_subcent_calibration.py` |
| A green-looking study could omit failures or models | Register bundle identity and coverage; preserve separate outcomes | `test_registered_evidence.py` |

These are reproducible engineering results, not claims that the tool is free from
all defects. Each contract is narrower than supporting every framework setting.

## Evidence and honest limits

See [QA evidence](qa_report.md) for tests, environments, and run links. The
[model study](hf_model_matrix.md) records the actual three-model experiment and its
limits. Its measured source was an uncommitted worktree; a complete source snapshot
was not preserved. The evidence index states that limitation explicitly. A new
release candidate needs commit-bound execution evidence, not a rewritten history.

There are no verified external adopters, measured cost savings, or production
prediction-accuracy claims. The current matrix uses only small IMDb subsets for
sequence classification on MPS. CUDA, LoRA, generation, and distributed engines
remain unverified. The source is private and Action access is `none`; an external
installation is not proven by copying the Action into the same repository.

The project includes an MIT license, an installed CLI, documented JSON, contribution
instructions, and reproducible tests. Those enable review and reuse; they do not
prove community adoption. Publication is still a separate gate.

## Where this can contribute

TrainCost concentrates on PR-time training-config review. Infracost documents
explicit usage inputs for estimating usage-based resources; TrainCost applies a
similar explicit-assumption approach to training time and GPU rates.
[Infracost usage documentation](https://www.infracost.io/docs/features/usage_based_resources/).

CodeCarbon tracks emissions from running code on local hardware. TrainCost's
config review happens before that execution and does not replace power or carbon
measurement. These are different stages of the workflow, not a superiority claim.
[CodeCarbon documentation](https://docs.codecarbon.io/latest/).

Useful first contributions are minimized unsupported-config cases, regression tests
for ambiguous semantics, or another reviewed sequence-classification profile with
preserved measurement evidence. Follow the [contribution guide](../CONTRIBUTING.md).
Avoid claiming a new task is supported merely because its model name is accepted.

## Research references

- [Infracost usage costs](https://www.infracost.io/docs/features/usage_based_resources/): usage assumptions can be explicit configuration.
- [CodeCarbon](https://docs.codecarbon.io/latest/): runtime measurement solves a different stage of the workflow.
- [Hugging Face Trainer](https://huggingface.co/docs/transformers/main_classes/trainer): fractional epochs and max_steps precedence require semantic adapters.
- [Lightning Trainer](https://lightning.ai/docs/pytorch/stable/common/trainer.html): device and node settings cannot be reduced to a global key rename.
- [GitHub secure use](https://docs.github.com/en/actions/reference/security/secure-use): least privilege and immutable action references.
