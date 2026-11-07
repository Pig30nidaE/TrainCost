# Hugging Face config corpus

Run the local evaluator from the repository root:

```bash
python scripts/verify_hf_corpus.py
```

The corpus has 50 labeled, minimized scenarios. The three source templates retain selected literal training settings from upstream examples. Each remaining scenario applies the changes named in its `id` and fields. Metadata such as GPU type, GPU count, and minutes per epoch is illustrative and was added here. The source examples did not supply those cost inputs. The model-only, conflicting, and secret examples are synthetic boundary tests, not upstream configurations.

The `accept` label expects normalization and analysis to succeed. Cases with `no_stale` reject a stale-runtime warning for an epoch-only change, an explicit `max_steps=-1` default, or equivalent alias values. `reject` expects a configuration error. `stale` expects a warning when a runtime-affecting input changes but minutes per epoch does not. `unsupported` expects a warning that names an unmodeled training setting. `redact` expects the synthetic sensitive value to stay out of the report and diagnostics. The evaluator constructs the test value at runtime. It does not read or transmit user credentials.

These are deliberately constructed tests, not a random sample of users or repositories. The case count and pass rate do not measure adoption, production accuracy, prediction quality, or prevalence of supported configurations. The upstream examples were written for training frameworks, not for TrainCost. Training code, data, weights, and model downloads are not part of this corpus.

## Source and transformation record

All three source files carry Apache License 2.0 notices. Copyright belongs to the Hugging Face contributors in the linked files. Only a few field names and literal values were retained. Original explanatory text and full files were not copied. Each scenario references its source by ID in `corpus.json`; each `set`, `top`, `base_set`, `base_top`, `remove_top`, `shape`, or `replace` entry records the mutation from that template.

| Source | Pinned file | Retained settings |
| --- | --- | --- |
| Transformers | [training.md at `2c6a00f`](https://github.com/huggingface/transformers/blob/2c6a00f97fab4643f473c1b2e3d430399175abf5/docs/source/en/training.md), [license](https://github.com/huggingface/transformers/blob/2c6a00f97fab4643f473c1b2e3d430399175abf5/LICENSE) | Epochs 3, microbatch 2, accumulation 8, bf16 enabled |
| PEFT | [quicktour.md at `f482b81`](https://github.com/huggingface/peft/blob/f482b819536f475da8d4a304cd7a7e37cae59351/docs/source/quicktour.md), [license](https://github.com/huggingface/peft/blob/f482b819536f475da8d4a304cd7a7e37cae59351/LICENSE) | Epochs 2, microbatch 32 |
| TRL | [sft.py at `16996bc`](https://github.com/huggingface/trl/blob/16996bcd2ea3190409f4a94aa7ccfd1150759b9a/trl/scripts/sft.py), [license](https://github.com/huggingface/trl/blob/16996bcd2ea3190409f4a94aa7ccfd1150759b9a/LICENSE) | Epochs 1, microbatch 2, accumulation 8 |

The TRL source enables packing. The template deliberately omits it to isolate training argument translation; it must not be presented as a complete copy of that training run. `r16` restores packing to test the unsupported-setting warning. `t14` introduces a checkpointing change, and the conflict cases introduce combinations not claimed by the original examples.
