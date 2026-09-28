#!/bin/zsh
# Waits for the q18 subset+grid-check queue to exit, restores np=10, then runs the full sealed-CAD local sweep (run_q19.sh).
cd /Users/trasomi/dev/cfd
setopt NO_BG_NICE
while kill -0 $(cat run_q18.pid) 2>/dev/null; do sleep 300; done
echo "$(date +%H:%M:%S) q18 finished; restoring np=10 and starting q19"
sed -i '' 's/"np": 8,/"np": 10,/' /Users/trasomi/.claude/skills/cfd-sweep/scripts/sweep_config.json
SHEET_EXISTING=1 ./run_q19.sh
