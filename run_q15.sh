#!/bin/zsh
# after q14: re-run the unconverged 15-deg / M0.9 point with twice the iterations and a 1000-iteration window
cd /Users/trasomi/dev/cfd
setopt NO_BG_NICE
P=$(awk '{print $NF}' run_q14.pid); while kill -0 $P 2>/dev/null; do sleep 300; done
COMMON="--start ramp --ramp-iters 300 --relax p=0.3,rho=0.05,U=0.7,h=0.7,k=0.7,omega=0.7 --pmin 20000 --pmax 300000 --open-sides --levels 5,6,6 --slot-level 6 --endtime 4000 --avg-window 1000"
name=M0.90_filled_fine_opensides_long
echo "$(date +%H:%M:%S) start d15 $name"
./venv/bin/python -u run_simscale_match.py ${=COMMON} --mesh-name mesh_filled_fine --deflection=15 --mach 0.9 --case $name > run_d15_$name.log 2>&1; rc=$?
echo "$(date +%H:%M:%S) done d15 $name rc=$rc: $(grep -E 'stop=' run_d15_$name.log | tail -1 | cut -c1-160) | $(grep -E '"Mroll"' run_d15_$name.log | head -1 | tr -d ' ')"
if [ -f runs_v4/d15/$name/result.json ]; then
  ./venv/bin/python -c "
import json; r=json.load(open('runs_v4/d15/$name/result.json')); c=r['convergence']; print('convergence', {k: c.get(k) for k in ('std_rel_pct','drift_pct','flags')})"
  ./venv/bin/python fill_coeff_row.py runs_v4/d15/$name 2>&1 | sed "s/^/  sheet: /"
fi
echo "$(date +%H:%M:%S) Q15 DONE"
