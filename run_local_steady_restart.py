"""run_local_steady_restart.py <source_steady_case> <new_case> --tag d15 --deflection 15 --mach 1.2 [--ramp-iters 300] [--endtime 2000]
[--avg-window 500] [--transonic] [--consistent] [--relax p=1,U=0.9,h=0.8,k=0.9,omega=0.9] [--pmin 20000 --pmax 300000] [--np 10]
STEADY rhoSimpleFoam restarted from another steady case's last time directory (same mesh), with an iteration-ramp of the inlet
velocity from the source speed to the new Mach — a numerical continuation for reaching supersonic Mach numbers that the cold
50 m/s ramp cannot survive. Writes result.json (mean over the last --avg-window iterations, 250-iteration block scatter)."""
import argparse, json, os, re, shutil, subprocess, sys, time
ROOT = os.path.dirname(os.path.abspath(__file__)); SKILL = os.path.expanduser("~/.claude/skills/cfd-sweep/scripts"); sys.path.insert(0, SKILL); sys.path.insert(0, os.path.join(ROOT, "pipeline"))
import foamutil
ap = argparse.ArgumentParser(); ap.add_argument("steady"); ap.add_argument("case"); ap.add_argument("--tag", default="d15"); ap.add_argument("--deflection", type=float, default=15.0); ap.add_argument("--mach", type=float, required=True)
ap.add_argument("--ramp-iters", type=int, default=300); ap.add_argument("--endtime", type=int, default=2000); ap.add_argument("--avg-window", type=int, default=500); ap.add_argument("--transonic", action="store_true"); ap.add_argument("--consistent", action="store_true")
ap.add_argument("--relax", default=""); ap.add_argument("--pmin", type=float, default=20000); ap.add_argument("--pmax", type=float, default=300000); ap.add_argument("--np", type=int, default=10); ap.add_argument("--build-only", action="store_true")
a = ap.parse_args(); D = os.path.join(ROOT, "runs_v4", a.tag); src = os.path.join(D, a.steady); case = os.path.join(D, a.case)
def log(m): print(time.strftime("%H:%M:%S"), m, flush=True)
times = sorted([t for t in os.listdir(src) if re.match(r"^\d+$", t) and t != "0"], key=int); last = times[-1]
srcres = json.load(open(os.path.join(src, "result.json"))); V0 = srcres["V_mps"]; V = round(a.mach * 339.1, 1)
if os.path.exists(case): shutil.rmtree(case)
os.makedirs(os.path.join(case, "constant")); shutil.copytree(os.path.join(src, "system"), os.path.join(case, "system")); shutil.copytree(os.path.join(src, last), os.path.join(case, "0"))
for f in os.listdir(os.path.join(src, "constant")):
    s = os.path.join(src, "constant", f)
    if f == "polyMesh": os.symlink(os.readlink(s), os.path.join(case, "constant", f))
    elif os.path.isfile(s): shutil.copy(s, os.path.join(case, "constant", f))
shutil.rmtree(os.path.join(case, "0", "uniform"), ignore_errors=True)
log(f"case {a.case}: steady restart from {a.steady}/{last} (V {V0} -> {V} m/s = M{a.mach:g}) ramp {a.ramp_iters} it, endTime {a.endtime}, transonic {a.transonic} consistent {a.consistent} relax '{a.relax}'")
tbl = f"((0 (0 0 -{V0:g})) ({a.ramp_iters} (0 0 -{V:g})) (1000000 (0 0 -{V:g})))"
rc, out = foamutil.foam_run(case, f"foamDictionary 0/U -entry boundaryField.inlet -set '{{type uniformFixedValue; uniformValue table {tbl}; value uniform (0 0 -{V0:g});}}'", "foamDictionary_U", check=False, timeout=600); assert rc == 0, out[-800:]
fl = os.path.join(case, "system", "flowSettings"); t = open(fl).read()
t = re.sub(r"^Uinf\s+[^;]+;", f"Uinf        (0 0 -{V:g});", t, flags=re.M); t = re.sub(r"^Ustart\s+[^;]+;", f"Ustart      (0 0 -{V0:g});", t, flags=re.M); t = re.sub(r"^rampTable\s+[^;]+;", f"rampTable   {tbl};", t, flags=re.M)
t = re.sub(r"^magUinf\s+[^;]+;", f"magUinf     {V:g};", t, flags=re.M); t = re.sub(r"^endTime\s+[^;]+;", f"endTime     {a.endtime};", t, flags=re.M); open(fl, "w").write(t)
cd = os.path.join(case, "system", "controlDict"); t = open(cd).read()
t = re.sub(r"^startFrom\s+\S+;", "startFrom       startTime;", t, flags=re.M); t = re.sub(r"^startTime\s+\S+;", "startTime       0;", t, flags=re.M); t = re.sub(r"^endTime\s+[^;]+;", f"endTime         {a.endtime};", t, flags=re.M); open(cd, "w").write(t)
fv = os.path.join(case, "system", "fvSolution"); t = open(fv).read()
t = re.sub(r"pMin\s+[^;]+;", f"pMin            {a.pmin:g};", t, count=1); t = re.sub(r"pMax\s+[^;]+;", f"pMax            {a.pmax:g};", t, count=1)
t = re.sub(r"^\s*transonic\s+\w+;\n", "", t, flags=re.M); t = re.sub(r"^\s*consistent\s+\w+;\n", "", t, flags=re.M)
extra = ("    transonic       yes;\n" if a.transonic else "") + ("    consistent      yes;\n" if a.consistent else "")
if extra: t2 = re.sub(r"(SIMPLE\s*\{\s*\n)", r"\1" + extra, t, count=1); assert t2 != t; t = t2
for kv in filter(None, a.relax.split(",")):
    k, v = kv.split("="); t2 = re.sub(rf"^(\s*{k})\s+[0-9.]+;", rf"\g<1> {float(v):g};", t, count=1, flags=re.M)
    if t2 == t: log(f"relaxation entry {k} not found in fvSolution (skipped)")
    t = t2
