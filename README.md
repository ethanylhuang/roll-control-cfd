# roll-control-cfd

CFD study of a deflectable roll-control tab on a sounding rocket's fin can
(OpenFOAM `rhoSimpleFoam`/`rhoPimpleFoam` locally, plus SimScale via its API):
tab deflection (−6° … 15°) × Mach (0.3 … 1.2) sweeps, mesh-independence checks,
tab-gap leakage vs. sealed-tab comparisons, and a camera-shroud geometry variant.

## Layout
- `models_*` – STL geometry per deflection (exported from Onshape)
- `run_*.py`, `run_q*.sh` – local case setup and run queues
- `simscale_sealed/`, `run_simscale_match.py`, `run_ss_*` – SimScale API sweep tooling
- `fill_*.py` – push coefficients to the results sheet
- `results/` – force/moment coefficients, mesh-independence study, transient audit
- `pipeline/`, `anim_render.py` – transient animation pipeline
- `newgeom_cam/`, `tools/split4cam/` – camera-shroud geometry work
- `sweep-dashboard/` – web dashboard for the sweep results

Large case data (OpenFOAM fields, meshes, VTK, solver logs, archives, venvs,
node_modules) is intentionally not tracked; see `.gitignore`.
