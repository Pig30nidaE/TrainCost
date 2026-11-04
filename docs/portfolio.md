# Portfolio walkthrough

TrainCost CI is a Python developer tool for reviewing ML experiment cost risk before training starts.
The portfolio contribution is the handling of uncertain and untrusted inputs, not a claim of accurate GPU runtime prediction.

## A five-minute walkthrough

1. Show the risky config diff and its report: epochs 5 to 50, T4 to A100, and one GPU to two.
2. Show the incomplete config report. Explain which values were assumed and why confidence is Low.
3. Show the invalid config report. Explain why NaN or a negative epoch must not become a trustworthy cost.
4. Open a real Git regression test. Show that deleted configs are excluded and worktree edits cannot change committed evidence.
5. Show the candidate's CI run, independent wheel install, source paths, and security regression tests.

## Engineering decisions to discuss

- Keep core analysis independent of GitHub to make it testable and installable.
- Parse configuration without executing PR code.
- Validate at input boundaries and report exact field paths.
- Treat missing values, invalid values, and Git failures as different states.
- Remove sensitive data before diffing rather than relying on masking after rendering.
- Make installation reproducible and isolate dependencies from the consumer repository.
- Preserve tests that reproduce specific mistakes instead of measuring progress by test count.

## Evidence and honest limits

See docs/qa_report.md for measured tests, coverage, environment, and run links.
Demo monetary values use supplied rates and runtime inputs. No actual cost savings or runtime accuracy is claimed.
There are no verified external adopters or benchmarked real training workloads in this repository.
Framework adapters and live comment behavior remain follow-up work.

## Research references

- [Infracost usage costs](https://www.infracost.io/docs/features/usage_based_resources/): usage assumptions can be explicit configuration.
- [CodeCarbon](https://docs.codecarbon.io/latest/): runtime measurement solves a different stage of the workflow.
- [Hugging Face Trainer](https://huggingface.co/docs/transformers/main_classes/trainer): fractional epochs and max_steps precedence require semantic adapters.
- [Lightning Trainer](https://lightning.ai/docs/pytorch/stable/common/trainer.html): device and node settings cannot be reduced to a global key rename.
- [GitHub secure use](https://docs.github.com/en/actions/reference/security/secure-use): least privilege and immutable action references.