open(fv, "w").write(t)
fs = os.path.join(case, "system", "fvSchemes"); t = open(fs).read()
if a.transonic and "div(phid,p)" not in t: t2 = re.sub(r"(divSchemes\s*\{\s*\n)", r"\1    div(phid,p)     Gauss upwind;\n", t, count=1); assert t2 != t; open(fs, "w").write(t2); log("fvSchemes: added div(phid,p) Gauss upwind")
if a.build_only: log("build-only done"); sys.exit(0)
rc, out = foamutil.foam_run(case, "decomposePar -force", "decomposePar", check=False, timeout=3600); log(f"decomposePar rc={rc}")
if rc: print(out[-1500:]); sys.exit("decomposePar failed")
t0 = time.time(); rc, out = foamutil.foam_run(case, f"mpirun -np {a.np} rhoSimpleFoam -parallel 2>&1 | tee log.rhoSimpleFoam.live", "rhoSimpleFoam", check=False, timeout=12 * 3600)
lastit = foamutil.last_iteration(out); fatal = ("FOAM FATAL" in out) or ("sigFpe" in out) or ("nan" in out[-20000:].lower()); log(f"solver rc={rc} last it={lastit} fatal={fatal} wall={time.time()-t0:.0f}s")
rrc, _ = foamutil.foam_run(case, "reconstructPar -latestTime", "reconstructPar", check=False, timeout=3600); log(f"reconstructPar rc={rrc}")
if rrc == 0:
    for p in os.listdir(case):
        if p.startswith("processor"): shutil.rmtree(os.path.join(case, p))
import numpy as np
hdr, data = foamutil.parse_dat(foamutil.find_fo_file(case, "forces_all", "moment.dat")); hf, fdata = foamutil.parse_dat(foamutil.find_fo_file(case, "forces_all", "force.dat"))
it = data[:, 0]; roll = -data[:, hdr.index("total_z")]; yaw = data[:, hdr.index("total_x")]; pitch = data[:, hdr.index("total_y")]; fx = fdata[:, hf.index("total_x")]; fy = fdata[:, hf.index("total_y")]; fz = fdata[:, hf.index("total_z")]
w = min(a.avg_window, len(roll)); wr = roll[-w:]; mean = float(wr.mean()); den = abs(mean) or 1e-12
blocks = [float(wr[i:i + 250].mean()) for i in range(0, len(wr) - 249, 250)]; block_std = 100 * float(np.std(blocks)) / den if len(blocks) > 1 else float("nan")
drift = 100 * abs(float(wr[-w // 4:].mean()) - float(wr[:w // 4].mean())) / den; done = (not fatal) and int(it[-1]) >= a.endtime - 1
lim = [l for l in out.splitlines() if "limitTemperature" in l][-2:]; pc = [l for l in out.splitlines() if "pressureControl" in l][-2:]
res = dict(deflection=a.deflection, mach=a.mach, V_mps=V, solver=f"rhoSimpleFoam restart from {a.steady}/{last}, iteration ramp {V0}->{V} m/s over {a.ramp_iters}, transonic {a.transonic}, consistent {a.consistent}, relax '{a.relax}'", restart_from=f"{a.steady}/{last}",
           endtime=a.endtime, last_iteration=int(it[-1]), pMin=a.pmin, pMax=a.pmax, mesh_name=srcres.get("mesh_name"), stop_reason=("endTime" if done else "diverged"),
           window=dict(it_start=int(it[-w]), it_end=int(it[-1]), n=int(w)), moments_Nm=dict(Mroll=mean, Myaw=float(yaw[-w:].mean()), Mpitch=float(pitch[-w:].mean())), forces_N=dict(Fx=float(fx[-w:].mean()), Fy=float(fy[-w:].mean()), Fz=float(fz[-w:].mean())),
           convergence=dict(std_rel_pct=100 * float(wr.std()) / den, block_std_pct=block_std, block_means=blocks, drift_pct=drift, roll_min=float(wr.min()), roll_max=float(wr.max()), last_limitT=lim, last_pressureControl=pc))
json.dump(res, open(os.path.join(case, "result.json"), "w"), indent=2); print(json.dumps({k: res[k] for k in ("stop_reason", "last_iteration", "moments_Nm", "forces_N", "convergence")}, indent=1))
