# Troubleshooting

**A run finishes instantly with 0 test cases.** `corpus_dir` didn't
resolve to a real directory — almost always because the config file was
copied outside `config/` without adjusting the relative path (see
[CONFIGURATION.md](CONFIGURATION.md#path-resolution--read-this-before-copying-the-file-anywhere)).
Check:

```bash
python3 -c "from promptfuzzr.config import RunConfig; print(RunConfig.from_yaml('your-config.yaml').corpus_dir)"
```

**A run seems to hang for a long time.** Almost always retry volume (see
[CONCEPTS.md](CONCEPTS.md#retries-are-outcome-based-not-just-error-based)),
not an actual hang. Drop `max_retries` to 1 and try again. If it's still
stuck at `max_retries: 1`, it's a genuine network stall — check the
target/router is actually reachable.

**Everything comes back `verdict: error`.** Run `findings --verdict error`
and read the `notes` column — it's the actual exception message (missing
API key, unreachable endpoint, malformed provider response), not a generic
failure.

**Everything comes back `verdict_basis: heuristic` when you expected
`action_outcome`.** The target never called a tool. Either it doesn't
support/isn't using tool calling (see
[USAGE.md](USAGE.md#confirming-tool-calling-support-before-a-real-run)), or
your seeds genuinely aren't triggering tool use for this target — check
with `target_profile: vulnerable` first to confirm the judge itself is
working (see [CONFIGURATION.md](CONFIGURATION.md#scenario-validating-the-pipeline-itself)).

**`minimize` fails with a propagation error.** Only `single_shot` findings
can be minimized — see [USAGE.md](USAGE.md#minimize--reduce-a-finding-to-its-minimal-reproducer).

**You're not sure where your results went.** Always
`~/.promptfuzzr/db/promptfuzzr.db` (see [USAGE.md](USAGE.md#database)) — no
per-run or per-config separation.
