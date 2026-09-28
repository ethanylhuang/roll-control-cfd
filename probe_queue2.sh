#!/bin/zsh
cd /Users/trasomi/dev/cfd
setopt NO_BG_NICE
for n in rho prelax eqrelax; do
  echo "$(date +%H:%M:%S) start probe $n"
  caffeinate -is ./venv/bin/python -u probe_numerics.py $n > probe_$n.log 2>&1
  echo "$(date +%H:%M:%S) done probe $n: $(grep VERDICT probe_$n.log)"
done
echo "QUEUE DONE"
