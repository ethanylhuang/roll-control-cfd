#!/bin/zsh
# after the grad-only run: local solver on SimScale mesh v3 with unlimited Gauss linear gradients for all fields = exact counterpart of SimScale run a231c6b2
cd /Users/trasomi/dev/cfd
setopt NO_BG_NICE
P=$(awk '{print $NF}' run_simscale_v3mesh_local_grad.pid); while kill -0 $P 2>/dev/null; do sleep 120; done
echo "$(date +%H:%M:%S) start local-on-SimScale-mesh --unlimited-grad"
./venv/bin/python -u run_local_on_simscale_mesh.py --unlimited-grad > run_M0.90_simscale_v3mesh_local_unlim.log 2>&1
echo "$(date +%H:%M:%S) done rc=$?: $(grep -E 'solver rc' run_M0.90_simscale_v3mesh_local_unlim.log | tail -1) | $(grep -E '"Mroll"' run_M0.90_simscale_v3mesh_local_unlim.log | head -1 | tr -d ' ')"
echo "$(date +%H:%M:%S) Q7 DONE"
