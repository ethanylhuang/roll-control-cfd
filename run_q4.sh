#!/bin/zsh
# queue 4 (after queue 3): local steady 2nd-order TVD limitedLinearV 1 at M0.9 on the fine mesh = scheme-matched counterpart of the SimScale fine-v2 limitedLinearV run
cd /Users/trasomi/dev/cfd
setopt NO_BG_NICE
QP=$(awk '{print $NF}' run_q3.pid); while kill -0 $QP 2>/dev/null; do sleep 120; done
name=M0.90_filled_fine_llV; echo "$(date +%H:%M:%S) start $name"
./venv/bin/python -u run_simscale_match.py --start ramp --ramp-iters 300 --relax p=0.3,rho=0.05,U=0.7,h=0.7,k=0.7,omega=0.7 --pmin 20000 --pmax 300000 --open-sides --levels 5,6,6 --slot-level 6 --mesh-name mesh_filled_fine --endtime 2000 --avg-window 500 --mach 0.9 --div-u limitedLinearV --case $name > run_$name.log 2>&1
echo "$(date +%H:%M:%S) done $name rc=$?: $(grep -E 'stop=' run_$name.log | tail -1 | cut -c1-200) | $(grep -E '"Mroll"' run_$name.log | head -1 | tr -d ' ')"
echo "$(date +%H:%M:%S) Q4 DONE"
