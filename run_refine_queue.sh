#!/bin/zsh
cd /Users/trasomi/dev/cfd
setopt NO_BG_NICE
COMMON="--start ramp --ramp-iters 300 --relax p=0.3,rho=0.05,U=0.7,h=0.7,k=0.7,omega=0.7 --pmin 1 --pmax 1e8 --open-sides"
run() { name=$1; shift; echo "$(date +%H:%M:%S) start $name"; ./venv/bin/python -u run_simscale_match.py ${=COMMON} "$@" --case $name > run_$name.log 2>&1; echo "$(date +%H:%M:%S) done $name: $(grep -E 'stop=' run_$name.log | tail -1) $(grep -E 'mesh_.* OK' run_$name.log | cut -c1-120)"; }
run M0.90_sealedfine_opensides --mach 0.9 --levels 5,6,6 --slot-level 6 --mesh-name mesh_sealed_fine
run M0.60_sealedfine_opensides --mach 0.6 --levels 5,6,6 --slot-level 6 --mesh-name mesh_sealed_fine
run M0.60_gap8_opensides      --mach 0.6 --mesh-name mesh_simscale
run M0.60_gap9_opensides      --mach 0.6 --slot-level 9 --mesh-name mesh_gap9
echo "REFINE QUEUE DONE"
