Diagnostic only; nothing here counts as a pass. The frozen browser evaluators (evaluation/browser*.py,
hashes in evidence/frozen-inputs.sha256) FAILED for run 007; their stdout/stderr are evidence/*.cdp.*.
To learn whether anything else fails behind the first assertion, copies in diagnostic/evaluation change
exactly three interface points: cards selected by [data-service-id][data-state] (run-007 also tags
incident rows with data-service-id), .state font threshold 14px instead of 16px (run-007 uses 0.9rem =
14.4px; no contract states 16px), and colour judged on the background when the text colour is neutral
(the contract allows "computed green/red/amber or corresponding background"; the frozen check reads
only `color`). With those, 21/21 static, 6/6 live and the hung-fetch case pass.
control/run006-minor-phone-chrome158.png: run-006's preserved page through the same CDP wrapper on
Chrome 158 tiles the same way as run-007 screenshots, so CDP screenshots are a harness artifact on this
Chrome version (run 006 used Chrome 156); DOM proofs are unaffected. control/run007-minor-tablet-cli.png
is a plain CLI capture used for visual review.
