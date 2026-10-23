# Run 001 — first clean-room synthetic status kata

Result: clean builder executed on Priory; independent static HTML evaluation passed green → red with failure description/time → green. A negative control changed a copy of the recovery state to impaired and the evaluator rejected it (exit 1). No browser rendering or responsive-device verification was performed. This is evidence for one bounded experiment, not validation of the general regenerative method or every inception obligation.

## Frozen artifacts and separation

- `builder-input/CONTRACT.md`: behavior and minimal CLI/rendering interface, with no old implementation, history, source baseline, or Upptime links.
- `builder-input/observations.json`: fully synthetic Groundhog Day observations; names, date, spacing, and schema are proposed fixture values.
- `evaluation/oracle.json` and `evaluation/evaluate.py`: independently authored before builder dispatch; unavailable to the builder by instruction.
- `evidence/frozen-inputs.sha256`: hashes frozen before builder dispatch, verified on Priory before build/evaluation.
- `builder-output/`: implementation authored in a fresh context given only the contract and observations. The agent authored files in the Mini task workspace, then transferred only these outputs to Priory; execution happened on Priory. No model runtime or credentials were installed on Priory. Isolation is enforced by fresh context and explicit read restrictions, not an OS sandbox preventing all possible file reads.
- `snapshots/`: actual Priory-generated HTML outputs, not manually fabricated success evidence.
- `evidence/`: evaluation results, output hashes, negative-control outcome, and prebuild provenance.

Source intent revisions: td-status `0c764d975365112b2c791047c453b33337cb1a4b`; td-meta method `ae1ee5a7037beb8d1ef9120a2908ede4e60a79ab`. These informed evaluator preparation; the builder was not given those repositories or links. Run trigger: user authorized the synthetic clean-room experiment on Priory for td-meta #176.

## Actual execution

Execution user was non-root `stig` on verified Priory, under `/home/stig/experiments/td-meta-176/run-001`. Existing system services and another user's processes were observed and left untouched. Python 3.14.4, Git 2.53.0 and Node 18.20.8 were available; this run used Python's standard library only. No global installs, public listeners, production deployment, or shared SSH-config edits.

After transferring frozen inputs/evaluation and verifying hashes, the clean builder transferred `builder-output` and ran:

```sh
cd /home/stig/experiments/td-meta-176/run-001/builder-output
python3 render.py ../builder-input/observations.json ../snapshots
```

Exit 0; three snapshots created. The evaluator then ran separately:

```sh
cd /home/stig/experiments/td-meta-176/run-001
sha256sum -c evidence/frozen-inputs.sha256
python3 evaluation/evaluate.py snapshots > evidence/evaluation.json
sha256sum builder-output/render.py builder-output/BUILD.md snapshots/*.html > evidence/output.sha256
```

All hashes matched; evaluator exit 0. It checks component name, explicit state and inline color, visible/semantic observation timestamp, failure/healthy description, help and experiment labeling. The negative control copied snapshots under `evidence/negative-control`, replaced recovery `data-state="healthy"` with `data-state="impaired"`, and reran the same evaluator; expected failure was recorded without modifying actual snapshots.

## Reproduction

From this directory with Python 3:

```sh
python3 builder-output/render.py builder-input/observations.json snapshots
python3 evaluation/evaluate.py snapshots
```

## Limits and next review

The evaluator inspects HTML semantics and an explicit color declaration, not computed browser style, visual presentation, accessibility, or responsive usability. It does not establish help effectiveness, proportionate impact comprehension, unknown/stale evidence policy, multi-component behavior, live probes/scheduling, or production readiness. Original obligations remain in the contract; no timing thresholds, incident log, or downtime duration were added. The HTML remains a generated experimental artifact, not a production replacement.

Next: review the three snapshots and the small interface/evaluator choices before deciding the next experiment. Brownfield characterization for TD Edge/Core remains pinned research, not started here.
