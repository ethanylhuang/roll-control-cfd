#!/bin/zsh
# after the M0.9 local transient: M0.95 local transient restarted from the converged first-order steady field (15 ms: the field must evolve to 2nd order)
cd /Users/trasomi/dev/cfd
setopt NO_BG_NICE
P=$(awk '{print $NF}' run_transient_m090.pid); while kill -0 $P 2>/dev/null; do sleep 120; done
echo "$(date +%H:%M:%S) start M0.95_filled_fine_transient"
./venv/bin/python -u run_local_transient.py M0.95_filled_fine_upwind M0.95_filled_fine_transient --endtime 0.015 > run_M0.95_filled_fine_transient.log 2>&1
echo "$(date +%H:%M:%S) done rc=$?: $(grep -E 'solver rc' run_M0.95_filled_fine_transient.log | tail -1) | $(grep -E '"Mroll"' run_M0.95_filled_fine_transient.log | head -1 | tr -d ' ')"
echo "$(date +%H:%M:%S) Q9 DONE"
