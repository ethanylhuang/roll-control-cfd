"""Run the local (converged) steady rhoSimpleFoam setup on SimScale's mesh v3 (downloaded ascii polyMesh): solver-vs-mesh test."""
import os, sys, json, re, shutil, subprocess, time
ROOT = os.path.dirname(os.path.abspath(__file__)); SKILL = os.path.expanduser("~/.claude/skills/cfd-sweep/scripts")
sys.path.insert(0, SKILL); sys.path.insert(0, os.path.join(ROOT, "pipeline"))
import foamutil, run_sweep as rs, report as report_mod
SP = "/private/tmp/claude-501/-Users-trasomi-dev-cfd/e77796e5-73f1-4b54-ac10-df1a9b566759/scratchpad"
D10 = os.path.join(ROOT, "runs_v4", "d10"); TPL = os.path.join(D10, "M0.90_filled_fine_opensides"); MESH = os.path.join(D10, "mesh_simscale_v3")
PMIN = float(sys.argv[sys.argv.index("--pmin") + 1]) if "--pmin" in sys.argv else 20000.0
SS_BCS = "--simscale-bcs" in sys.argv; SS_SCHEMES = "--simscale-schemes" in sys.argv; SS_GRAD = "--simscale-grad" in sys.argv; UNLIM = "--unlimited-grad" in sys.argv; LSG = "--ls-grad" in sys.argv
case = os.path.join(D10, "M0.90_simscale_v3mesh_local" + ("" if PMIN == 20000.0 else f"_pmin{int(PMIN/1000)}k") + ("_ssBCs" if SS_BCS else "") + ("_ssSchemes" if SS_SCHEMES else "") + ("_ssGrad" if SS_GRAD else "") + ("_unlimGrad" if UNLIM else "") + ("_lsGrad" if LSG else "")); ENDTIME = 2000; AVG = 500; NP = 10
def log(m): print(time.strftime("%H:%M:%S"), m, flush=True)
pm = json.load(open(f"{SP}/v3_patch_map.json")); g = pm["groups"]
inlet = g["Velocity inlet 1"][0]; outlet = g["Pressure outlet 2"][0]; sides = g["Sides open (pressure outlet)"]; walls = g["Wall 4"]
if not os.path.exists(os.path.join(MESH, "constant", "polyMesh")):
    os.makedirs(os.path.join(MESH, "constant")); shutil.copytree(f"{SP}/sol_v3/constant/polyMesh", os.path.join(MESH, "constant", "polyMesh"))
if os.path.exists(case): shutil.rmtree(case)
os.makedirs(os.path.join(case, "constant")); shutil.copytree(os.path.join(TPL, "0"), os.path.join(case, "0")); shutil.copytree(os.path.join(TPL, "system"), os.path.join(case, "system"))
for f in os.listdir(os.path.join(TPL, "constant")):
    src = os.path.join(TPL, "constant", f)
    if os.path.isfile(src): shutil.copy(src, os.path.join(case, "constant", f))
os.symlink(os.path.relpath(os.path.join(MESH, "constant", "polyMesh"), os.path.join(case, "constant")), os.path.join(case, "constant", "polyMesh"))
# rewrite boundaryField patch names in every 0/ field
def block(txt, name):
    m = re.search(r"\n(\s*)" + re.escape(name) + r"[ \t]*(?://[^\n]*)?\n\s*\{(.*?)\n\s*\}", txt, re.S); return m
for f in os.listdir(os.path.join(case, "0")):
    p = os.path.join(case, "0", f); t = open(p).read()
    if "boundaryField" not in t: continue
    mi, mo, ms, mw = block(t, "inlet"), block(t, "outlet"), block(t, "sides"), block(t, '"rocket.*"')
    if not (mi and mo and ms and mw): print("skip", f, bool(mi), bool(mo), bool(ms), bool(mw)); continue
    body = lambda m: m.group(2)
    new = "\n    " + inlet + "\n    {" + body(mi) + "\n    }\n    " + outlet + "\n    {" + body(mo) + "\n    }\n"
    for s in sides: new += "    " + s + "\n    {" + body(ms) + "\n    }\n"
    new += '    "B5_TE5_B5_TE.*"\n    {' + body(mw) + "\n    }\n"
    head = t[:t.index("boundaryField")]; t2 = head + "boundaryField\n{" + new + "}\n"
    open(p, "w").write(t2)
