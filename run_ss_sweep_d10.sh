#!/bin/zsh
# SimScale 10-deg fine-mesh (v3) sweep at M <= 0.85, one run at a time, results into the SimScale coefficient tab
cd /Users/trasomi/dev/cfd
SP=/private/tmp/claude-501/-Users-trasomi-dev-cfd/e77796e5-73f1-4b54-ac10-df1a9b566759/scratchpad
for m in 0.3 0.5 0.6 0.7 0.8 0.85; do
  echo "$(date +%H:%M:%S) start SimScale d10 M$m"
  ./venv/bin/python -u $SP/ss_sweep_run.py --mach $m --deflection 10 > $SP/ss_sweep_d10_M$m.log 2>&1; rc=$?
  echo "$(date +%H:%M:%S) done SimScale d10 M$m rc=$rc: $(grep -E 'run (FINISHED|FAILED|CANCELED)' $SP/ss_sweep_d10_M$m.log | tail -1) | $(grep -E '"Mroll"' $SP/ss_sweep_d10_M$m.log | head -1 | cut -c1-140)"
  f=$SP/ss_sweep_d10_M$m.json; [ -f $f ] && ./venv/bin/python fill_coeff_row_ss.py $f 2>&1 | sed "s/^/  sheet: /"
done
echo "$(date +%H:%M:%S) SS SWEEP D10 DONE"
