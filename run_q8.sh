#!/bin/zsh
# after queue 7: local solver on SimScale mesh v3 with unlimited leastSquares gradients for all fields (SimScale LEASTSQUARES candidate)
cd /Users/trasomi/dev/cfd
setopt NO_BG_NICE
P=$(awk '{print $NF}' run_q7.pid); while kill -0 $P 2>/dev/null; do sleep 120; done
echo "$(date +%H:%M:%S) start local-on-SimScale-mesh --ls-grad"
./venv/bin/python -u run_local_on_simscale_mesh.py --ls-grad > run_M0.90_simscale_v3mesh_local_ls.log 2>&1
echo "$(date +%H:%M:%S) done rc=$?: $(grep -E 'solver rc' run_M0.90_simscale_v3mesh_local_ls.log | tail -1) | $(grep -E '"Mroll"' run_M0.90_simscale_v3mesh_local_ls.log | head -1 | tr -d ' ')"
echo "$(date +%H:%M:%S) Q8 DONE"
