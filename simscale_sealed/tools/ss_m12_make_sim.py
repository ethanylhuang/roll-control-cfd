"""ss_m12_make_sim.py [--mach 1.2] [--dt 4e-6] [--endtime 0.012] [--ramp 0.0015] [--procs 64] [--outer 2] [--corr 2]
TRANSIENT compressible simulation in the M1.2 project (simscale_sealed/m12_project.json) on the extracted sealed d15 flow region:
model = the sweep's d15 sealed base spec (simscale_sealed/m12_base_spec_from_sweep_d15.json: linearUpwindV, fixed inlet k/omega, v4 relax,
p 20-300 kPa, open sides) re-pointed by face role, switched to TRANSIENT (Euler, PIMPLE outer x corr, fixed deltaT, forces every step)
with a time-based inlet ramp table (-50 -> -V m/s over --ramp s). Creates or updates the sim; records sim id + table id in m12_project.json."""
import os, sys, json, copy, argparse
sys.path.insert(0, os.path.expanduser("~/.claude/skills/cfd-sweep/scripts"))
from simscale_api import SimScale, ApiError
ap = argparse.ArgumentParser(); ap.add_argument("--mach", type=float, default=1.2); ap.add_argument("--dt", type=float, default=4e-6); ap.add_argument("--endtime", type=float, default=0.012)
ap.add_argument("--ramp", type=float, default=0.0015); ap.add_argument("--procs", type=int, default=64); ap.add_argument("--outer", type=int, default=2); ap.add_argument("--corr", type=int, default=2)
ap.add_argument("--write-every", type=int, default=1000); ap.add_argument("--maxrun", type=int, default=36000); ap.add_argument("--name", default=None); ap.add_argument("--dry", action="store_true")
ap.add_argument("--pmin", type=float, default=None, help="lower pressure bound Pa (default: keep the sweep's 20 kPa)"); ap.add_argument("--pmax", type=float, default=None); ap.add_argument("--potential-init", action="store_true", help="potentialFoam initialisation of the velocity field (smooth impulsive start around the body)"); ap.add_argument("--no-momentum-predictor", action="store_true"); ap.add_argument("--adjustable-co", type=float, default=None, help="Courant-limited adjustable time step (max Co); deltaT then = initial step"); ap.add_argument("--transonic", action="store_true", help="numerics.transonic true (pressure-based supersonic formulation)"); ap.add_argument("--no-ramp", action="store_true", help="impulsive start: constant inlet -V and initial U = -V (a transient must not ramp the inlet: the whole air column would have to accelerate)"); ap.add_argument("--relax-h", type=float, default=None, help="enthalpy relaxation factor (non-final PIMPLE iterations)"); ap.add_argument("--sim", default=None, help="update this simulation id in place instead of matching by name")
a = ap.parse_args(); api = SimScale(); SP = "/Users/trasomi/dev/cfd/simscale_sealed"; J = json.load(open(f"{SP}/m12_project.json")); P = J["new_project"]; flow = J["flow"]
V = round(a.mach * 339.1, 1); gid = flow["geometry_id"]; box = flow["box"]; walls = flow["walls"]
inlet = [box["Max Z@Flow region"]]; outlet = [box["Min Z@Flow region"]]; sides = [box[k + "@Flow region"] for k in ("Max X", "Min X", "Max Y", "Min Y")]
spec = json.load(open(f"{SP}/m12_base_spec_from_sweep_d15.json")); m = copy.deepcopy(spec["model"])
def repoint(h, ents): h["topologicalReference"] = {"entities": ents, "sets": []}
for bc in m["boundaryConditions"]:
    t = bc["type"]; n = bc["name"].lower()
    if t.startswith("VELOCITY_INLET"): repoint(bc, inlet)
    elif t.startswith("PRESSURE_OUTLET") and "side" in n: repoint(bc, sides)
    elif t.startswith("PRESSURE_OUTLET"): repoint(bc, outlet)
    elif t.startswith("WALL"): repoint(bc, walls)
    else: print("unhandled BC", t, bc["name"])
