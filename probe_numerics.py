#!/usr/bin/env python3
"""Single-variable stability probes: the SimScale-matched case (templates/case_simscale)
with ONE group reverted to the v4 setting, d10 / M0.9, ramp -50 -> -305 over 300
iterations, endTime 200 (the SimScale-numerics ramp-300 run collapsed at 100-135).
usage: probe_numerics.py <name>   names: base bounded relax rho prelax eqrelax gamg laplacian energy bounds nonorth solvers turb"""
import os, re, shutil, sys, importlib.util
sys.path.insert(0, os.path.expanduser("~/.claude/skills/cfd-sweep/scripts")); sys.path.insert(0, "pipeline")
import run_sweep as rs, foamutil
spec = importlib.util.spec_from_file_location("rsm", "run_simscale_match.py"); rsm = importlib.util.module_from_spec(spec); spec.loader.exec_module(rsm)
V4 = os.path.expanduser("~/.claude/skills/cfd-sweep/templates/case")
name = sys.argv[1]; END = 200
root = os.getcwd(); cfg = rs.load(root)
cfg["mach_velocities"]["0.9"] = 305.0; cfg["z_cg"] = 0.399; cfg["p_inf"], cfg["T_inf"] = 97690.0, 286.2
cfg["rho_inf"] = cfg["p_inf"] / (287.04 * cfg["T_inf"]); cfg["u_start"] = 50.0; cfg["ramp_iters"] = 300
cfg["endtime"] = END; cfg["avg_start"] = END - 50; cfg["auto_extend"] = False
mesh_dir, rep = rs.mesh_deflection(root, 10.0, cfg, foamutil.foam_run, mesh_name="mesh_simscale")  # reuses the marker
case = os.path.join(root, cfg["roots"]["runs"], "d10", f"probe_{name}")
if os.path.exists(case): shutil.rmtree(case)
rsm.copy_template(case)
pm = os.path.join(case, "constant", "polyMesh")
os.symlink(os.path.relpath(os.path.join(mesh_dir, "constant", "polyMesh"), os.path.join(case, "constant")), pm)
meta = rs.write_flow_settings(case, root, cfg, 0.9, rep, END, cfg["np"])
if name != "turb":
    rsm.patch_turbulence(case)
def sub(rel, pairs):
    fp = os.path.join(case, rel); s = open(fp).read()
    for a, b in pairs:
        s2 = re.sub(a, b, s, count=1, flags=re.M)
        assert s2 != s, f"pattern not found in {rel}: {a}"
        s = s2
    open(fp, "w").write(s)
if name == "bounded":
    sub("system/fvSchemes", [(r"div\(phi,U\)\s+Gauss linearUpwindV grad\(U\);", "div(phi,U)      bounded Gauss linearUpwindV grad(U);"),
                            (r"div\(phi,K\)\s+Gauss linear;", "div(phi,K)      bounded Gauss linear;")])
elif name == "relax":
    sub("system/fvSolution", [(r"p\s+0\.15;", "p 0.3;"), (r"rho\s+0\.1;", "rho 0.05;"), (r"U\s+0\.5;", "U 0.7;"),
                             (r"e\s+0\.1;", "e 0.7;"), (r"h\s+0\.5;", "h 0.7;"), (r"k\s+0\.3;", "k 0.7;"), (r"omega\s+0\.5;", "omega 0.7;")])
elif name == "rho":
    sub("system/fvSolution", [(r"rho\s+0\.1;", "rho 0.05;")])
elif name == "prelax":
    sub("system/fvSolution", [(r"p\s+0\.15;", "p 0.3;")])
elif name == "eqrelax":
    sub("system/fvSolution", [(r"U\s+0\.5;", "U 0.7;"), (r"h\s+0\.5;", "h 0.7;"), (r"k\s+0\.3;", "k 0.7;"), (r"omega\s+0\.5;", "omega 0.7;")])
elif name == "gamg":
    sub("system/fvSolution", [(r"nPreSweeps\s+2;\s*nPostSweeps\s+1;\s*cacheAgglomeration on;\s*nCellsInCoarsestLevel 100;\s*mergeLevels 1;\s*tolerance\s+1e-7;", "tolerance 1e-8;")])
elif name == "laplacian":
    sub("system/fvSchemes", [(r"default\s+Gauss linear limited corrected 0\.5;", "default Gauss linear corrected;"),
                            (r"default\s+limited corrected 0\.5;", "default corrected;")])
