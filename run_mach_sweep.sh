#!/bin/zsh
# 10 deg tab, filled-gap CAD, local OpenFOAM Mach sweep on the grid-converged mesh (5/6/6, 1.5 M cells)
# with the SimScale-matched settings that converged at M0.9 (ramp300, v4 relaxation, p 20-300 kPa, open sides).
cd /Users/trasomi/dev/cfd
setopt NO_BG_NICE
COMMON="--start ramp --ramp-iters 300 --relax p=0.3,rho=0.05,U=0.7,h=0.7,k=0.7,omega=0.7 --pmin 1000 --pmax 1000000 --open-sides --levels 5,6,6 --slot-level 6 --mesh-name mesh_filled_fine --endtime 2000 --avg-window 500"
run() { name=$1; shift; echo "$(date +%H:%M:%S) start $name"; ./venv/bin/python -u run_simscale_match.py ${=COMMON} "$@" --case $name > run_$name.log 2>&1; rc=$?
  echo "$(date +%H:%M:%S) done $name rc=$rc: $(grep -E 'stop=' run_$name.log | tail -1 | cut -c1-200) | $(grep -E 'Mroll' run_$name.log | tail -1 | cut -c1-160)"
  if [ -f runs_v4/d10/$name/result.json ]; then ./venv/bin/python fill_sheet_row.py runs_v4/d10/$name 2>&1 | sed "s/^/  sheet: /"; else echo "  no result.json for $name"; fi; }
# M0.95 and M0.85 need the pseudo-transient (LTS) solver: steady SIMPLE limit-cycles at M>=0.95 on this mesh (2026-09-05 00:24-01:10)
run M0.80_filled_fine_opensides --mach 0.80
run M0.70_filled_fine_opensides --mach 0.70
run M0.60_filled_fine_opensides --mach 0.60
run M0.50_filled_fine_opensides --mach 0.50
run M0.30_filled_fine_opensides --mach 0.30
echo "$(date +%H:%M:%S) MACH SWEEP DONE"
