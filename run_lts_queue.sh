#!/bin/zsh
# waits for the steady Mach sweep to finish, then runs the high-Mach cases with the pseudo-transient solver
cd /Users/trasomi/dev/cfd
setopt NO_BG_NICE
QP=$(awk '{print $NF}' run_mach_sweep.pid)
while kill -0 $QP 2>/dev/null; do sleep 120; done
echo "$(date +%H:%M:%S) steady queue finished; starting LTS queue"
run() { name=$1; mach=$2; echo "$(date +%H:%M:%S) start $name"; ./venv/bin/python -u run_lts_case.py $mach $name > run_$name.log 2>&1; rc=$?
  echo "$(date +%H:%M:%S) done $name rc=$rc: $(grep -E 'stop=' run_$name.log | tail -1 | cut -c1-200) | $(grep -E '"Mroll"' run_$name.log | head -1 | tr -d ' ')"
  if [ "$3" = "sheet" ] && [ -f runs_v4/d10/$name/result.json ]; then ./venv/bin/python fill_sheet_row.py runs_v4/d10/$name 2>&1 | sed "s/^/  sheet: /"; fi; }
run M0.95_filled_fine_LTS 0.95 sheet
run M0.90_filled_fine_LTS 0.90 nosheet
run M0.85_filled_fine_LTS 0.85 sheet
echo "$(date +%H:%M:%S) LTS QUEUE DONE"
