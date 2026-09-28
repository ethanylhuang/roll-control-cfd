#!/bin/zsh
# run the remaining single-variable probes one after another, after probe 1 ends
cd /Users/trasomi/dev/cfd
setopt NO_BG_NICE
while kill -0 $(cat probe.pid) 2>/dev/null; do sleep 20; done
for n in relax laplacian energy bounds nonorth; do
  echo "$(date +%H:%M:%S) start probe $n"
  caffeinate -is ./venv/bin/python -u probe_numerics.py $n > probe_$n.log 2>&1
  echo "$(date +%H:%M:%S) done probe $n: $(grep VERDICT probe_$n.log)"
done
echo "QUEUE DONE"
