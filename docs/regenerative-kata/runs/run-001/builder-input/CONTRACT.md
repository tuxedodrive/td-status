# Groundhog Day status-page kata — run 001

Build a small page-only experience from supplied fixed observations. No live network monitoring, scheduling, external dependencies, or deployment.

The component boundary is a CLI: `python3 render.py INPUT.json OUTPUT_DIRECTORY`. Read an object with `components` (id/name pairs) and ordered `observations` (component_id, observed_at, result.kind, result.http_status). Write one self-contained UTF-8 HTML snapshot per observation, named `step-000.html`, `step-001.html`, etc. The output directory is supplied by the caller. Use Python standard library only. Do not fetch source or packages.

For each snapshot, display the component name and current status visibly. Success is healthy and green. A received HTTP 502 is red with a clear failure description and its observation timestamp. A fresh success restores green. Showing numeric 502 is optional. No exact prose, layout, debounce, stale-data threshold, incident log, or downtime duration is prescribed.

Expose the visible status container with `data-component-id` matching its input id and `data-state="healthy"` or `data-state="impaired"`. The container's inline `style` must set `color: green` or `color: red` respectively (a minimal testable rendering interface, proposed for this run). The failure timestamp must appear in a visible `time` element with matching `datetime` attribute. These attributes supplement real visible text; they cannot replace it.

Keep essential status and help readable on an ordinary phone, roughly square unfolded phone, and tablet. Explain that observations cover the listed component rather than diagnosing every wash problem, keep help visible even when green, and use a clearly labeled illustrative help destination without claiming real support response. Preserve uncertainty/freshness and proportionate-impact intent without inventing timing rules: show observation time, do not claim all wash operations are healthy or down, and do not claim unknown observations are fresh success. This run's fixed three-event evaluation does not validate every broader obligation.

Use the supplied arbitrary Groundhog Day component/date and 15-minute spacing as synthetic fixture values only, never as a runtime policy or real incident. This is an experiment, not operational status.
