#!/usr/bin/env python3
"""Run one d10 / M0.9 case with the SimScale 'roll-control' setup recreated
locally (spec re-read from the SimScale API 2026-09-04, project
5692073260772831163, simulation 'Compressible', mesh 'Mesh 33').

Recreated from the live spec (templates/case_simscale + this runner):
  domain       z -4.40..2.00, background 21x21x112 (cubic 0.05714 m cells)
  freestream   p 97690 Pa, T 286.2 K, U (0 0 -305)  -> M 0.899, rho 1.189
  turbulence   k 13.98 m2/s2, omega 93500 1/s (SimScale automatic, ~1 % / 10x)
  material     Air: M 28.97, Cp 1004, mu 1.83e-5, Pr 0.713, sensibleEnthalpy
  momentum     Gauss linearUpwindV grad(U); h upwind; k/omega bounded upwind
  gradient     cellLimited leastSquares 1; laplacian/snGrad limited 0.5
  relaxation   p 0.15  rho 0.1  U 0.5  h 0.5  k 0.3  omega 0.5
  pressure     pMin 50 kPa / pMax 200 kPa, GAMG 2/1 sweeps, nNonOrth 1
  control      endTime 3000, mean over the final 500 iterations, CofR (0,0,0.399)

--start faithful : SimScale start = uniform fields + potentialFoam, inlet at
                   -305 m/s from iteration 1 (what the SimScale run did)
--start ramp     : v4 start = inlet ramped -50 -> -305 m/s over 300
                   iterations, no potentialFoam (the ONLY change vs faithful)
"""
import argparse
import json
import os
import re
import shutil
import sys

SKILL = os.path.expanduser("~/.claude/skills/cfd-sweep/scripts")
sys.path.insert(0, SKILL)
sys.path.insert(0, os.path.join(os.getcwd(), "pipeline"))

import run_sweep as rs
import foamutil

TPL = os.path.join(SKILL, "..", "templates", "case_simscale")
K_INF, OMEGA_INF = 13.98, 93500.0        # SimScale initialConditions (auto turbulence)


def copy_template(case):
    os.makedirs(case, exist_ok=True)
    for sub in ("0.orig", "constant", "system"):
        dst = os.path.join(case, sub)
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(os.path.join(TPL, sub), dst)


rs.copy_template = copy_template          # both mesh and solve use the variant


