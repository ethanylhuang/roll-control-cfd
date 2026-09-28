#!/bin/zsh
# boattail variant, queued behind the corrected as-assembled run (no two 10-rank jobs at once)
cd /Users/trasomi/dev/cfd
setopt NO_BG_NICE
until grep -qE "RUN DONE|Traceback" newgeom_cam/run_m060_v2.log; do sleep 30; done
V5CAM_VARIANT=_bt ./venv/bin/python -u newgeom_cam/run_newgeom.py --start ramp --ramp-iters 300 --relax p=0.3,rho=0.05,U=0.7,h=0.7,k=0.7,omega=0.7 \
  --pmin 20000 --pmax 300000 --open-sides --levels 5,6,6 --slot-level 6 --endtime 2000 --avg-window 500 \
  --mesh-name mesh_sealedcad_fine --deflection=15 --mach 0.6 --case M0.60_sealedcad_fine_opensides
echo "RUN DONE rc=$?"
