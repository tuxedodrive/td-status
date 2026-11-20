# Run 007 — clean-room rebuild from a covenant-form contract

Run 007 asked whether restating the run 006 contract in IMP Covenant heavy form would produce a clean-room rebuild at least as good as run 006. It did not, under the frozen evaluator. The backend matched run 006: 20 functional checks passed twice, plus 8 alert, 4 resilience and 2 operations checks. All three browser stages failed. Each failure traces to a hook or threshold that the run 006 evaluator asserts and neither contract states. Production is unchanged; the Priory preview is still Run 003 on port 44167.

## What was frozen

- `builder-input/contracts/`: run 006's 61-line contract restated as one heavy-form component, `status.service`. It holds 45 obligations: 44 active, and I38 retired, because run 006 said in-line delivery "is superseded". There are 14 component decision records and 2 system ones, all `approved_by: pending JPB`. The "run 005" title slip is gone. An independent reviewer compared the two sentence by sentence; its 10 findings were fixed before freezing.
- `evaluation/`: the run 006 evaluators. Each check was tagged with `# proves[...]: status.service.I<n>` end-of-line comments. The ASTs are identical to run 006 (only comments added). Also included: `coverage.py`, a stdlib per-obligation report, and run 006's `chrome-cdp-wrapper.py`.
- `evidence/frozen-inputs.sha256` was written before the build. After evaluation, all 20 frozen-input and output hashes still verified on Priory.

## Builder isolation

This is stronger than runs 001–006. A fresh `claude -p --restricted` session (model opus, Claude Code 2.1.322) ran on the Mini in a new `mktemp` directory holding only `contracts/`. It ran 2026-11-20 16:49:14–16:59:42 UTC, 31 turns, about $2.43.

- File tools were confined to that directory.
- Bash ran in the macOS sandbox, with reads of `/Users`, the orchestrator scratch tree, `/private/var/folders` (old run006-cdp temp dirs) and `/Volumes` denied.
- Non-loopback network was blocked and there was no web tool.

The probes and their observed results are in `evidence/builder-isolation-probe.json`; the settings used are in `evidence/builder-sandbox-settings.json`. The builder never saw an evaluator, an earlier run or the journal. One difference from runs 001–006: the builder model is recorded here, which it was not before. That model difference is a confound.

## Results (frozen evaluator, Priory backend + Mini Chrome 158 via CDP)

| Boundary | Run 006 | Run 007 |
|---|---|---|
| Functional (fresh dirs) | 20 pass, twice | 20 pass, twice |
| Alerts | 8 pass | 8 pass |
| Serving with monitor/deps stopped; backup/restore | both true | both true |
| Stalled-sink resilience | 4 pass; 0.094 s / 0.083 s | 4 pass; 0.196 s / 0.158 s |
| Static/responsive browser (7 states × 3 viewports) | 21 pass | **FAIL** at the first case, `healthy-phone: text`: `.state` font is 14.4px; the evaluator asserts ≥16px |
| Open-page recovery / failed refresh | 6 pass | **FAIL** at `recover-phone`: 12 `[data-service-id]` elements; incident rows carry it too |
| Hung fetch then recovery | pass (2 calls) | **FAIL**: 2 calls and every card healthy, but 12 tagged elements instead of 10 |
| Obligation coverage (same tagged evaluator) | 30/44 active | **20/44** active |
| `status.py` | 160 lines | 1477 lines, plus the builder's own 13 loopback tests and `QUESTIONS.md` (10 questions) |

Coverage evidence: `independent-evaluation/evidence/coverage.txt` and `coverage.json`. The run 006 figure comes from running the same `coverage.py` over run 006's committed evidence.

**Fourteen active obligations have no check in either run:** I1, I5, I9, I14, I15, I17, I21, I26, I27, I30, I34, I35, I36, I37. They cover the stdlib-only rule, no external messaging, persisted fields, operator timing, config format, escaping and untrusted strings, bounded history, the provider caveat, no promises, the no-JS label, synthetic examples, ops and readiness docs, and the demo. These are untested obligations, not passes.

## Diagnosis of the browser failures (diagnostic, not passes)

`independent-evaluation/diagnostic/` holds copies of the browser evaluators that change only three interface points:

1. Cards are selected by `[data-service-id][data-state]`.
2. The `.state` font threshold is 14px instead of 16px.
3. Colour is judged on the background when the text colour is neutral. The contract allows a "computed green/red/amber or corresponding background", but the frozen check reads only `color`; run 007 uses white text on coloured badges.

With those changes, 21/21 static, 6/6 live and the hung-fetch case pass. The three points are gaps between the evaluator and the contract, present in run 006's contract too; run 006's builder happened to match them. The colour one is an evaluator defect against the contract's own wording. None of this changes the recorded failures.

CDP screenshots tile on Chrome 158; run 006 used Chrome 156. A control showed run 006's own preserved page tiling the same way through the same wrapper (`diagnostic/control/`). The screenshots are therefore a harness artifact, and the DOM proofs stand. Visual review used a plain CLI capture at tablet width: support sits in the header, states are shown by label as well as colour, and the provider caveat is visible.

## What the covenant form changed, observably

- The builder recorded 10 contract ambiguities in `builder-output/QUESTIONS.md`, as the regeneration brief invites. Runs 001–006 recorded none. Examples:
  - the publication-age threshold for `#banner`
  - whether outbox events exist without `notification_url`
  - the `deliver` exit code on a refused event
  - the fixed 5 s delivery timeout
  - extra public fields
- Per-obligation coverage made the 14 untested obligations and the browser-interface gaps visible as named ids rather than prose.
- It did not prevent the regression. The evaluator's interface assumptions are not in the contract, and a heavy-form restatement of the same prose cannot carry them.

## Reproduce

On Priory, from `/home/stig/experiments/td-meta-176/run-007`, run `sh evaluation-run-eval.sh`. It verifies both manifests, then runs functional, operations, alerts, resilience and a functional repeat in a fresh `independent-eval-<ts>/` directory. Unlike run 006's instructions, it continues past a failing stage so that every stage is recorded.

Browser stages run on the Mini, as for run 006: `python3 evaluation/browser.py "$PWD/evaluation/chrome-cdp-wrapper.py"`, then the same for `browser_live.py` and `browser_hung.py`.

Coverage: `python3 -I evaluation/coverage.py`. It exits 1 while any active obligation lacks a passing check.

## Placeholders, not policy

Freshness and retention policy, production cadence and timeouts, `.com` versus `.dev` canonical host, the real support destination, SMTP/From/auth, the GitHub credential and destination, hosting/TLS/DNS, supervision, backups and cutover/rollback all remain experiment placeholders. They are listed in the intent's Known limits and in the `production-activation-placeholders` record. No decision record is approved.