log(f"0/ rewritten: inlet {inlet}, outlet {outlet}, sides {sides}, walls regex for {len(walls)} patches")
if SS_BCS:  # SimScale's BC choices: sides/outlet U inletOutlet(0), T zeroGradient on sides/outlet, nutUSpaldingWallFunction, omega wall blending stepwise
    def sub_block(t, name, new_body):
        return re.sub(r"(\n\s{4}" + re.escape(name) + r"[ \t]*(?://[^\n]*)?\n\s{4}\{)(.*?)(\n\s{4}\})", lambda mm: mm.group(1) + new_body + mm.group(3), t, count=1, flags=re.S)
    pU = os.path.join(case, "0", "U"); t = open(pU).read()
    for sname in sides: t = sub_block(t, sname, "\n        type            inletOutlet;\n        inletValue      uniform (0 0 0);\n        value           uniform $Ustart;")
    open(pU, "w").write(t)
    pT = os.path.join(case, "0", "T"); t = open(pT).read()
    for sname in sides + [outlet]: t = sub_block(t, sname, "\n        type            zeroGradient;")
    open(pT, "w").write(t)
    pn = os.path.join(case, "0", "nut"); t = open(pn).read(); t = sub_block(t, '"B5_TE5_B5_TE.*"', "\n        type            nutUSpaldingWallFunction;\n        maxIter         100;\n        tolerance       1e-07;\n        value           uniform 0;"); open(pn, "w").write(t)
    po = os.path.join(case, "0", "omega"); t = open(po).read(); t = sub_block(t, '"B5_TE5_B5_TE.*"', "\n        type            omegaWallFunction;\n        blending        stepwise;\n        value           uniform $omegaInf;"); open(po, "w").write(t)
    log("SimScale BC variants applied (sides inletOutlet U, T zeroGradient sides/outlet, nutUSpalding, omega stepwise)")
if LSG:  # unlimited leastSquares for ALL gradients (SimScale LEASTSQUARES forDefault)
    fsch = os.path.join(case, "system", "fvSchemes"); t = open(fsch).read()
    t = re.sub(r"gradSchemes\s*\{.*?\n\}", "gradSchemes\n{\n    default         leastSquares;\n}", t, count=1, flags=re.S); open(fsch, "w").write(t); log("unlimited leastSquares for all gradients")
if UNLIM:  # SimScale-equivalent: Gauss linear unlimited for ALL gradients (SimScale cannot limit U/k/omega separately)
    fsch = os.path.join(case, "system", "fvSchemes"); t = open(fsch).read()
    t = re.sub(r"gradSchemes\s*\{.*?\n\}", "gradSchemes\n{\n    default         Gauss linear;\n}", t, count=1, flags=re.S); open(fsch, "w").write(t); log("unlimited Gauss linear for all gradients")
if SS_GRAD:  # only the gradient scheme change
    fsch = os.path.join(case, "system", "fvSchemes"); t = open(fsch).read()
    t = re.sub(r"gradSchemes\s*\{.*?\n\}", "gradSchemes\n{\n    default         cellLimited leastSquares 1.0;\n}", t, count=1, flags=re.S); open(fsch, "w").write(t); log("SimScale gradient scheme only (cellLimited leastSquares 1 for all gradients)")
if SS_SCHEMES:  # SimScale's scheme choices: cellLimited leastSquares 1 for all gradients, bounded div(phi,U) linearUpwindV, bounded K/h
    fsch = os.path.join(case, "system", "fvSchemes"); t = open(fsch).read()
    t = re.sub(r"gradSchemes\s*\{.*?\n\}", "gradSchemes\n{\n    default         cellLimited leastSquares 1.0;\n}", t, count=1, flags=re.S)
    t = re.sub(r"div\(phi,U\)\s+[^;]+;", "div(phi,U)      bounded Gauss linearUpwindV grad(U);", t, count=1)
    t = re.sub(r"div\(phi,K\)\s+[^;]+;", "div(phi,K)      bounded Gauss linear;", t, count=1)
    t = re.sub(r"div\(phi,h\)\s+[^;]+;", "div(phi,h)      bounded Gauss upwind;", t, count=1)
    open(fsch, "w").write(t); log("SimScale scheme variants applied (cellLimited leastSquares 1 gradients, bounded linearUpwindV/K/h)")
