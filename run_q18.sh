#!/bin/zsh
# Sealed-CAD subset (2026-09-11): baselines on the sweep mesh (levels 5/6/6, slot 6, 21x21x112) then the background-refined grid check.
cd /Users/trasomi/dev/cfd
setopt NO_BG_NICE
COMMON="--start ramp --ramp-iters 300 --relax p=0.3,rho=0.05,U=0.7,h=0.7,k=0.7,omega=0.7 --pmin 20000 --pmax 300000 --open-sides --levels 5,6,6 --slot-level 6 --endtime 2000 --avg-window 500"
run_case() { d=$1; m=$2
  tag=$(./venv/bin/python -c "print('dm%02d' % abs($d) if $d < 0 else 'd%02d' % $d)")
  name=$(printf "M%.2f_sealedcad_fine_opensides" $m)
  if [ -f runs_v4/$tag/$name/result.json ]; then echo "$(date +%H:%M:%S) skip $tag $name (done)"; return; fi
  echo "$(date +%H:%M:%S) start $tag $name"
  ./venv/bin/python -u run_simscale_match.py ${=COMMON} --mesh-name mesh_sealedcad_fine --deflection=$d --mach $m --case $name > run_${tag}_$name.log 2>&1; rc=$?
  echo "$(date +%H:%M:%S) done $tag $name rc=$rc: $(grep -E 'stop=' run_${tag}_$name.log | tail -1 | cut -c1-160) | $(grep -E '"Mroll"' run_${tag}_$name.log | head -1 | tr -d ' ')"
}
run_case 3 0.3; run_case 15 0.85; run_case 10 0.6
echo "$(date +%H:%M:%S) baselines done; starting the r30 grid check"
NPROC=$(./venv/bin/python -c "import json;print(json.load(open('/Users/trasomi/.claude/skills/cfd-sweep/scripts/sweep_config.json'))['np'])") JOBS=d03:0.3,d15:0.85,d10:0.6 RES=30,30,160 RES_TAG=r30 ./venv/bin/python -u results/mesh_independence_sealed_20260911/local_study.py > results/mesh_independence_sealed_20260911/local_r30.log 2>&1; echo "$(date +%H:%M:%S) grid check rc=$?"
echo "$(date +%H:%M:%S) Q18 DONE"
