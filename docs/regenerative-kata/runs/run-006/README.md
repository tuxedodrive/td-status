# Run 006 — independent evaluation of the final frozen candidate

Run 006 demonstrates the essential replacement behavior under synthetic interfaces, including the two resilience gaps preserved in Run 003. This is a working candidate for configuration and activation review; production is unchanged. The live Priory demonstration remains Run 003, not this candidate.

## Provenance and limits of the record

The original candidate was already present at `/home/stig/experiments/td-meta-176/run-006` when independent evaluation began on 2026-10-23. Its final contract and seven evaluator files matched the pre-existing `frozen-inputs.sha256` manifest. The retained contract heading says “run 005”; that heading is preserved byte-for-byte, not silently rewritten. Run 006 is the subsequent candidate directory built against that frozen contract. The final contract makes notification delivery a separate bounded worker and requires finite, abortable browser refresh deadlines.

The independent evaluator did not author or modify this builder output. It copied the candidate, contract and evaluators to a new directory, `/home/stig/experiments/td-meta-176/independent-run006-20261023T162009Z`, and ran tests only there. This continuation verifies the files and behavior; it does not independently attest to unseen builder-session isolation. The original builder instruction requires a fresh contract-only implementation. Do not turn that instruction alone into proof of an OS-enforced clean room.

`evidence/source-before.json` and `source-after.json` identify the twelve original contract/evaluator/builder files. Checks between remote evaluations, during browser review and at **16:23:14 UTC** found no concurrent source changes. `evidence/final-source-check.json` records original/copy equality. Original `builder-output/status.py` SHA-256:

```
f35a26e9169699e02a7dea1b9ed61e0c85a8ea4ebfc888e4c10829acc9fca0f9
```

## Results

| Boundary | Independent result | Evidence |
|---|---|---|
| Functional monitoring, history, stale/absent evidence, scope and safe removal | 20 passes; repeated with a distinct generated work directory, exit 0 again | `evidence/functional-results.json`, `evaluate.stdout`, `evaluate-repeat.stdout` |
| Durable opened/resolved alert events, retry and stable identity | 8 passes against a loopback sink | `evidence/alert-results.json` |
| Static serving with dependencies/monitor stopped; backup/restore | HTTP 200 and both operational assertions true | `evidence/operations-results.json` |
| Delivery worker isolation and bounded drain | 4 passes | `evidence/resilience-results.json` |
| Static/responsive browser | 21 passes: seven states × phone/square/tablet | `browser-review/results.json` and screenshots |
| Open-page recovery and failed-refresh aging | 6 passes: two cases × three viewports | `browser-live/results.json` and screenshots |
| Hung first fetch followed by available recovery | pass: two fetch calls; ten healthy services at 3.5 seconds | `evidence/browser-hung-result.json` |

The stalled sink delayed each synthetic event by two seconds. Impairment collection/publication completed in **0.094106 seconds**; recovery while the delivery worker was stalled completed in **0.083101 seconds**. Six queued opening/recovery events survived and were delivered to the local fake without loss. Those measurements are local test outcomes, not production latency promises.

The hung-fetch fixture advances its controlled clock using `performance.now()`. With one-second refresh and a half-second abort deadline, the first fetch remains unresolved until aborted and subsequent requests expose recovery. This checks recovery within the contract's four-second synthetic budget; it does not freeze freshness while waiting.

## Preserved harness failures and correction

Initial installed-Chrome CLI runs failed `healthy-phone: overflow` and `recover-phone: overflow`. Diagnostic DOM proof showed **500px innerWidth despite a requested 390px window**, document width 500 and no overflowing elements. These were viewport-harness capability failures, not demonstrated page overflow. Original stdout/stderr and `evidence/browser-independent-summary.json` remain intact. `evidence/cli-viewport-proof.json` records that diagnosis.

