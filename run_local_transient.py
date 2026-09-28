"""run_local_transient.py <steady_case_name> <new_case_name> [--endtime 0.010] [--dt 4e-6] [--build-only]
Second-order TRANSIENT (rhoPimpleFoam, Euler, PIMPLE 2x2) restarted from a converged steady case's last time directory,
constant 305 m/s inlet (no ramp), local schemes otherwise unchanged. Output: result.json with the mean over the last 25 % of time."""
import argparse, json, os, re, shutil, subprocess, sys, time
ROOT = os.path.dirname(os.path.abspath(__file__)); SKILL = os.path.expanduser("~/.claude/skills/cfd-sweep/scripts")
sys.path.insert(0, SKILL); sys.path.insert(0, os.path.join(ROOT, "pipeline"))
import foamutil
ap = argparse.ArgumentParser(); ap.add_argument("steady"); ap.add_argument("case"); ap.add_argument("--endtime", type=float, default=0.010); ap.add_argument("--dt", type=float, default=4e-6)
ap.add_argument("--tag", default="d10", help="deflection directory under runs_v4"); ap.add_argument("--deflection", type=float, default=10.0); ap.add_argument("--second-order", action="store_true", help="force linearUpwindV momentum convection (use when the steady source case was first-order upwind)"); ap.add_argument("--build-only", action="store_true"); ap.add_argument("--np", type=int, default=10); ap.add_argument("--pmin", type=float, default=5000); ap.add_argument("--pmax", type=float, default=500000); ap.add_argument("--anim", action="store_true", help="write cutting-plane/isosurface VTK animation output (pipeline/animFO)"); ap.add_argument("--transonic", action="store_true", help="PIMPLE transonic yes (compressibility term in the pressure equation; use for M > 1)")
a = ap.parse_args(); D10 = os.path.join(ROOT, "runs_v4", a.tag); src = os.path.join(D10, a.steady); case = os.path.join(D10, a.case)
def log(m): print(time.strftime("%H:%M:%S"), m, flush=True)
times = sorted([t for t in os.listdir(src) if re.match(r"^\d+$", t) and t != "0"], key=int); last = times[-1]
srcres = json.load(open(os.path.join(src, "result.json"))); V = srcres["V_mps"]; mach = srcres["mach"]
if os.path.exists(case): shutil.rmtree(case)
os.makedirs(os.path.join(case, "constant"))
shutil.copytree(os.path.join(src, "system"), os.path.join(case, "system")); shutil.copytree(os.path.join(src, last), os.path.join(case, "0"))
for f in os.listdir(os.path.join(src, "constant")):
    s = os.path.join(src, "constant", f)
    if f == "polyMesh": os.symlink(os.readlink(s), os.path.join(case, "constant", f))
    elif os.path.isfile(s): shutil.copy(s, os.path.join(case, "constant", f))
shutil.rmtree(os.path.join(case, "0", "uniform"), ignore_errors=True)
log(f"case {a.case}: restart from {a.steady}/{last} (M{mach}, V={V}), rhoPimpleFoam Euler dt {a.dt:g} endTime {a.endtime:g}")
# constant inlet velocity instead of the iteration-ramp table
rc, out = foamutil.foam_run(case, f"foamDictionary 0/U -entry boundaryField.inlet -set '{{type fixedValue; value uniform (0 0 -{V:g});}}'", "foamDictionary_U", check=False, timeout=600)
assert rc == 0, out[-800:]
# controlDict
cd = os.path.join(case, "system", "controlDict"); t = open(cd).read()
t = re.sub(r"^application\s+\S+;", "application     rhoPimpleFoam;", t, flags=re.M)
t = re.sub(r"^startFrom\s+\S+;", "startFrom       startTime;", t, flags=re.M); t = re.sub(r"^startTime\s+\S+;", "startTime       0;", t, flags=re.M)
t = re.sub(r"^endTime\s+[^;]+;", f"endTime         {a.endtime:g};", t, flags=re.M); t = re.sub(r"^deltaT\s+\S+;", f"deltaT          {a.dt:g};", t, flags=re.M)
t = re.sub(r"^writeInterval\s+\S+;", "writeInterval   500;", t, flags=re.M)
if "adjustTimeStep" not in t: t = t.replace("writeControl", "adjustTimeStep  no;\nwriteControl", 1)
if a.anim:
    shutil.copy(os.path.join(ROOT, "pipeline", "animFO"), os.path.join(case, "system", "animFO"))
    t2 = re.sub(r"(#includeFunc\s+solverInfo[^\n]*\n)", r'\1    #include "animFO"\n', t, count=1)   # after MachNo so Ma is current when the planes are sampled
    if t2 == t: t2 = re.sub(r"(functions\s*\{\s*\n)", r'\1    #include "animFO"\n', t, count=1)
    assert t2 != t, "functions block not found"; t = re.sub(r"^\s*#includeFunc\s+MachNo\s*\n", "", t2, flags=re.M); log("animation output enabled (system/animFO; MachNo replaced by MachNoAnim every 25 steps)")
open(cd, "w").write(t)
# fvSchemes: Euler time derivative
fs = os.path.join(case, "system", "fvSchemes"); t = open(fs).read(); t = re.sub(r"(ddtSchemes\s*\{\s*\n\s*default\s+)steadyState;", r"\1Euler;", t); open(fs, "w").write(t)
if a.second_order:
    t = open(fs).read(); t2 = re.sub(r"div\(phi,U\)\s+bounded Gauss upwind;", "div(phi,U)      Gauss linearUpwindV grad(U);", t); assert t2 != t or "linearUpwindV" in t, "div(phi,U) upwind line not found"; open(fs, "w").write(t2); print("fvSchemes: div(phi,U) -> Gauss linearUpwindV grad(U) (second order)")
