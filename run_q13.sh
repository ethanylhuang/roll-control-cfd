#!/bin/zsh
# after q12: redo the M0.95 10-deg transient with SECOND-ORDER momentum (the q9 run inherited 'bounded Gauss upwind' from the first-order steady source and just sat at 0.7529)
cd /Users/trasomi/dev/cfd
setopt NO_BG_NICE
P=$(awk '{print $NF}' run_q12.pid); while kill -0 $P 2>/dev/null; do sleep 300; done
[ -d runs_v4/d10/M0.95_filled_fine_transient ] && [ ! -d runs_v4/d10/M0.95_filled_fine_transient_upwindschemes ] && mv runs_v4/d10/M0.95_filled_fine_transient runs_v4/d10/M0.95_filled_fine_transient_upwindschemes
echo "$(date +%H:%M:%S) start M0.95_filled_fine_transient (second-order momentum)"
./venv/bin/python -u run_local_transient.py M0.95_filled_fine_upwind M0.95_filled_fine_transient --second-order --endtime 0.015 > run_M0.95_filled_fine_transient2.log 2>&1
echo "$(date +%H:%M:%S) done rc=$?: $(grep -E 'solver rc' run_M0.95_filled_fine_transient2.log | tail -1) | $(grep -E '"Mroll"' run_M0.95_filled_fine_transient2.log | head -1 | tr -d ' ')"
echo "$(date +%H:%M:%S) Q13 DONE"