The browser invocation adapter was replaced by `evaluation/chrome-cdp-wrapper.py`, which uses the same installed Chrome with a new temporary profile per case, exact CDP viewport emulation, the requested virtual-time budget, DOM capture and screenshots. The frozen evaluator files and their assertions were unchanged. All three browser evaluators then exited 0; `evidence/browser-cdp-summary.json` preserves the outcomes. Chrome version: **156.0.8078.47**. Viewports: **390×844**, **720×720**, **820×1180**. This is desktop browser emulation, not physical-device, cross-browser, full accessibility or user-comprehension validation.

## Reproduce from fresh output

Use an existing Python 3 environment. From this run directory, make a new isolated copy (never run into a preserved evidence directory):

```sh
set -eu
RUN=$(mktemp -d /tmp/status-run006-eval.XXXXXX)
cp -R builder-input builder-output evaluation "$RUN/"
mkdir "$RUN/evidence"
cp evidence/frozen-inputs.sha256 "$RUN/evidence/"
cd "$RUN"
sha256sum -c evidence/frozen-inputs.sha256
python3 -B evaluation/evaluate.py > evidence/functional-first.stdout 2> evidence/functional-first.stderr
python3 -B evaluation/operations.py > evidence/operations.stdout 2> evidence/operations.stderr
python3 -B evaluation/alerts.py > evidence/alerts.stdout 2> evidence/alerts.stderr
python3 -B evaluation/resilience.py > evidence/resilience.stdout 2> evidence/resilience.stderr
python3 -B evaluation/evaluate.py > evidence/functional-repeat.stdout 2> evidence/functional-repeat.stderr
```

On macOS use `shasum -a 256 -c` instead of `sha256sum -c`. Each functional invocation creates a unique `evaluation/generated/functional-*` and writes `evidence/latest-functional-work.json`; operations/browser evaluators follow that relative pointer. A repeat does not require deleting tracked fixture state. Use separate output capture names to retain both invocations. Run commands sequentially and stop on a nonzero exit; do not alter assertions to fit output.

For the browser stages, copy the isolated evaluator tree and generated synthetic snapshots to the Mini, which already has Chrome. The invocation wrapper uses the existing `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome` and `/opt/homebrew/bin/python3`; it installs nothing. Make the wrapper executable, then:

```sh
chmod u+x evaluation/chrome-cdp-wrapper.py
python3 evaluation/browser.py "$PWD/evaluation/chrome-cdp-wrapper.py"
python3 evaluation/browser_live.py "$PWD/evaluation/chrome-cdp-wrapper.py"
python3 evaluation/browser_hung.py "$PWD/evaluation/chrome-cdp-wrapper.py"
```

All synthetic HTTP fixtures bind loopback and their evaluators stop them. Browser processes are evaluator-owned with unique profiles and are stopped by the wrapper. No real provider endpoint, external email, GitHub issue transport or public listener is exercised.

## Remaining configuration and activation choices

The source-mapped dormant configuration and Run 004 synthetic SMTP/GitHub adapter remain separate artifacts under `../../readiness` and `../run-004`. This run proves the generic outbox/worker boundary; it does not claim integration of that adapter, authenticated transport success, human receipt, or real external alert delivery.

Existing source supplies probe URLs/codes/keywords, 5000ms timeouts, 900-second cadence, support mailbox and configured `.dev` host. Do not describe those as unknown. New freshness/retention policy still needs a deliberate choice; dormant draft freshness is null to prevent accidental activation. Confirm whether the user's `.com` wording means a different canonical host. Review actual endpoint/impact/support configuration, SMTP/From/auth and approved GitHub credential/destination if those transports are selected, public hosting/TLS/DNS, process supervision, backup/retention and a cutover/rollback plan. Nothing here changes production or declares cutover complete.

Preserved Run 003 failures remain valid historical evidence. Run 005 recorded intermediate passing resilience results; Run 006 is the latest candidate independently evaluated here. No retrospective claim that earlier passes covered the missing resilience boundaries is made.