# fvSolution: PIMPLE, Final solvers, Final relaxation 1
fv = os.path.join(case, "system", "fvSolution"); t = open(fv).read()
t = re.sub(r"SIMPLE\s*\{.*?\n\}", f"PIMPLE\n{{\n    momentumPredictor   yes;\n    transonic           {'yes' if a.transonic else 'no'};\n    nOuterCorrectors    2;\n    nCorrectors         2;\n    nNonOrthogonalCorrectors 1;\n    pMin            {a.pmin:g};\n    pMax            {a.pmax:g};\n}}", t, count=1, flags=re.S)
finals = '    "rho.*"\n    {\n        solver          diagonal;\n    }\n    pFinal\n    {\n        $p;\n        relTol          0;\n    }\n    "(U|k|omega)Final"\n    {\n        $U;\n        relTol          0;\n    }\n    "(e|h)Final"\n    {\n        $h;\n        relTol          0;\n    }\n'
m = re.search(r"solvers\s*\{", t); depth = 0; i = m.end() - 1
for j in range(i, len(t)):
    if t[j] == "{": depth += 1
    elif t[j] == "}":
        depth -= 1
        if depth == 0: break
t = t[:j] + finals + t[j:]   # Final entries appended at the END of the solvers block (macros need p/U/h defined first)
# the "(U|k|omega)" and "(e|h)" macro names: define aliases U and h if they only exist as regex groups
if not re.search(r"\n\s{4}U\s*\n", t): t = t.replace('    "(U|k|omega)"\n', '    U\n    {\n        solver          PBiCGStab;\n        preconditioner  DILU;\n        tolerance       1e-8;\n        relTol          0.01;\n    }\n    "(k|omega)"\n', 1)
if not re.search(r"\n\s{4}h\s*\n", t): t = t.replace('    "(e|h)"\n', '    h\n    {\n        solver          smoothSolver;\n        smoother        GaussSeidel;\n        nSweeps         1;\n        tolerance       1e-7;\n        relTol          0.01;\n    }\n    e\n', 1)
t = re.sub(r"(relaxationFactors\s*\{\s*\n\s*fields\s*\{)", r'\1\n        ".*Final"       1;', t, count=1); t = re.sub(r"(equations\s*\{)", r'\1\n        ".*Final"       1;', t, count=1)
open(fv, "w").write(t)
fl = os.path.join(case, "system", "flowSettings"); t = open(fl).read(); t = re.sub(r"^endTime\s+\S+;", f"endTime     {a.endtime:g};", t, flags=re.M); open(fl, "w").write(t)
if a.build_only: log("build-only done"); sys.exit(0)
rc, out = foamutil.foam_run(case, "decomposePar -force", "decomposePar", check=False, timeout=3600); log(f"decomposePar rc={rc}")
if rc: print(out[-1500:]); sys.exit("decomposePar failed")
t0 = time.time(); rc, out = foamutil.foam_run(case, f"mpirun -np {a.np} rhoPimpleFoam -parallel 2>&1 | tee log.rhoPimpleFoam.live", "rhoPimpleFoam", check=False, timeout=14 * 3600)
lastt = foamutil.last_iteration(out); fatal = ("FOAM FATAL" in out) or ("sigFpe" in out); log(f"solver rc={rc} last t={lastt} fatal={fatal} wall={time.time()-t0:.0f}s")
import numpy as np
hdr, data = foamutil.parse_dat(foamutil.find_fo_file(case, "forces_all", "moment.dat")); hf, fdata = foamutil.parse_dat(foamutil.find_fo_file(case, "forces_all", "force.dat"))
tcol = data[:, 0]; roll = -data[:, hdr.index("total_z")]; yaw = data[:, hdr.index("total_x")]; pitch = data[:, hdr.index("total_y")]; fy = fdata[:, hf.index("total_y")]; fz = fdata[:, hf.index("total_z")]; fx = fdata[:, hf.index("total_x")]
win = tcol >= tcol[-1] - 0.25 * (tcol[-1] - tcol[0]); w = roll[win]
res = dict(deflection=a.deflection, mach=mach, V_mps=V, solver=f"rhoPimpleFoam Euler PIMPLE 2x2 transonic {'yes' if a.transonic else 'no'}", restart_from=f"{a.steady}/{last}", dt=a.dt, endtime=a.endtime, t_last=float(tcol[-1]), pMin=a.pmin, pMax=a.pmax, mesh_name=srcres.get("mesh_name"), stop_reason=("diverged" if fatal else "endTime"),
           window=dict(t_start=float(tcol[win][0]), t_end=float(tcol[-1]), n=int(win.sum())), moments_Nm=dict(Mroll=float(w.mean()), Myaw=float(yaw[win].mean()), Mpitch=float(pitch[win].mean())), forces_N=dict(Fx=float(fx[win].mean()), Fy=float(fy[win].mean()), Fz=float(fz[win].mean())),
           convergence=dict(std_rel_pct=float(100 * w.std() / abs(w.mean())), drift_pct=float(100 * abs(np.polyfit(tcol[win], w, 1)[0] * (tcol[-1] - tcol[win][0])) / abs(w.mean())), roll_min=float(w.min()), roll_max=float(w.max())),
           quarter_means=[float(roll[win][i * len(w) // 4:(i + 1) * len(w) // 4].mean()) for i in range(4)])
json.dump(res, open(os.path.join(case, "result.json"), "w"), indent=2); print(json.dumps({k: res[k] for k in ("stop_reason", "t_last", "window", "moments_Nm", "forces_N", "convergence", "quarter_means")}, indent=1))
