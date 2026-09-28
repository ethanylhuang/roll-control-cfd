#!/bin/zsh
# Sealed-CAD full local sweep (2026-09-11): 8 deflections x 7 Machs on mesh_sealedcad_fine (levels 5/6/6, slot 6, 21x21x112, ~1.5 M cells).
# Cases already produced by the q18 subset (3/M0.3, 15/M0.85, 10/M0.6) are reused. Each result -> sheet tab 'v5 sealed coeff sweep'.
cd /Users/trasomi/dev/cfd
setopt NO_BG_NICE
COMMON="--start ramp --ramp-iters 300 --relax p=0.3,rho=0.05,U=0.7,h=0.7,k=0.7,omega=0.7 --pmin 20000 --pmax 300000 --open-sides --levels 5,6,6 --slot-level 6 --endtime 2000 --avg-window 500"
run_defl() { d=$1
  tag=$(./venv/bin/python -c "print('dm%02d' % abs($d) if $d < 0 else 'd%02d' % $d)")
  for m in 0.3 0.5 0.6 0.7 0.8 0.85 0.9; do
    name=$(printf "M%.2f_sealedcad_fine_opensides" $m)
    if [ -f runs_v4/$tag/$name/result.json ]; then echo "$(date +%H:%M:%S) skip $tag $name (done)"; [ "$SHEET_EXISTING" = "1" ] && ./venv/bin/python fill_coeff_row_sealed.py runs_v4/$tag/$name 2>&1 | sed "s/^/  sheet: /"; continue; fi
    echo "$(date +%H:%M:%S) start $tag $name"
    ./venv/bin/python -u run_simscale_match.py ${=COMMON} --mesh-name mesh_sealedcad_fine --deflection=$d --mach $m --case $name > run_${tag}_$name.log 2>&1; rc=$?
    echo "$(date +%H:%M:%S) done $tag $name rc=$rc: $(grep -E 'stop=' run_${tag}_$name.log | tail -1 | cut -c1-160) | $(grep -E '"Mroll"' run_${tag}_$name.log | head -1 | tr -d ' ')"
    [ -f runs_v4/$tag/$name/result.json ] && ./venv/bin/python fill_coeff_row_sealed.py runs_v4/$tag/$name 2>&1 | sed "s/^/  sheet: /"
  done; }
for d in 0 3 6 9 10 12 15 -6; do run_defl $d; done
echo "$(date +%H:%M:%S) Q19 DONE"
