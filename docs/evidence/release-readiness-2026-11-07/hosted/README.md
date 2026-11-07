# Hosted candidate evidence

Downloaded from artifact `traincost-release-evidence` of
[run 42350745903](https://github.com/Pig30nidaE/TrainCost/actions/runs/42350745903).
The reports and verification.json are unedited artifact bytes. The workflow copy
is from consumer commit `95486b6c43cf9eb2da14b164cda57f68454260aa`.

`verification.json` records the actual Action outputs and successful assertions.
The workflow uses code candidate `20af5724ed292066d79c8e47557baf5dd3e14a43`, not
the later evidence commit. It checks complete, partial, error, output-link safety,
and byte equality with runner Step Summary files. It does not validate an external
repository, a real fork, live comments, rendered GitHub UI, or GPU training.

To retrieve the original artifact while GitHub retains it:

```bash
gh run download 42350745903 --repo Pig30nidaE/TrainCost \
  --name traincost-release-evidence --dir /tmp/traincost-evidence
```

Repository access is required. The artifact retention period is 14 days; these
copies preserve the selected evidence independently of that expiry. No raw job
logs, tokens, model weights, dataset text, or full environment dumps are included.