cd = os.path.join(case, "system", "controlDict"); t = open(cd).read()
wl = "(" + " ".join(walls) + ")"
t = t.replace("patches         (rocket_body rocket_fins rocket_tab rocket_slot);", f"patches         {wl};").replace("patches         (rocket_tab rocket_slot);", f"patches         {wl};").replace("patches         (rocket_tab);", f"patches         {wl};")
open(cd, "w").write(t); assert "rocket_" not in t, "unmapped patches remain in controlDict"
fs = os.path.join(case, "system", "flowSettings"); t = open(fs).read(); t = re.sub(r"^endTime\s+\S+;", f"endTime     {ENDTIME};", t, flags=re.M); open(fs, "w").write(t)
fv = os.path.join(case, "system", "fvSolution"); t = open(fv).read(); t = re.sub(r"pMin\s+[^;]+;", f"pMin            {PMIN:g};", t, count=1); open(fv, "w").write(t)
if "--build-only" in sys.argv: log("build-only done"); sys.exit(0)
rc, out = foamutil.foam_run(case, "decomposePar -force", "decomposePar", check=False, timeout=3600); log(f"decomposePar rc={rc}")
if rc: print(out[-1500:]); sys.exit("decomposePar failed")
t0 = time.time(); rc, out = foamutil.foam_run(case, f"mpirun -np {NP} rhoSimpleFoam -parallel 2>&1 | tee log.rhoSimpleFoam.live", "rhoSimpleFoam", check=False, timeout=12 * 3600)
last = foamutil.last_iteration(out); fatal = ("FOAM FATAL" in out) or ("sigFpe" in out)
stop = "diverged" if fatal else ("endTime" if (last and int(float(last)) >= ENDTIME) else f"stopped@{last}"); log(f"solver rc={rc} last={last} stop={stop} wall={time.time()-t0:.0f}s")
avg_start = ENDTIME - AVG
res = dict(deflection=10.0, mach=0.9, V_mps=305.0, stop_reason=stop, start="ramp", pMin=PMIN, pMax=300000.0, relax_overrides="p=0.3,rho=0.05,U=0.7,h=0.7,k=0.7,omega=0.7", div_u="", transonic=False, consistent=False, open_sides=True, slot_level=None, mesh_name="mesh_simscale_v3 (SimScale mesh op b4ed004d, 1.60M cells)", setup="local rhoSimpleFoam on SimScale mesh v3" + (" + SimScale BCs" if SS_BCS else "") + (" + SimScale schemes" if SS_SCHEMES else "") + (" + SimScale gradients only" if SS_GRAD else "") + (" + unlimited Gauss linear gradients" if UNLIM else "") + (" + unlimited leastSquares gradients" if LSG else ""), cofr_z=0.399, p_inf=97690.0, T_inf=286.2, rho_inf=1.18915)
try:
    mom, nm = rs.window_means(case, "forces_all", "moment.dat", avg_start, foamutil.find_fo_file, foamutil.parse_dat)
    frc, _ = rs.window_means(case, "forces_all", "force.dat", avg_start, foamutil.find_fo_file, foamutil.parse_dat)
    conv = report_mod.mroll_convergence(case, avg_start, ENDTIME, 3.0, 5.0)
    res.update(n_avg_samples=nm, moments_Nm=(dict(Mroll=-mom["total_z"], Mpitch=mom["total_y"], Myaw=mom["total_x"]) if mom else None), forces_N=(dict(Fx=frc["total_x"], Fy=frc["total_y"], Fz=frc["total_z"]) if frc else None), convergence=conv)
except Exception as e: res.update(postprocess_error=repr(e))
json.dump(res, open(os.path.join(case, "result.json"), "w"), indent=2)
print(json.dumps({k: res.get(k) for k in ("stop_reason", "n_avg_samples", "moments_Nm", "forces_N", "convergence", "postprocess_error")}, indent=1))