for fl in m["materials"]["fluids"]: repoint(fl, [flow["region"]])
for fm in (m.get("resultControl", {}).get("forcesMoments") or []): repoint(fm, walls)
for key in ("surfaceData", "probePoints"):
    for sd in (m.get("resultControl", {}).get(key) or []):
        if "topologicalReference" in sd: repoint(sd, walls)
# transient
m["timeDependency"] = {"type": "TRANSIENT"}
m["numerics"]["schemes"]["timeDifferentiation"] = {"forDefault": {"type": "EULER"}}
m["numerics"]["numOuterCorrectors"] = a.outer; m["numerics"]["numCorrectors"] = a.corr; m["numerics"]["momentumPredictor"] = True; m["numerics"]["transonic"] = bool(a.transonic)
# transient-only spec hygiene: drop steady-only scheme entries, add density + Final solvers (PIMPLE)
for key in ("div_phi_Ekp",): m["numerics"]["schemes"]["divergence"].pop(key, None)
for key in ("laplacian_rho_1_A_U_pressure",): m["numerics"]["schemes"]["laplacian"].pop(key, None)
sv = m["numerics"]["solvers"]; import copy as _c
sv["densitySolver"] = _c.deepcopy(sv["pressureSolver"])   # rho equation: same GAMG settings as p (schema allows GAMG/PCG/SMOOTH)
for base_key in ("velocity", "pressure", "enthalpy", "internalEnergy", "turbulentKineticEnergy", "omegaDissipationRate", "density"):
    src = sv.get(base_key + "Solver")
    if src is not None: f = _c.deepcopy(src); f["relativeTolerance"] = 0; sv[base_key + "FinalSolver"] = f
sc = m["simulationControl"]; sc["endTime"] = {"value": a.endtime, "unit": "s"}; sc["deltaT"] = {"value": a.dt, "unit": "s"}; sc["adjustableTimestep"] = {"type": "ACTIVE_TIMESTEP", "maximalCourantNumber": a.adjustable_co} if a.adjustable_co else {"type": "INACTIVE_TIMESTEP"}
sc["writeControl"] = {"type": "TIME_STEP", "writeInterval": a.write_every}; sc["numProcessors"] = a.procs; sc["maxRunTime"] = {"value": a.maxrun, "unit": "s"}; sc["potentialFoamInitialization"] = bool(a.potential_init)
if a.no_momentum_predictor: m["numerics"]["momentumPredictor"] = False
fl = m["numerics"].setdefault("stabilization", {}).setdefault("fieldLimits", {})
if a.pmin: fl["lowerPressureBound"] = {"value": a.pmin, "unit": "Pa"}
if a.pmax: fl["upperPressureBound"] = {"value": a.pmax, "unit": "Pa"}
# inlet ramp in physical time
inl = next(b for b in m["boundaryConditions"] if b["type"].startswith("VELOCITY_INLET"))
if a.no_ramp:
    tid = None; inl["velocity"]["value"]["value"] = {"type": "COMPONENT", "x": {"type": "CONSTANT", "value": 0}, "y": {"type": "CONSTANT", "value": 0}, "z": {"type": "CONSTANT", "value": -V}}
    m["initialConditions"]["velocity"]["global"]["value"] = {"x": 0, "y": 0, "z": -V}; print(f"impulsive start: inlet and initial U = (0 0 -{V:g})")
else:
    csv = f"t,ux,uy,uz\n0,0,0,-50\n{a.ramp:g},0,0,-{V:g}\n1,0,0,-{V:g}\n".encode()
    tid = None if a.dry else api.import_table(P, csv); print("ramp table", tid, csv.decode().replace("\n", " | "))
    inl["velocity"]["value"]["value"]["tableId"] = tid; m["initialConditions"]["velocity"]["global"]["value"] = {"x": 0, "y": 0, "z": -50.0}
