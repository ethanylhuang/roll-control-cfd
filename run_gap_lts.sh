#!/bin/zsh
cd /Users/trasomi/dev/cfd
setopt NO_BG_NICE
./venv/bin/python - <<'PY'
import sys, os
sys.path.insert(0, "pipeline"); import foamutil
case = os.path.abspath("runs_v4/d10/M0.90_gap_LTS")
print("[lts] rhoPimpleFoam localEuler transonic from 500 ...", flush=True)
rc, log = foamutil.foam_run(case, "mpirun -np 10 rhoPimpleFoam -parallel 2>&1 | tee log.rhoPimpleFoam.live", "rhoPimpleFoam", check=False, timeout=12*3600)
print(f"[lts] rc={rc} last={foamutil.last_iteration(log)}", flush=True)
PY
