#!/bin/zsh
# 2026-09-13 21:30, replaces run_q21.sh (killed): waits for the running d15 M0.90 transient (pid 22432), then renders its video and
# fills the sheet, then the 15 deg / M1.2 STEADY as a restart from the converged M0.90 field (M0.9 -> M1.2 iteration ramp; transonic +
# consistent SIMPLEC first, plain SIMPLE fallback) + still, then the -6 / 12 deg M0.90 transients, and LAST the M1.2 TRANSIENT (+anim) + video (user request 22:30).
cd /Users/trasomi/dev/cfd
setopt NO_BG_NICE
TP=22432
while kill -0 $TP 2>/dev/null; do sleep 120; done
echo "$(date +%H:%M:%S) d15 M0.90 transient process ended"
T=runs_v4/d15/M0.90_sealedcad_fine_transient/result.json
if [ -f $T ]; then
  ./venv/bin/python -c "
import json; r=json.load(open('$T')); c=r['convergence']; print('d15 M0.90 transient Mroll %.4f' % r['moments_Nm']['Mroll'], {k: round(c[k],3) for k in ('std_rel_pct','drift_pct')}, 'quarters', [round(q,4) for q in r.get('quarter_means',[])])"
  ./venv/bin/python fill_coeff_row_sealed.py runs_v4/d15/M0.90_sealedcad_fine_transient 2>&1 | sed "s/^/  sheet: /"
  echo "$(date +%H:%M:%S) rendering d15 M0.90 video"; ./venv/bin/python anim_render.py runs_v4/d15/M0.90_sealedcad_fine_transient > anim_d15_M0.90.log 2>&1; tail -n 1 anim_d15_M0.90.log; cp runs_v4/d15/M0.90_sealedcad_fine_transient/anim/*.mp4 results/anim/ 2>/dev/null
else echo "$(date +%H:%M:%S) no d15 M0.90 transient result"; fi
S12=runs_v4/d15/M1.20_sealedcad_fine_restart
ok_steady() { ./venv/bin/python -c "import json,sys; sys.exit(0 if json.load(open('$1/result.json'))['stop_reason']=='endTime' else 1)" 2>/dev/null; }
TRANS=""
echo "$(date +%H:%M:%S) start d15 M1.20 steady restart from M0.90 (transonic + consistent, tutorial relaxation)"
./venv/bin/python -u run_local_steady_restart.py M0.90_sealedcad_fine_opensides M1.20_sealedcad_fine_restart --tag d15 --deflection 15 --mach 1.2 --transonic --consistent --relax p=1,U=0.9,h=0.8,k=0.9,omega=0.9 > run_d15_M1.20_restart_transonic.log 2>&1
echo "$(date +%H:%M:%S) done rc=$?: $(grep -E 'stop_reason|\"Mroll\"' run_d15_M1.20_restart_transonic.log | tr -d ' \n' | cut -c1-160)"
if [ -f $S12/result.json ] && ok_steady $S12; then TRANS="--transonic"
else
  echo "$(date +%H:%M:%S) transonic restart failed -> plain SIMPLE restart (sweep relaxation)"
  ./venv/bin/python -u run_local_steady_restart.py M0.90_sealedcad_fine_opensides M1.20_sealedcad_fine_restart --tag d15 --deflection 15 --mach 1.2 --relax p=0.3,U=0.7,h=0.7,k=0.7,omega=0.7 > run_d15_M1.20_restart_plain.log 2>&1
  echo "$(date +%H:%M:%S) done rc=$?: $(grep -E 'stop_reason|\"Mroll\"' run_d15_M1.20_restart_plain.log | tr -d ' \n' | cut -c1-160)"
fi
if [ -f $S12/result.json ] && ok_steady $S12; then ./anim_still.sh $S12 2>&1 | tail -n 2; else echo "$(date +%H:%M:%S) no usable M1.2 steady"; fi
run_transient() { tag=$1; d=$2
  R=runs_v4/$tag/M0.90_sealedcad_fine_opensides/result.json; [ -f $R ] || return
  [ -f runs_v4/$tag/M0.90_sealedcad_fine_transient/result.json ] && { echo "$(date +%H:%M:%S) $tag M0.90 transient exists"; return; }
  drift=$(./venv/bin/python -c "import json; print(json.load(open('$R'))['convergence']['drift_pct'])")
  if ./venv/bin/python -c "import sys; sys.exit(0 if float('$drift') > 3 else 1)"; then
    echo "$(date +%H:%M:%S) $tag M0.90 drift ${drift}% -> transient restart (15 ms)"
    ./venv/bin/python -u run_local_transient.py M0.90_sealedcad_fine_opensides M0.90_sealedcad_fine_transient --tag $tag --deflection $d --endtime 0.015 > run_${tag}_M0.90_sealedcad_fine_transient.log 2>&1
    echo "$(date +%H:%M:%S) done rc=$?: $(grep -E '\"Mroll\"' run_${tag}_M0.90_sealedcad_fine_transient.log | head -1 | tr -d ' ')"
    [ -f runs_v4/$tag/M0.90_sealedcad_fine_transient/result.json ] && ./venv/bin/python fill_coeff_row_sealed.py runs_v4/$tag/M0.90_sealedcad_fine_transient 2>&1 | sed "s/^/  sheet: /"
  else echo "$(date +%H:%M:%S) $tag M0.90 drift ${drift}% -> steady value kept"; fi
}
run_transient dm06 -6
run_transient d12 12
# user (2026-09-13 22:30): the M1.2 transient goes LAST
if [ -f $S12/result.json ] && ok_steady $S12; then
  echo "$(date +%H:%M:%S) start d15 M1.20 transient (10 ms, dt 3e-6, ${TRANS:-transonic no}, animation output)"
  ./venv/bin/python -u run_local_transient.py M1.20_sealedcad_fine_restart M1.20_sealedcad_fine_transient --tag d15 --deflection 15 --endtime 0.010 --dt 3e-6 --anim $TRANS > run_d15_M1.20_sealedcad_fine_transient.log 2>&1
  echo "$(date +%H:%M:%S) done rc=$?: $(grep -E '\"Mroll\"' run_d15_M1.20_sealedcad_fine_transient.log | head -1 | tr -d ' ')"
  [ -f runs_v4/d15/M1.20_sealedcad_fine_transient/result.json ] && { echo "$(date +%H:%M:%S) rendering d15 M1.20 video"; ./venv/bin/python anim_render.py runs_v4/d15/M1.20_sealedcad_fine_transient > anim_d15_M1.20.log 2>&1; tail -n 1 anim_d15_M1.20.log; cp runs_v4/d15/M1.20_sealedcad_fine_transient/anim/*.mp4 results/anim/ 2>/dev/null; }
else echo "$(date +%H:%M:%S) no usable M1.2 steady -> M1.2 transient skipped"; fi
echo "$(date +%H:%M:%S) Q22 DONE"
