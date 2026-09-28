#!/bin/zsh
# queue 3: steady SIMPLE (the validated route) for M0.85 2nd-order; then first-order upwind at M0.90 (bias calibration) and M0.95 (only converging steady option there)
cd /Users/trasomi/dev/cfd
setopt NO_BG_NICE
COMMON="--start ramp --ramp-iters 300 --relax p=0.3,rho=0.05,U=0.7,h=0.7,k=0.7,omega=0.7 --pmin 20000 --pmax 300000 --open-sides --levels 5,6,6 --slot-level 6 --mesh-name mesh_filled_fine --endtime 2000 --avg-window 500"
run() { name=$1; shift; sheet=$1; shift; echo "$(date +%H:%M:%S) start $name"; ./venv/bin/python -u run_simscale_match.py ${=COMMON} "$@" --case $name > run_$name.log 2>&1; rc=$?
  echo "$(date +%H:%M:%S) done $name rc=$rc: $(grep -E 'stop=' run_$name.log | tail -1 | cut -c1-200) | $(grep -E '"Mroll"' run_$name.log | head -1 | tr -d ' ')"
  if [ "$sheet" = "sheet" ] && [ -f runs_v4/d10/$name/result.json ]; then ./venv/bin/python fill_sheet_row.py runs_v4/d10/$name 2>&1 | sed "s/^/  sheet: /"; fi; }
run M0.85_filled_fine_opensides sheet   --mach 0.85
run M0.90_filled_fine_upwind    nosheet --mach 0.90 --div-u upwind
run M0.95_filled_fine_upwind    sheet   --mach 0.95 --div-u upwind
echo "$(date +%H:%M:%S) Q3 DONE"
