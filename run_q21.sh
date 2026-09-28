#!/bin/zsh
# After the sealed sweep (q19 DONE 20:56), in this order (2026-09-13, reordered 21:02):
#  1. 15 deg / M1.2 STEADY on the fine sealed mesh with the sweep's exact setup (+ transonic retry) + still
#  2. 15 deg / M0.90 TRANSIENT restart (15 ms, animation output) -> video
#  3. 15 deg / M1.2 TRANSIENT restart (10 ms, dt 3e-6, transonic, animation output) -> video
#  4. -6 deg (and 12 deg if drift > 3 %) M0.90 transients, no animation
cd /Users/trasomi/dev/cfd
setopt NO_BG_NICE
while kill -0 $(cat run_q19.pid) 2>/dev/null; do sleep 300; done
echo "$(date +%H:%M:%S) q19 finished"
COMMON="--start ramp --ramp-iters 300 --relax p=0.3,rho=0.05,U=0.7,h=0.7,k=0.7,omega=0.7 --pmin 20000 --pmax 300000 --open-sides --levels 5,6,6 --slot-level 6 --endtime 2000 --avg-window 500"
S12=runs_v4/d15/M1.20_sealedcad_fine_opensides
ok_steady() { ./venv/bin/python -c "import json,sys; sys.exit(0 if json.load(open('$1/result.json'))['stop_reason']=='endTime' else 1)" 2>/dev/null; }
if [ ! -f $S12/result.json ]; then
  echo "$(date +%H:%M:%S) start d15 M1.20 steady (sweep setup, fine sealed mesh)"
  ./venv/bin/python -u run_simscale_match.py ${=COMMON} --mesh-name mesh_sealedcad_fine --deflection=15 --mach 1.2 --case M1.20_sealedcad_fine_opensides > run_d15_M1.20_sealedcad_fine_opensides.log 2>&1; rc=$?
  echo "$(date +%H:%M:%S) done d15 M1.20 steady rc=$rc: $(grep -E 'stop=' run_d15_M1.20_sealedcad_fine_opensides.log | tail -1 | cut -c1-120) | $(grep -E '"Mroll"' run_d15_M1.20_sealedcad_fine_opensides.log | head -1 | tr -d ' ')"
  if [ -f $S12/result.json ] && ok_steady $S12; then ./anim_still.sh $S12 2>&1 | tail -n 2
  else
    echo "$(date +%H:%M:%S) d15 M1.20 steady did not reach endTime with the sweep setup -> retry with SIMPLE transonic yes"
    ./venv/bin/python -u run_simscale_match.py ${=COMMON} --transonic --mesh-name mesh_sealedcad_fine --deflection=15 --mach 1.2 --case M1.20_sealedcad_fine_opensides > run_d15_M1.20_sealedcad_fine_opensides_transonic.log 2>&1; rc=$?
    echo "$(date +%H:%M:%S) done d15 M1.20 steady (transonic) rc=$rc: $(grep -E 'stop=' run_d15_M1.20_sealedcad_fine_opensides_transonic.log | tail -1 | cut -c1-120) | $(grep -E '"Mroll"' run_d15_M1.20_sealedcad_fine_opensides_transonic.log | head -1 | tr -d ' ')"
    [ -f $S12/result.json ] && ./anim_still.sh $S12 2>&1 | tail -n 2
  fi
fi
run_transient() { tag=$1; d=$2; anim=$3
  R=runs_v4/$tag/M0.90_sealedcad_fine_opensides/result.json; [ -f $R ] || return
  [ -f runs_v4/$tag/M0.90_sealedcad_fine_transient/result.json ] && { echo "$(date +%H:%M:%S) $tag M0.90 transient exists"; return; }
  drift=$(./venv/bin/python -c "import json; print(json.load(open('$R'))['convergence']['drift_pct'])")
  if ./venv/bin/python -c "import sys; sys.exit(0 if float('$drift') > 3 else 1)"; then
    echo "$(date +%H:%M:%S) $tag M0.90 drift ${drift}% -> transient restart (15 ms${anim:+, animation output})"
    ./venv/bin/python -u run_local_transient.py M0.90_sealedcad_fine_opensides M0.90_sealedcad_fine_transient --tag $tag --deflection $d --endtime 0.015 $anim > run_${tag}_M0.90_sealedcad_fine_transient.log 2>&1
    echo "$(date +%H:%M:%S) done rc=$?: $(grep -E '"Mroll"' run_${tag}_M0.90_sealedcad_fine_transient.log | head -1 | tr -d ' ')"
    T=runs_v4/$tag/M0.90_sealedcad_fine_transient/result.json
    [ -f $T ] && ./venv/bin/python -c "
import json; r=json.load(open('$T')); c=r['convergence']; print('transient convergence', {k: round(c[k],3) for k in ('std_rel_pct','drift_pct')}, 'quarters', [round(q,4) for q in r.get('quarter_means',[])])" && ./venv/bin/python fill_coeff_row_sealed.py runs_v4/$tag/M0.90_sealedcad_fine_transient 2>&1 | sed "s/^/  sheet: /"
    if [ -n "$anim" ] && [ -f $T ]; then echo "$(date +%H:%M:%S) rendering $tag M0.90 video"; ./venv/bin/python anim_render.py runs_v4/$tag/M0.90_sealedcad_fine_transient > anim_${tag}_M0.90.log 2>&1; tail -n 1 anim_${tag}_M0.90.log; cp runs_v4/$tag/M0.90_sealedcad_fine_transient/anim/*.mp4 results/anim/ 2>/dev/null; fi
  else echo "$(date +%H:%M:%S) $tag M0.90 drift ${drift}% -> steady value kept"; fi
}
run_transient d15 15 --anim
if [ -f $S12/result.json ] && ok_steady $S12 && [ ! -f runs_v4/d15/M1.20_sealedcad_fine_transient/result.json ]; then
  echo "$(date +%H:%M:%S) start d15 M1.20 transient (10 ms, dt 3e-6, transonic, animation output)"
  ./venv/bin/python -u run_local_transient.py M1.20_sealedcad_fine_opensides M1.20_sealedcad_fine_transient --tag d15 --deflection 15 --endtime 0.010 --dt 3e-6 --anim --transonic > run_d15_M1.20_sealedcad_fine_transient.log 2>&1
  echo "$(date +%H:%M:%S) done rc=$?: $(grep -E '"Mroll"' run_d15_M1.20_sealedcad_fine_transient.log | head -1 | tr -d ' ')"
  echo "$(date +%H:%M:%S) rendering d15 M1.20 video"; ./venv/bin/python anim_render.py runs_v4/d15/M1.20_sealedcad_fine_transient > anim_d15_M1.20.log 2>&1; tail -n 1 anim_d15_M1.20.log; cp runs_v4/d15/M1.20_sealedcad_fine_transient/anim/*.mp4 results/anim/ 2>/dev/null
fi
run_transient dm06 -6 ""
run_transient d12 12 ""
echo "$(date +%H:%M:%S) Q21 DONE"