def patch_turbulence(case):
    fp = os.path.join(case, "system", "flowSettings")
    s = open(fp).read()
    s = re.sub(r"^kInf\s+[^;]+;", f"kInf        {K_INF:g};      // SimScale", s, flags=re.M)
    s = re.sub(r"^omegaInf\s+[^;]+;", f"omegaInf    {OMEGA_INF:g};     // SimScale", s, flags=re.M)
    open(fp, "w").write(s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", choices=("faithful", "ramp"), default="faithful")
    ap.add_argument("--endtime", type=int, default=3000)
    ap.add_argument("--avg-window", type=int, default=500)
    ap.add_argument("--case", default=None, help="case dir name under runs_v4/d10")
    ap.add_argument("--ramp-iters", type=int, default=None, help="ramp length in iterations (config ramp_iters=300)")
    ap.add_argument("--relax", default="", help="relaxation overrides, e.g. 'p=0.3,rho=0.05,U=0.7,h=0.7,k=0.7,omega=0.7' (probe 2026-09-04: v4 set converges, SimScale set cycles)")
    ap.add_argument("--div-u", default="", choices=("", "upwind", "linearUpwind", "linearUpwindV", "limitedLinearV"), help="override div(phi,U): upwind = SimScale BOUNDED_GAUSS_UPWIND (bounded, 1st order)")
    ap.add_argument("--transonic", action="store_true", help="SIMPLE transonic yes (compressible pressure equation with div(phid,p))")
    ap.add_argument("--consistent", action="store_true", help="SIMPLEC (consistent yes)")
    ap.add_argument("--open-sides", action="store_true", help="sides patch = pressure outlet (p fixed pInf, U pressureInletOutletVelocity, T/k/omega inletOutlet) instead of slip walls")
    ap.add_argument("--levels", default=None, help="body,fins,tab snappy levels, e.g. 5,6,6 (config 4,5,5)")
    ap.add_argument("--slot-level", type=int, default=None, help="snappy level for the tab slot surface + slot box (config 8 resolves the 0.75 mm gap; 5 = 1.8 mm cells seal it)")
    ap.add_argument("--mesh-name", default="mesh_simscale", help="mesh directory name under runs_v4/d10")
    ap.add_argument("--mach", type=float, default=0.9, help="freestream Mach; V = Mach x 339.1 m/s (286.2 K)")
    ap.add_argument("--deflection", type=float, default=10.0, help="tab deflection in deg (geometry exported from Onshape via the v4 exporter if models_v4/dXX is missing)")
    ap.add_argument("--pmin", type=float, default=50000.0, help="pressureControl pMin [Pa] (SimScale 50000)")
    ap.add_argument("--pmax", type=float, default=200000.0, help="pressureControl pMax [Pa] (SimScale 200000)")
    a = ap.parse_args()

    root = os.getcwd()
    cfg = rs.load(root)
    mach = a.mach
    v_free = 305.0 if abs(mach - 0.9) < 1e-6 else round(mach * 339.1, 1)   # SimScale M0.9 inlet is exactly -305
    cfg["mach_velocities"][f"{mach:g}"] = v_free
    cfg["z_cg"] = 0.399                     # SimScale CofR (0,0,399 mm)
    cfg["p_inf"], cfg["T_inf"] = 97690.0, 286.2
    cfg["rho_inf"] = cfg["p_inf"] / (287.04 * cfg["T_inf"])
    cfg["endtime"] = a.endtime
    cfg["avg_start"] = a.endtime - a.avg_window
    cfg["auto_extend"] = False
    if a.start == "faithful":
        cfg["u_start"] = 305.0              # no ramp: freestream from iteration 1
    else:
        cfg["u_start"] = 50.0               # v4 ramp, cfg["ramp_iters"] (300) long
        if a.ramp_iters:
            cfg["ramp_iters"] = a.ramp_iters
    d, np_ = float(a.deflection), int(os.environ.get("CFD_NP", cfg["np"]))   # CFD_NP overrides sweep_config np (side tests next to a running sweep)
    if not os.path.exists(os.path.join(root, cfg["roots"]["models"], rs.dtag(d), "geometry_report.json")):
        from onshape_export import export as onshape_export
        rs.ensure_exports(root, cfg, [d], onshape_export)
    name = a.case or (f"M{mach:.2f}_simscale" if a.start == "faithful" else f"M{mach:.2f}_simscale_ramp")

    print(f"SimScale-matched run [{a.start}]: d{int(d)} M{mach} V={v_free} m/s p={cfg['p_inf']:g} "
          f"T={cfg['T_inf']} rho={cfg['rho_inf']:.4f} CofR z={cfg['z_cg']} "
          f"endTime={cfg['endtime']} avg from {cfg['avg_start']} case={name}")

    levels = None
    if a.slot_level is not None or a.levels:
        levels = dict(cfg.get("levels", {"body": 4, "fins": 5, "tab": 5, "slot": 8}))
        if a.slot_level is not None: levels["slot"] = a.slot_level
        if a.levels:
            b, f, t = (int(x) for x in a.levels.split(",")); levels.update(body=b, fins=f, tab=t)
        print(f"[mesh] levels {levels} -> mesh '{a.mesh_name}'")
    mesh_dir, rep = rs.mesh_deflection(root, d, cfg, foamutil.foam_run,
                                       levels=levels, mesh_name=a.mesh_name)

    case = os.path.join(root, cfg["roots"]["runs"], rs.dtag(d), name)
    if os.path.exists(case):
        shutil.rmtree(case)
    copy_template(case)
    pm = os.path.join(case, "constant", "polyMesh")
    if os.path.lexists(pm):
        os.unlink(pm) if os.path.islink(pm) else shutil.rmtree(pm)
    os.symlink(os.path.relpath(os.path.join(mesh_dir, "constant", "polyMesh"),
                               os.path.join(case, "constant")), pm)
    meta = rs.write_flow_settings(case, root, cfg, mach, rep, cfg["endtime"], np_)
    patch_turbulence(case)
    fs = os.path.join(case, "system", "fvSolution"); t = open(fs).read()
    t = re.sub(r"pMin\s+[^;]+;", f"pMin            {a.pmin:g};", t, count=1)
    t = re.sub(r"pMax\s+[^;]+;", f"pMax            {a.pmax:g};", t, count=1)
    for kv in filter(None, a.relax.split(",")):
        k, v = kv.split("=")
        t2 = re.sub(rf"^(\s*{k})\s+[0-9.]+;", rf"\g<1> {float(v):g};", t, count=1, flags=re.M)
        assert t2 != t, f"relaxation entry {k} not found"
        t = t2
    open(fs, "w").write(t)
    if a.transonic or a.consistent:
        t = open(fs).read()
        extra = ("    transonic       yes;\n" if a.transonic else "") + ("    consistent      yes;\n" if a.consistent else "")
        t2 = re.sub(r"(SIMPLE\s*\{\s*\n)", r"\1" + extra, t, count=1)
        assert t2 != t; open(fs, "w").write(t2); print(f"[solve] SIMPLE: {extra.strip()}")
    if a.div_u:
        sc = os.path.join(case, "system", "fvSchemes"); u = open(sc).read()
        new = {"upwind": "bounded Gauss upwind", "linearUpwind": "bounded Gauss linearUpwind limited",
               "linearUpwindV": "Gauss linearUpwindV grad(U)",
               "limitedLinearV": "Gauss limitedLinearV 1"}[a.div_u]
        u2 = re.sub(r"div\(phi,U\)\s+[^;]+;", f"div(phi,U)      {new};", u, count=1)
        assert u2 != u; open(sc, "w").write(u2); print(f"[solve] div(phi,U) -> {new}")
    print(f"[solve] pressure bounds {a.pmin:g} .. {a.pmax:g} Pa; relaxation overrides: {a.relax or 'none (SimScale set)'}")
    print(f"[solve] hinge {meta['hinge_src']} at {['%.4f' % v for v in meta['hinge_point']]}")

    if a.open_sides:
        reps = {"U": ("type            pressureInletOutletVelocity;\n        value           uniform $Ustart;"),
                "p": ("type            fixedValue;\n        value           uniform $pInf;"),
                "T": ("type            inletOutlet;\n        inletValue      uniform $Tinf;\n        value           uniform $Tinf;"),
                "k": ("type            inletOutlet;\n        inletValue      uniform $kInf;\n        value           uniform $kInf;"),
                "omega": ("type            inletOutlet;\n        inletValue      uniform $omegaInf;\n        value           uniform $omegaInf;")}
        for fld, body in reps.items():
            fp0 = os.path.join(case, "0.orig", fld); z = open(fp0).read()
            z2 = re.sub(r"sides\s*\{[^}]*\}", "sides\n    {\n        " + body + "\n    }", z, count=1)
            assert z2 != z, fld; open(fp0, "w").write(z2)
        print("[solve] sides -> pressure outlet (open far field)")
    shutil.rmtree(os.path.join(case, "0"), ignore_errors=True)
    shutil.copytree(os.path.join(case, "0.orig"), os.path.join(case, "0"))
    foamutil.foam_run(case, "decomposePar -force", "decomposePar", timeout=3600)

    if a.start == "faithful":
        print("[solve] potentialFoam initialisation (SimScale potentialFoamInitialization=True)")
        foamutil.foam_run(case, f"mpirun -np {np_} potentialFoam -parallel -writephi",
                          "potentialFoam", check=False, timeout=3600)
    else:
        print(f"[solve] ramped start -{cfg['u_start']:g} -> -{v_free:g} m/s over {cfg['ramp_iters']} iterations, no potentialFoam")

    print(f"[solve] rhoSimpleFoam to {cfg['endtime']} ...", flush=True)
    # tee keeps a LIVE copy of the solver log (pressureControl / limitTemperature
    # lines) while foam_run still captures the whole thing for classify_stop.
    rc, log = foamutil.foam_run(case, f"mpirun -np {np_} rhoSimpleFoam -parallel 2>&1 | tee log.rhoSimpleFoam.live",
                                "rhoSimpleFoam", check=False, timeout=12 * 3600)
    stop = foamutil.classify_stop(log, endtime=cfg["endtime"])
    print(f"[solve] stop={stop} rc={rc} iters={foamutil.last_iteration(log)}", flush=True)
    rrc, _ = foamutil.foam_run(case, "reconstructPar -latestTime", "reconstructPar",
                               check=False, timeout=3600)
    if rrc == 0:
        for p in os.listdir(case):
            if p.startswith("processor"):
                shutil.rmtree(os.path.join(case, p))
    else:
        print("[solve] reconstructPar failed; processor dirs kept")

    import report as report_mod
    out = dict(deflection=d, mach=mach, V_mps=meta["v"], stop_reason=stop, start=a.start,
               pMin=a.pmin, pMax=a.pmax, relax_overrides=a.relax, div_u=a.div_u, transonic=a.transonic, consistent=a.consistent, open_sides=a.open_sides, slot_level=a.slot_level, mesh_name=a.mesh_name,
               setup="simscale-matched", cofr_z=cfg["z_cg"], p_inf=cfg["p_inf"],
               T_inf=cfg["T_inf"], rho_inf=cfg["rho_inf"])
    try:
        stats = foamutil.fo_stats(case, "forceCoeffs_total", window=a.avg_window)
        mom, nm = rs.window_means(case, "forces_all", "moment.dat", cfg["avg_start"],
                                  foamutil.find_fo_file, foamutil.parse_dat)
        frc, _ = rs.window_means(case, "forces_all", "force.dat", cfg["avg_start"],
                                 foamutil.find_fo_file, foamutil.parse_dat)
        conv = report_mod.mroll_convergence(case, cfg["avg_start"], cfg["endtime"], 3.0, 5.0)
        out.update(n_avg_samples=nm,
                   moments_Nm=(dict(Mroll=-mom["total_z"], Mpitch=mom["total_y"],
                                    Myaw=mom["total_x"]) if mom else None),
                   forces_N=(dict(Fx=frc["total_x"], Fy=frc["total_y"],
                                  Fz=frc["total_z"]) if frc else None),
                   coefficients=stats, convergence=conv)
    except Exception as e:                  # a diverged/short run has no window
        out.update(postprocess_error=repr(e))
    with open(os.path.join(case, "result.json"), "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps({k: out.get(k) for k in
                      ("stop_reason", "n_avg_samples", "moments_Nm", "forces_N",
                       "convergence", "postprocess_error")}, indent=1))


if __name__ == "__main__":
    main()
