#!/bin/zsh
# exhaustive local sweep: deflection x Mach, fine mesh per deflection, validated 2nd-order steady settings; waits for the M0.95 transient queue (q9)
cd /Users/trasomi/dev/cfd
setopt NO_BG_NICE
P=$(awk '{print $NF}' run_q9.pid); while kill -0 $P 2>/dev/null; do sleep 120; done
COMMON="--start ramp --ramp-iters 300 --relax p=0.3,rho=0.05,U=0.7,h=0.7,k=0.7,omega=0.7 --pmin 20000 --pmax 300000 --open-sides --levels 5,6,6 --slot-level 6 --endtime 2000 --avg-window 500"
run_defl() { d=$1; mesh=$2; suffix=$3
  tag=$(./venv/bin/python -c "print('dm%02d' % abs($d) if $d < 0 else 'd%02d' % $d)")
  for m in 0.3 0.5 0.6 0.7 0.8 0.85 0.9; do
    name=$(printf "M%.2f_filled_fine_%s" $m $suffix)
    if [ -f runs_v4/$tag/$name/result.json ]; then echo "$(date +%H:%M:%S) skip $tag $name (done)"; continue; fi
    echo "$(date +%H:%M:%S) start $tag $name"
    ./venv/bin/python -u run_simscale_match.py ${=COMMON} --mesh-name $mesh --deflection=$d --mach $m --case $name > run_${tag}_$name.log 2>&1; rc=$?
    echo "$(date +%H:%M:%S) done $tag $name rc=$rc: $(grep -E 'stop=' run_${tag}_$name.log | tail -1 | cut -c1-160) | $(grep -E '"Mroll"' run_${tag}_$name.log | head -1 | tr -d ' ')"
    [ -f runs_v4/$tag/$name/result.json ] && ./venv/bin/python fill_coeff_row.py runs_v4/$tag/$name 2>&1 | sed "s/^/  sheet: /"
  done; }
for d in 0 6 12 3 9 15 -6; do run_defl $d mesh_filled_fine opensides; done
run_defl 10 mesh_filled_fine_cad2 cad2      # 10 deg on the current CAD export (Sep-4 export kept as models_v4/d10_sep4cad; reference runs untouched)
echo "$(date +%H:%M:%S) Q10 DONE"
