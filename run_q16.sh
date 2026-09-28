#!/bin/zsh
# after q15: longer re-runs of the two remaining transonic points with block scatter > 3 % (12 deg and -6 deg at M0.9)
cd /Users/trasomi/dev/cfd
setopt NO_BG_NICE
P=$(awk '{print $NF}' run_q15.pid); while kill -0 $P 2>/dev/null; do sleep 300; done
COMMON="--start ramp --ramp-iters 300 --relax p=0.3,rho=0.05,U=0.7,h=0.7,k=0.7,omega=0.7 --pmin 20000 --pmax 300000 --open-sides --levels 5,6,6 --slot-level 6 --endtime 4000 --avg-window 1000"
for d in 12 -6; do
  tag=$(./venv/bin/python -c "print('dm%02d' % abs($d) if $d < 0 else 'd%02d' % $d)"); name=M0.90_filled_fine_opensides_long
  echo "$(date +%H:%M:%S) start $tag $name"
  ./venv/bin/python -u run_simscale_match.py ${=COMMON} --mesh-name mesh_filled_fine --deflection=$d --mach 0.9 --case $name > run_${tag}_$name.log 2>&1; rc=$?
  echo "$(date +%H:%M:%S) done $tag $name rc=$rc: $(grep -E 'stop=' run_${tag}_$name.log | tail -1 | cut -c1-160) | $(grep -E '"Mroll"' run_${tag}_$name.log | head -1 | tr -d ' ')"
  [ -f runs_v4/$tag/$name/result.json ] && { ./venv/bin/python -c "
import json; r=json.load(open('runs_v4/$tag/$name/result.json')); c=r['convergence']; print('convergence', {k: c.get(k) for k in ('std_rel_pct','drift_pct','flags')})"; ./venv/bin/python fill_coeff_row.py runs_v4/$tag/$name 2>&1 | sed "s/^/  sheet: /"; }
done
echo "$(date +%H:%M:%S) Q16 DONE"
