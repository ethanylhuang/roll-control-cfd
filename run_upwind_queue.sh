#!/bin/zsh
# after the LTS queue: local first-order-upwind steady run at M0.9 on the fine mesh (equal-numerics comparison with the SimScale upwind run)
cd /Users/trasomi/dev/cfd
setopt NO_BG_NICE
QP=$(awk '{print $NF}' run_lts_queue.pid)
while kill -0 $QP 2>/dev/null; do sleep 120; done
echo "$(date +%H:%M:%S) LTS queue finished; starting upwind comparison run"
name=M0.90_filled_fine_upwind
./venv/bin/python -u run_simscale_match.py --start ramp --ramp-iters 300 --relax p=0.3,rho=0.05,U=0.7,h=0.7,k=0.7,omega=0.7 --pmin 20000 --pmax 300000 --open-sides --levels 5,6,6 --slot-level 6 --mesh-name mesh_filled_fine --endtime 2000 --avg-window 500 --mach 0.9 --div-u upwind --case $name > run_$name.log 2>&1
echo "$(date +%H:%M:%S) done $name rc=$?: $(grep -E 'stop=' run_$name.log | tail -1 | cut -c1-200) | $(grep -E 'Mroll' run_$name.log | tail -1 | cut -c1-160)"
echo "$(date +%H:%M:%S) UPWIND QUEUE DONE"
