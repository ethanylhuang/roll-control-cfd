#!/bin/zsh
cd /Users/trasomi/dev/cfd
setopt NO_BG_NICE
for m in 0.6 0.9; do
  tag=$(printf "M%.2f" $m)
  echo "$(date +%H:%M:%S) start $tag slot-level-6"
  ./venv/bin/python -u run_simscale_match.py --start ramp --ramp-iters 300 --mach $m --relax p=0.3,rho=0.05,U=0.7,h=0.7,k=0.7,omega=0.7 --pmin 1 --pmax 1e8 --open-sides --slot-level 6 --mesh-name mesh_sealed6 --case ${tag}_sealed6_opensides > run_sealed6_${tag}.log 2>&1
  echo "$(date +%H:%M:%S) done $tag: $(grep -E 'stop=' run_sealed6_${tag}.log | tail -1)"
done
echo "PAIR DONE"
