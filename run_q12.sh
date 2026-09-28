#!/bin/zsh
# exhaustive local sweep, take 2: all deflections on the CURRENT (Sep-5) CAD export. Waits for the old-CAD d00 M0.3 diagnostic runner (pid 32112),
# parks the Sep-4 d00 case + mesh, then: d00 (fresh export + mesh), d10 cad2, 6, 12, 3, 9, 15, -6. Same numerics as q10.
cd /Users/trasomi/dev/cfd
setopt NO_BG_NICE
while kill -0 32112 2>/dev/null; do sleep 60; done
[ -d runs_v4/d00/M0.30_filled_fine_opensides ] && [ ! -d runs_v4/d00/M0.30_filled_fine_opensides_sep4cad ] && mv runs_v4/d00/M0.30_filled_fine_opensides runs_v4/d00/M0.30_filled_fine_opensides_sep4cad
[ -d runs_v4/d00/mesh_filled_fine ] && [ ! -d runs_v4/d00/mesh_filled_fine_sep4cad ] && mv runs_v4/d00/mesh_filled_fine runs_v4/d00/mesh_filled_fine_sep4cad
echo "$(date +%H:%M:%S) old-CAD d00 case/mesh parked as *_sep4cad; models_v4/d00 must be the Sep-5 export (tab 1090 tris)"
COMMON="--start ramp --ramp-iters 300 --relax p=0.3,rho=0.05,U=0.7,h=0.7,k=0.7,omega=0.7 --pmin 20000 --pmax 300000 --open-sides --levels 5,6,6 --slot-level 6 --endtime 2000 --avg-window 500"
run_defl() { d=$1; mesh=$2; suffix=$3
  tag=$(./venv/bin/python -c "print('dm%02d' % abs($d) if $d < 0 else 'd%02d' % $d)")
  for m in 0.3 0.5 0.6 0.7 0.8 0.85 0.9; do
    name=$(printf "M%.2f_filled_fine_%s" $m $suffix)
    if [ -f runs_v4/$tag/$name/result.json ]; then echo "$(date +%H:%M:%S) skip $tag $name (done)"; continue; fi
    echo "$(date +%H:%M:%S) start $tag $name"
    ./venv/bin/python -u run_simscale_match.py ${=COMMON} --mesh-name $mesh --deflection=$d --mach $m --case $name > run_${tag}_$name.log 2>&1; rc=$?
    echo "$(date +%H:%M:%S) done $tag $name rc=$rc: $(grep -E 'stop=' run_${tag}_$name.log | tail -1 | cut -c1-160) | $(grep -E '"Mroll"' run_${tag}_$name.log | head -1 | tr -d ' ')"
    [ -f runs_v4/$tag/$name/result.json ] && ./venv/bin/python fill_coeff_row.py runs_v4/$tag/$name 2>&1 | sed "s/^/  sheet: /"
  done; }
run_defl 0 mesh_filled_fine opensides
run_defl 10 mesh_filled_fine_cad2 cad2
for d in 6 12 3 9 15 -6; do run_defl $d mesh_filled_fine opensides; done
echo "$(date +%H:%M:%S) Q12 DONE"
