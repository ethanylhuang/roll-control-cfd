#!/bin/zsh
# After the sealed sweep (q19): time-accurate transient restarts (15 ms, dt 4e-6, 2nd order) for the transonic points whose steady
# window drifts > 3 % (15 deg / M0.90 for sure; -6 deg / M0.90 if flagged). Result overwrites the steady row on the sheet.
cd /Users/trasomi/dev/cfd
setopt NO_BG_NICE
while kill -0 $(cat run_q19.pid) 2>/dev/null; do sleep 300; done
echo "$(date +%H:%M:%S) q19 finished; checking M0.90 drift"
for spec in "d15:15" "dm06:-6" "d12:12"; do tag=${spec%%:*}; d=${spec#*:}
  R=runs_v4/$tag/M0.90_sealedcad_fine_opensides/result.json; [ -f $R ] || continue
  drift=$(./venv/bin/python -c "import json; print(json.load(open('$R'))['convergence']['drift_pct'])")
  if ./venv/bin/python -c "import sys; sys.exit(0 if float('$drift') > 3 else 1)"; then
    echo "$(date +%H:%M:%S) $tag M0.90 drift ${drift}% -> transient restart"
    ./venv/bin/python -u run_local_transient.py M0.90_sealedcad_fine_opensides M0.90_sealedcad_fine_transient --tag $tag --deflection $d --endtime 0.015 --anim > run_${tag}_M0.90_sealedcad_fine_transient.log 2>&1
    echo "$(date +%H:%M:%S) done rc=$?: $(grep -E '\"Mroll\"' run_${tag}_M0.90_sealedcad_fine_transient.log | head -1 | tr -d ' ')"
    T=runs_v4/$tag/M0.90_sealedcad_fine_transient/result.json
    [ -f $T ] && ./venv/bin/python -c "
import json; r=json.load(open('$T')); c=r['convergence']; print('transient convergence', {k: round(c[k],3) for k in ('std_rel_pct','drift_pct')}, 'quarters', [round(q,4) for q in r.get('quarter_means',[])])" && ./venv/bin/python fill_coeff_row_sealed.py runs_v4/$tag/M0.90_sealedcad_fine_transient 2>&1 | sed "s/^/  sheet: /"
  else echo "$(date +%H:%M:%S) $tag M0.90 drift ${drift}% -> steady value kept"; fi
done
echo "$(date +%H:%M:%S) Q20 DONE"
