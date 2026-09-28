#!/bin/zsh
# warm restart of the open-sides case from iteration 500 with the transonic pressure equation
cd /Users/trasomi/dev/cfd
setopt NO_BG_NICE
./venv/bin/python - <<'PY'
import sys, os
sys.path.insert(0, "pipeline"); import foamutil
case = os.path.abspath("runs_v4/d10/M0.90_transonic_restart")
print("[restart] rhoSimpleFoam transonic from 500 ...", flush=True)
rc, log = foamutil.foam_run(case, "mpirun -np 10 rhoSimpleFoam -parallel 2>&1 | tee log.rhoSimpleFoam.live", "rhoSimpleFoam", check=False, timeout=12*3600)
print(f"[restart] stop={foamutil.classify_stop(log, endtime=700)} iters={foamutil.last_iteration(log)}", flush=True)
PY
