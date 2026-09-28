#!/bin/zsh
# the two missing 10-deg coarse Machs on the validated Sep-4 geometry/mesh (parallel), then sheet rows
cd /Users/trasomi/dev/cfd
SP=/private/tmp/claude-501/-Users-trasomi-dev-cfd/e77796e5-73f1-4b54-ac10-df1a9b566759/scratchpad
B=$(./venv/bin/python -c "import json; print(json.load(open('$SP/coarse_d10_ref.json'))['base'])"); M=$(./venv/bin/python -c "import json; print(json.load(open('$SP/coarse_d10_ref.json'))['mesh'])")
for m in 0.6 0.8; do
  ( ./venv/bin/python -u $SP/ss_sweep_run.py --mach $m --deflection 10 --base $B --mesh $M --label "COARSE mesh 922k" > $SP/ss_sweep_d10_M${m}_coarse.log 2>&1; rc=$?
    echo "$(date +%H:%M:%S) done d10 M$m coarse rc=$rc: $(grep -E 'run (FINISHED|FAILED|CANCELED)' $SP/ss_sweep_d10_M${m}_coarse.log | tail -1)"
    f=$SP/ss_sweep_d10_M${m}_coarse.json; [ -f $f ] && GOOGLE_WORKSPACE_CLI_KEYRING_BACKEND=file ./venv/bin/python fill_coeff_row_ss.py $f 2>&1 | sed "s/^/  sheet: /" ) &
done
wait; echo "$(date +%H:%M:%S) D10 COARSE FILL DONE"
