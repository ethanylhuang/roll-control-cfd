#!/bin/zsh
# after q16: time-accurate transient for the limit-cycling 15-deg / M0.9 point, restarted from the 4000-iteration steady field (15 ms)
cd /Users/trasomi/dev/cfd
setopt NO_BG_NICE
P=$(awk '{print $NF}' run_q16.pid); while kill -0 $P 2>/dev/null; do sleep 300; done
echo "$(date +%H:%M:%S) start d15 M0.90_filled_fine_transient"
./venv/bin/python -u run_local_transient.py M0.90_filled_fine_opensides_long M0.90_filled_fine_transient --tag d15 --deflection 15 --endtime 0.015 > run_d15_M0.90_filled_fine_transient.log 2>&1
echo "$(date +%H:%M:%S) done rc=$?: $(grep -E 'solver rc' run_d15_M0.90_filled_fine_transient.log | tail -1) | $(grep -E '"Mroll"' run_d15_M0.90_filled_fine_transient.log | head -1 | tr -d ' ')"
R=runs_v4/d15/M0.90_filled_fine_transient/result.json
[ -f $R ] && ./venv/bin/python -c "
import json; r=json.load(open('$R')); c=r['convergence']; print('transient convergence', {k: round(c[k],3) for k in ('std_rel_pct','drift_pct')}, 'quarters', [round(q,4) for q in r['quarter_means']])"
echo "$(date +%H:%M:%S) Q17 DONE"
