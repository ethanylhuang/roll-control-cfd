#!/bin/zsh
# after the local-on-SimScale-mesh run: repeat it with the pressure floor at 5 kPa (the floor was active every iteration at 20 kPa)
cd /Users/trasomi/dev/cfd
setopt NO_BG_NICE
P=$(awk '{print $NF}' run_simscale_v3mesh_local.pid); while kill -0 $P 2>/dev/null; do sleep 120; done
echo "$(date +%H:%M:%S) start M0.90_simscale_v3mesh_local_pmin5k"
./venv/bin/python -u run_local_on_simscale_mesh.py --pmin 5000 > run_M0.90_simscale_v3mesh_local_pmin5k.log 2>&1
echo "$(date +%H:%M:%S) done rc=$?: $(grep -E 'solver rc' run_M0.90_simscale_v3mesh_local_pmin5k.log | tail -1) | $(grep -E '"Mroll"' run_M0.90_simscale_v3mesh_local_pmin5k.log | head -1 | tr -d ' ')"
echo "$(date +%H:%M:%S) Q5 DONE"
