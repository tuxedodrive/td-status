# Browser and obligation review — run 001

Independent follow-up to the original Priory execution; no regeneration or product changes. Original output SHA-256 hashes were rechecked and all matched.

Priory had no Chromium/Firefox binary or Playwright/Puppeteer module. The Mini already had Google Chrome for Testing 147.0.7727.15, so verified output copies were rendered locally using `file://`, an isolated temporary browser profile, Chrome's normal sandbox, and no server, package installation or public deployment. The initial restricted process launch failed in Chrome sandbox initialization; the permitted escalated launch succeeded without disabling Chrome's sandbox.

## Checks and observations

Nine cases passed: three snapshots at each viewport:

| Viewport class | CSS pixels | Result |
| --- | --- | --- |
| Ordinary phone | 390 × 844 | 3/3 passed |
| Square unfolded-phone proxy | 720 × 720 | 3/3 passed |
| Tablet | 820 × 1180 | 3/3 passed |

`results.json` records actual viewport dimensions, document width, status/help bounds, computed font sizes/colors and text. All cases had no horizontal document or element overflow; status computed green/red/green; status/help had positive dimensions, visible styles and at least 16px text. All three phone screenshots and the square/tablet failure screenshots were visually inspected: readable wrapping, clear failure timestamp, and a readable help section. Normal vertical scrolling is allowed; this is not a requirement that the whole page fit one screen. Nine viewport screenshots are preserved under `screenshots/`.

`pages/` contains copies with an evaluation-only script inserted to observe DOM/layout; original snapshots are unchanged. The script adds only an invisible JSON script element after measurement. `run_browser.py` launches the existing browser for each case, captures screenshots/DOM, and evaluates those measurements. Invocation from the task workspace was `python3 run-001/browser-review/run_browser.py <existing-chrome-headless-shell-path>`. These are viewport proxies in one desktop browser, not physical-device, fold-hinge, touch, assistive-technology or cross-browser testing.

## Original obligation coverage

| Original obligation | Actual evidence | Still omitted / not established |
| --- | --- | --- |
| Healthy → received 502 → recovery | Frozen independent HTML assertions, browser-computed colors and displayed text/times for three snapshots; broken recovery negative control rejected | General event handling, multiple components, live transitions/scheduling |
| Independence from monitored platform | Self-contained local snapshots rendered without fetching app assets | Failure-boundary/hosting independence under an actual monitored-platform outage |
| Explicit coverage | Synthetic component is explicitly listed and its name displayed | Registry completeness, ten-service coverage and dependency-gap discovery |
| Honest evidence / uncertainty / freshness | Synthetic labeling, observation timestamps, limited-scope/freshness copy are present | Missing/stale/unknown fixtures and policy; no timing threshold selected or tested |
| Appropriate meaning / proportionate impact | Visible copy avoids claiming all wash operations are healthy/down | Minor/noncritical impairment scenario and customer impact/scope comprehension |
| Actionability, including green-but-broken | Help text and illustrative in-page destination are readable in green/red/recovery | A real support route, effective next action, or a user test of the green-but-broken journey; illustrative help is not full conformance |
| Responsive usability | Nine viewport checks and inspected screenshots support readable status/help with no horizontal overflow | Physical phone/foldable/tablet, keyboard/touch/screen-reader usability and cross-browser behavior |
| Technical staff/recovery journey | Success after failure renders healthy/green from fresh supplied observation | Real incident coordination, real telemetry and end-to-end staff workflow |

The passing slice and layout checks must not be presented as full contract conformance or validation of the general regenerative method. No new product behavior or scope is implied by this review. The useful next decision is whether the proposed boundary/evaluator and visual result are sufficient for this first kata, or which one bounded missing obligation to evaluate next.
