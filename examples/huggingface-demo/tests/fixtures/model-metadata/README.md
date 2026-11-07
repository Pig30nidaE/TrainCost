# Reviewed upstream metadata

These are byte-preserved `config.json` and `tokenizer_config.json` files downloaded
for the real-model study, not model weights or dataset text. Their SHA-256 values
are pinned in `examples/hf-model-matrix/profiles.json` and checked before model
construction. The metadata is distributed under the models' Apache-2.0 licenses.

- DistilBERT: [revision 12040acc](https://huggingface.co/distilbert/distilbert-base-uncased/tree/12040accade4e8a0f71eabdb258fecc2e7e948be).
- BERT: [revision 86b5e093](https://huggingface.co/google-bert/bert-base-uncased/tree/86b5e0934494bd15c9632b12f734a8a67f723594).
- ALBERT: [revision 8e2f239c](https://huggingface.co/albert/albert-base-v2/tree/8e2f239c5f8a2c0f253781ca60135db913e5c80c).

Do not reformat these files without reviewing and updating the corresponding
profile hashes. New profiles require reviewed metadata and a regression fixture.
