"""run_lts_case.py <mach> <case_name> [--endtime 3000] [--avg-window 500] [--build-only]
Local pseudo-transient (rhoPimpleFoam, localEuler, transonic, maxCo 3, no relaxation) run of the 10 deg filled-gap rocket
on the grid-converged mesh (mesh_filled_fine, 5/6/6, 1.5 M cells) with open sides and the 300-step inlet ramp.
Case built from the converged steady case M0.90_filled_fine_opensides (BCs, mesh link, function objects) plus the
fvSchemes/fvSolution of M0.90_gap_LTS (the recipe that converged the choked-gap case). Writes result.json like run_simscale_match.py."""
import argparse, json, os, re, shutil, subprocess, sys, time
ROOT = os.path.dirname(os.path.abspath(__file__)); SKILL = os.path.expanduser("~/.claude/skills/cfd-sweep/scripts")
sys.path.insert(0, SKILL); sys.path.insert(0, os.path.join(ROOT, "pipeline"))
import foamutil, run_sweep as rs, report as report_mod
ap = argparse.ArgumentParser(); ap.add_argument("mach", type=float); ap.add_argument("case"); ap.add_argument("--endtime", type=int, default=3000)
ap.add_argument("--avg-window", type=int, default=500); ap.add_argument("--build-only", action="store_true"); ap.add_argument("--np", type=int, default=10); ap.add_argument("--no-transonic", action="store_true", help="PIMPLE transonic no (pseudo-time version of the steady non-transonic pressure equation)")
a = ap.parse_args()
D10 = os.path.join(ROOT, "runs_v4", "d10"); TPL = os.path.join(D10, "M0.90_filled_fine_opensides"); LTS = os.path.join(D10, "M0.90_gap_LTS")
case = os.path.join(D10, a.case); V = 305.0 if abs(a.mach - 0.9) < 1e-6 else round(a.mach * 339.1, 1)
def log(m): print(time.strftime("%H:%M:%S"), m, flush=True)
if os.path.exists(case): shutil.rmtree(case)
os.makedirs(case)
for sub in ("0", "system"): shutil.copytree(os.path.join(TPL, sub), os.path.join(case, sub))
os.makedirs(os.path.join(case, "constant"))
for f in os.listdir(os.path.join(TPL, "constant")):
    src = os.path.join(TPL, "constant", f)
    if f == "polyMesh": os.symlink(os.readlink(src), os.path.join(case, "constant", f))
    elif os.path.isfile(src): shutil.copy(src, os.path.join(case, "constant", f))
for f in ("fvSchemes", "fvSolution"): shutil.copy(os.path.join(LTS, "system", f), os.path.join(case, "system", f))
if a.no_transonic:
    fvs = os.path.join(case, "system", "fvSolution"); t = open(fvs).read(); t = re.sub(r"transonic\s+yes;", "transonic           no;", t); open(fvs, "w").write(t)
cd = os.path.join(case, "system", "controlDict"); t = open(cd).read()
t = re.sub(r"^application\s+\S+;", "application     rhoPimpleFoam;", t, flags=re.M); open(cd, "w").write(t)
fs = os.path.join(case, "system", "flowSettings"); t = open(fs).read()
t = re.sub(r"^Uinf\s+\([^)]*\);", f"Uinf        (0 0 -{V:g});", t, flags=re.M)
t = re.sub(r"^rampTable\s+.*;", f"rampTable   ((0 (0 0 -50)) (300 (0 0 -{V:g})) (1000000 (0 0 -{V:g})));", t, flags=re.M)
t = re.sub(r"^magUinf\s+\S+;", f"magUinf     {V:g};", t, flags=re.M)
t = re.sub(r"^endTime\s+\S+;", f"endTime     {a.endtime};", t, flags=re.M); open(fs, "w").write(t)
log(f"case {a.case}: M{a.mach} V={V} m/s, rhoPimpleFoam localEuler transonic={not a.no_transonic}, endTime {a.endtime}, mesh {os.readlink(os.path.join(case, 'constant', 'polyMesh'))}")
print(subprocess.run(["grep", "-E", "^(Uinf|rampTable|magUinf|endTime)", fs], capture_output=True, text=True).stdout)
if a.build_only: log("build-only: done"); sys.exit(0)
rc, out = foamutil.foam_run(case, "decomposePar -force", "decomposePar", check=False, timeout=3600); log(f"decomposePar rc={rc}")
if rc: sys.exit("decomposePar failed")
log("rhoPimpleFoam ..."); t0 = time.time()
rc, out = foamutil.foam_run(case, f"mpirun -np {a.np} rhoPimpleFoam -parallel 2>&1 | tee log.rhoPimpleFoam.live", "rhoPimpleFoam", check=False, timeout=12 * 3600)
last = foamutil.last_iteration(out); fatal = ("FOAM FATAL" in out) or ("sigFpe" in out)
stop = "diverged" if fatal else ("endTime" if (last and int(float(last)) >= a.endtime) else f"stopped@{last}")
log(f"solver rc={rc} last={last} stop={stop} wall={time.time()-t0:.0f}s")
avg_start = a.endtime - a.avg_window
res = dict(deflection=10.0, mach=a.mach, V_mps=V, stop_reason=stop, start="ramp", pMin=1000.0, pMax=1e6, relax_overrides=("LTS: localEuler, transonic NO, maxCo 3, no relaxation" if a.no_transonic else "LTS: localEuler, transonic, maxCo 3, no relaxation"), div_u="", transonic=(not a.no_transonic), consistent=False, open_sides=True, slot_level=6, mesh_name="mesh_filled_fine", setup="simscale-matched LTS", cofr_z=0.399, p_inf=97690.0, T_inf=286.2, rho_inf=1.18915, solver="rhoPimpleFoam localEuler")
try:
    mom, nm = rs.window_means(case, "forces_all", "moment.dat", avg_start, foamutil.find_fo_file, foamutil.parse_dat)
    frc, _ = rs.window_means(case, "forces_all", "force.dat", avg_start, foamutil.find_fo_file, foamutil.parse_dat)
    conv = report_mod.mroll_convergence(case, avg_start, a.endtime, 3.0, 5.0)
    res.update(n_avg_samples=nm, moments_Nm=(dict(Mroll=-mom["total_z"], Mpitch=mom["total_y"], Myaw=mom["total_x"]) if mom else None),
               forces_N=(dict(Fx=frc["total_x"], Fy=frc["total_y"], Fz=frc["total_z"]) if frc else None), convergence=conv)
except Exception as e: res.update(postprocess_error=repr(e))
json.dump(res, open(os.path.join(case, "result.json"), "w"), indent=2)
print(json.dumps({k: res.get(k) for k in ("stop_reason", "n_avg_samples", "moments_Nm", "forces_N", "convergence", "postprocess_error")}, indent=1))
