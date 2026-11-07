# Optional training dependency security

Status on 2026-11-08: replacement locks audited; fresh training verified. Core and Action do not import Torch,
Transformers, or datasets. The optional model experiment does. Successful
training does not substitute for dependency security review.

The [original audit](evidence/hf-matrix-2026-11-08/ml-dependency-audit.json) used
pip-audit 2.10.1, the exact macOS lock, PyPI advisory data, and
`--disable-pip --no-deps --strict`, without ignored vulnerabilities. The complete
environment had been installed from the hash-pinned lock. The audit reported 16
entries in four packages, including four duplicate CVEs: 12 distinct vulnerabilities.
Some duplicate records disagree about fixed versions. An empty fix list does not
establish that the latest version is safe or unfixable.

## Exposure review

QAReview compared advisories with the pinned workflow without running exploit code.
It found no evidence that their specific exploit paths were executed. This is a
bounded code-path assessment, not a no-impact guarantee.

| Package | Advisory scope | Current experiment boundary |
| --- | --- | --- |
| datasets | Folder metadata traversal, [CVE-2026-66007](https://github.com/advisories/GHSA-379c-qx7v-6h59) | Fixed local parquet, no folder builder |
| fsspec | Reference template execution, [CVE-2026-104851](https://github.com/advisories/GHSA-27vj-qcqg-25rc) | No reference filesystem or supplied catalog |
| torch | `.pt2` loading, CVE-2026-4538 | No `.pt2` import; fix status needs review |
| torch | JIT/LSTM corruption, CVE-2025-3000 / CVE-2025-3001 | No explicit scripting or LSTM; transitive calls still require care |
| torch | Pickle loading, [CVE-2026-24747](https://github.com/advisories/GHSA-63cw-57p8-fm3p) | Safetensors only, no resume |
| transformers | X-CLIP conversion, CVE-2025-14929 | No conversion tool invoked; fix status needs review |
| transformers | RNG restore, [CVE-2026-1839](https://github.com/advisories/GHSA-69w3-r845-3855) | No resume; advisory also specifies older Torch conditions |
| transformers | Kernel config, [CVE-2026-4372](https://github.com/advisories/GHSA-29pf-2h5f-8g72) | Pinned metadata; custom kernel keys rejected |
| transformers | LightGlue remote code, [CVE-2026-5241](https://github.com/advisories/GHSA-fgcw-684q-jj6r) | Reviewed model types; nested remote-code keys rejected |
| transformers | Tokenizer paths, [CVE-2026-9856](https://github.com/advisories/GHSA-xrqw-3rrv-vx5w) | No tokenizer save; template/path controls rejected |
| transformers | Generation download, [CVE-2026-80047](https://github.com/advisories/GHSA-x9r9-c232-4q39) | No generation or custom-generation hook |

Restrictions do not repair upstream libraries. Integration regenerated both
platform locks. The new versions include Torch 2.14.1, Transformers 5.22.2,
datasets 5.1.0, and fsspec 2026.7.0. The complete
[macOS audit](evidence/hf-matrix-2026-11-08/updated-macos-audit.json) covers 52
packages and the [CUDA audit](evidence/hf-matrix-2026-11-08/updated-cuda-audit.json)
covers 71. Both report zero known advisory entries without ignored vulnerabilities.
Each record includes the lock SHA-256, tool version, and timestamp. Absence of
known advisories is not proof that packages have no vulnerabilities.

`scripts/audit_ml_dependencies.py` audits both locks in CI without installing ML
packages. It rejects missing hashes, conditional/duplicate entries, unexpected
direct URLs, skipped results, and incomplete coverage. The official CUDA wheel's
public Torch version is queried alongside every pinned CUDA dependency. This is
advisory checking, not binary scanning or GPU compatibility validation.

## Loading boundary

`model_safety.py` runs before Transformers in all three local runners. It rejects
duplicate/nonfinite or overlarge/deep metadata, unreviewed hashes, mismatched model
types, remote-code/kernel fields, external-file references, and chat templates.
Actual upstream fixtures and synthetic rejection cases cover the boundary.
Unreviewed model-size changes cannot reach model construction.

Source inventory version 2 includes this helper. Version 1 remains unchanged for
historical Git replay. Old profiles remain readable for evidence replay; new
execution requires reviewed metadata hashes. Do not relabel old measurements as
runs of the new dependencies or loading boundary.

The [replacement-environment study](hf_security_upgrade_study.md) measured commit
`26613f6`: 27 fresh runs, all training/report/timing checks passed. The committed
source includes the loading boundary. All earlier observations remain preserved;
new dependencies did not inherit the old study's timing or training results.
CUDA execution remains deferred to the user-operated WSL2 machine.
