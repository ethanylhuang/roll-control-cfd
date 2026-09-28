#!/bin/zsh
# pseudo-transient NON-transonic (same pressure equation as the converged steady runs, stabilized by local time stepping):
# M0.90 validation (no sheet), M0.95, M0.85 (sheet), then the steady upwind comparison at M0.9.
cd /Users/trasomi/dev/cfd
setopt NO_BG_NICE
run() { name=$1; mach=$2; echo "$(date +%H:%M:%S) start $name"; ./venv/bin/python -u run_lts_case.py $mach $name --no-transonic > run_$name.log 2>&1; rc=$?
  echo "$(date +%H:%M:%S) done $name rc=$rc: $(grep -E 'stop=' run_$name.log | tail -1 | cut -c1-200) | $(grep -E '"Mroll"' run_$name.log | head -1 | tr -d ' ')"
  if [ "$3" = "sheet" ] && [ -f runs_v4/d10/$name/result.json ]; then ./venv/bin/python fill_sheet_row.py runs_v4/d10/$name 2>&1 | sed "s/^/  sheet: /"; fi; }
run M0.90_filled_fine_LTSnt 0.90 nosheet
run M0.95_filled_fine_LTSnt 0.95 sheet
run M0.85_filled_fine_LTSnt 0.85 sheet
name=M0.90_filled_fine_upwind; echo "$(date +%H:%M:%S) start $name"
./venv/bin/python -u run_simscale_match.py --start ramp --ramp-iters 300 --relax p=0.3,rho=0.05,U=0.7,h=0.7,k=0.7,omega=0.7 --pmin 20000 --pmax 300000 --open-sides --levels 5,6,6 --slot-level 6 --mesh-name mesh_filled_fine --endtime 2000 --avg-window 500 --mach 0.9 --div-u upwind --case $name > run_$name.log 2>&1
echo "$(date +%H:%M:%S) done $name rc=$?: $(grep -E 'stop=' run_$name.log | tail -1 | cut -c1-200) | $(grep -E 'Mroll' run_$name.log | tail -1 | cut -c1-160)"
echo "$(date +%H:%M:%S) LTS2 QUEUE DONE"
