# Security policy

TrainCost CI reads configuration files and Git history on the local runner. Cost estimates are advisory. Do not commit credentials, private training data, or model weights to an issue, pull request, or test fixture.

## Report a vulnerability

Do not open a public issue for a suspected vulnerability. If the repository's Security tab offers **Report a vulnerability**, use that private reporting flow. If it does not, contact a maintainer through an existing trusted private channel before sharing technical details. This repository does not currently specify a separate security email address or response-time commitment.

Provide the affected version or commit, the conditions required to reproduce the issue, and a minimal synthetic reproduction. Remove tokens, customer data, private paths, logs containing secrets, and unrelated configuration. For an exposed credential, revoke or rotate it through its provider; do not include it in the report.

## Scope

Useful reports include secret disclosure in generated reports, unsafe config parsing, execution of untrusted repository content, and unexpected token exposure. Reports about cost-estimate accuracy should use a normal issue unless they reveal a security problem. No hosted service or external code upload is required for local analysis.
