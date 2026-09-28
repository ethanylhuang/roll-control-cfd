#!/bin/zsh
# after queue 5: local solver on SimScale's mesh with SimScale's BC choices, then with SimScale's scheme choices (discriminate solver-fork vs settings)
cd /Users/trasomi/dev/cfd
setopt NO_BG_NICE
P=$(awk '{print $NF}' run_q5.pid); while kill -0 $P 2>/dev/null; do sleep 120; done
for v in "--simscale-bcs" "--simscale-schemes"; do
  tag=$(echo $v | sed 's/--simscale-//'); echo "$(date +%H:%M:%S) start local-on-SimScale-mesh $v"
  ./venv/bin/python -u run_local_on_simscale_mesh.py $v > run_M0.90_simscale_v3mesh_local_$tag.log 2>&1
  echo "$(date +%H:%M:%S) done $v rc=$?: $(grep -E 'solver rc' run_M0.90_simscale_v3mesh_local_$tag.log | tail -1) | $(grep -E '"Mroll"' run_M0.90_simscale_v3mesh_local_$tag.log | head -1 | tr -d ' ')"
done
echo "$(date +%H:%M:%S) Q6 DONE"
