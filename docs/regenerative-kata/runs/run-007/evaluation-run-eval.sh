#!/bin/sh
# Run 007 backend evaluation on Priory, mirroring run-006 README "Reproduce from fresh output".
# Usage: sh run-eval.sh  (from /home/stig/experiments/td-meta-176/run-007)
set -u
RUNDIR=$(pwd)
TS=$(date -u +%Y%m%dT%H%M%SZ)
EVAL="$RUNDIR/independent-eval-$TS"
mkdir "$EVAL"
cp -R builder-input builder-output evaluation "$EVAL/"
mkdir "$EVAL/evidence"
cp evidence/frozen-inputs.sha256 evidence/output.sha256 "$EVAL/evidence/"
cd "$EVAL"
sha256sum -c evidence/frozen-inputs.sha256 > evidence/frozen-input-verification.txt 2>&1; echo "frozen-check rc=$?"
sha256sum -c evidence/output.sha256 > evidence/output-verification.txt 2>&1; echo "output-check rc=$?"
for stage in evaluate:functional-first operations:operations alerts:alerts resilience:resilience evaluate:functional-repeat; do
  script=${stage%%:*}; label=${stage#*:}
  python3 -B evaluation/$script.py > evidence/$label.stdout 2> evidence/$label.stderr
  rc=$?; echo "$label rc=$rc"; echo "{\"stage\":\"$label\",\"exit\":$rc}" >> evidence/stage-exits.jsonl
  [ "$label" = functional-first ] && cp evidence/functional-results.json evidence/functional-results-first.json 2>/dev/null
done
echo "$EVAL"