elif name == "energy":
    shutil.copy(os.path.join(V4, "constant", "thermophysicalProperties"), os.path.join(case, "constant", "thermophysicalProperties"))
    sub("system/fvSchemes", [(r"div\(phi,e\)\s+Gauss linearUpwind limited;", "div(phi,e) bounded Gauss limitedLinear 1;"),
                            (r"div\(phi,K\)\s+Gauss linear;", "div(phi,K) bounded Gauss limitedLinear 1;"),
                            (r"div\(phi,Ekp\)\s+bounded Gauss upwind;", "div(phi,Ekp) bounded Gauss limitedLinear 1;")])
elif name == "bounds":
    sub("system/fvSolution", [(r"pMin\s+[^;]+;", "pMin 1;"), (r"pMax\s+[^;]+;", "pMax 1e8;")])
elif name == "nonorth":
    sub("system/fvSolution", [(r"nNonOrthogonalCorrectors\s+1;", "nNonOrthogonalCorrectors 0;")])
elif name == "solvers":
    shutil.copy(os.path.join(V4, "system", "fvSolution"), os.path.join(case, "system", "fvSolution"))
    # keep SimScale SIMPLE + relaxation, only the linear solvers from v4
    sub("system/fvSolution", [(r"nNonOrthogonalCorrectors\s+0;", "nNonOrthogonalCorrectors 1;"), (r"pMin\s+1;", "pMin 50000;"), (r"pMax\s+1e8;", "pMax 200000;"),
                             (r"p\s+0\.3;", "p 0.15;"), (r"rho\s+0\.05;", "rho 0.1;"), (r"U\s+0\.7;", "U 0.5;"), (r"e\s+0\.7;", "e 0.1;"), (r"h\s+0\.7;", "h 0.5;"),
                             (r'"\(k\|omega\)"\s+0\.7;', "k 0.3; omega 0.5;")])
elif name in ("base", "turb"):
    pass
else:
    sys.exit(f"unknown probe {name}")
print(f"[probe {name}] case {case}")
for rel, pat in (("system/fvSchemes", r"div\(phi,(U|K|e|Ekp)\)|laplacianSchemes|snGradSchemes|default"), ("system/fvSolution", r"pMin|pMax|nNonOrth|^\s+(p|rho|U|e|h|k|omega|\"\(k)\s"), ("constant/thermophysicalProperties", r"energy"), ("system/flowSettings", r"^(kInf|omegaInf|rampTable)")):
    for l in open(os.path.join(case, rel)):
        if re.search(pat, l): print("   ", rel.split("/")[-1] + ":", re.sub(r"\s+", " ", l.split("//")[0].strip())[:90])
shutil.copytree(os.path.join(case, "0.orig"), os.path.join(case, "0"))
foamutil.foam_run(case, "decomposePar -force", "decomposePar", timeout=3600)
print(f"[probe {name}] rhoSimpleFoam to {END} ...", flush=True)
rc, log = foamutil.foam_run(case, f"mpirun -np {cfg['np']} rhoSimpleFoam -parallel 2>&1 | tee log.rhoSimpleFoam.live", "rhoSimpleFoam", check=False, timeout=3600)
for p in os.listdir(case):
    if p.startswith("processor"): shutil.rmtree(os.path.join(case, p))
# ---- summary
t = 0; clamps = []
for line in log.splitlines():
    if line.startswith("Time = "): t = int(float(line.split()[2]))
    elif line.startswith("pressureControl: p m"): clamps.append((t, line.split()[2][1:], float(line.split()[-1])))
F = [[float(x) for x in l.split()] for l in open(os.path.join(case, "postProcessing/forces_all/0/force.dat")) if not l.startswith("#")]
M = [[float(x) for x in l.split()] for l in open(os.path.join(case, "postProcessing/forces_all/0/moment.dat")) if not l.startswith("#")]
zero = sum(1 for f in F if abs(f[6]) < 1e-6)
late = [c for c in clamps if c[0] > 70]
print(f"[probe {name}] iterations {int(F[-1][0])}  clamps total {len(clamps)} (after it.70: {len(late)})  zero-pressure-force rows {zero}")
print(f"[probe {name}] clamp iterations: {sorted(set(c[0] for c in clamps))[:40]}")
print(f"[probe {name}] iter: Fz_tot/Fz_pres/Mroll  " + "  ".join(f"{int(f[0])}:{f[3]:.0f}/{f[6]:.0f}/{-m[3]:.3f}" for f, m in zip(F, M) if int(f[0]) in (25, 50, 75, 100, 125, 150, 175, 200)))
verdict = "PASS" if (zero == 0 and len(late) == 0 and abs(-M[-1][3]) < 0.25) else "FAIL"
print(f"[probe {name}] VERDICT {verdict}")