if a.relax_h: m["numerics"]["relaxationFactor"]["enthalpyEquation"] = a.relax_h
name = a.name or f"SEALED transient d15 M{a.mach:g} (rhoPimple Euler {a.outer}x{a.corr}, dt {a.dt:g}, {a.endtime*1e3:g} ms, {'impulsive start' if a.no_ramp else f'ramp {a.ramp*1e3:g} ms'}{', potentialFoam init' if a.potential_init else ''}{', no mom predictor' if a.no_momentum_predictor else ''}{f', p {a.pmin/1e3:g}-{a.pmax/1e3:g} kPa' if (a.pmin or a.pmax) else ''}{f', adj Co {a.adjustable_co:g}' if a.adjustable_co else ''}{', transonic' if a.transonic else ''}{f', h {a.relax_h:g}' if a.relax_h else ''}, linearUpwindV, v4 relax, API)"
if a.dry: json.dump({"name": name, "geometryId": gid, "model": m, "version": spec["version"]}, open(f"{SP}/m12_sim_body_dry.json", "w"), indent=1); sys.exit("dry: wrote m12_sim_body_dry.json")
sims = api.embedded(f"/projects/{P}/simulations", limit=300); ex = [s for s in sims if s["name"] == name] or ([{"simulationId": a.sim}] if a.sim else [])
body = {"name": name, "geometryId": gid, "model": m, "version": spec["version"]}
if ex:
    sid = ex[0]["simulationId"]; cur = api.simulation(P, sid); cur["model"] = m; cur["geometryId"] = gid; cur["name"] = name
    try: api.update_simulation(P, cur); print("updated", sid, "| mesh", cur.get("meshId"))
    except ApiError as e:
        body_txt = getattr(e, "body", None) or str(e); import re as _re; i = body_txt.find("{") if isinstance(body_txt, str) else -1
        try: probs = json.loads(body_txt[i:])["details"]["problems"]
        except Exception: probs = [dict(path=p_, message="?") for p_ in _re.findall(r'"path" : "([^"]+)"', body_txt)]
        print("update failed:", len(probs), "problems"); [print("  ", pr.get("severity"), pr.get("code"), "|", pr.get("path"), "|", str(pr.get("message"))[:150]) for pr in probs]; sys.exit(1)
else:
    try: sid = api.post(f"/projects/{P}/simulations", body)["simulationId"]; print("created", sid)
    except ApiError as e:
        body_txt = getattr(e, "body", None) or str(e); open(f"{SP}/m12_create_error.txt", "w").write(body_txt if isinstance(body_txt, str) else json.dumps(body_txt))
        import re as _re; i = body_txt.find("{") if isinstance(body_txt, str) else -1
        try: probs = json.loads(body_txt[i:])["details"]["problems"]
        except Exception: probs = [dict(path=p_, message="?") for p_ in _re.findall(r'"path" : "([^"]+)"', body_txt)]
        print("create failed:", len(probs), "problems"); [print("  ", pr.get("severity"), pr.get("code"), "|", pr.get("path"), "|", str(pr.get("message"))[:150]) for pr in probs]; sys.exit(1)
g = api.simulation(P, sid); mm = g["model"]
print("geometry", g["geometryId"][:8], "| timeDependency", mm["timeDependency"], "| dt", mm["simulationControl"]["deltaT"], "endTime", mm["simulationControl"]["endTime"], "| BCs:", [(b["name"], len(b["topologicalReference"]["entities"])) for b in mm["boundaryConditions"]], "| inlet table", mm["boundaryConditions"][0]["velocity"]["value"]["value"].get("tableId"))
try: print("check:", json.dumps(api.check_simulation(P, sid))[:600])
except ApiError as e: print("check failed:", str(e)[:400])
J["sim_id"] = sid; J["table_id"] = tid; J["sim_name"] = name; json.dump(J, open(f"{SP}/m12_project.json", "w"), indent=1); print("SIM", sid)
