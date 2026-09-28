"""ss_m12_steady.py [--mach 1.2] [--endtime 3000] [--window 1500] [--procs 32] [--relax-h 0.7]
STEADY SimScale run at M1.2 in the M1.2 project with the sweep recipe verbatim (sealed d15 base spec re-pointed to the new flow
region, iteration ramp table 50 -> V over 300 it, linearUpwindV, v4 relaxation, p 20-300 kPa, open sides), attached to the fine mesh.
Creates/updates the sim, runs it, and writes simscale_sealed/results/ss_m12_steady_d15.json (last-window mean, 250-block scatter)."""
import os, sys, json, copy, argparse, time, csv, io, statistics as st
sys.path.insert(0, os.path.expanduser("~/.claude/skills/cfd-sweep/scripts")); from simscale_api import SimScale, check_entries, ApiError
ap = argparse.ArgumentParser(); ap.add_argument("--mach", type=float, default=1.2); ap.add_argument("--endtime", type=int, default=3000); ap.add_argument("--window", type=int, default=1500); ap.add_argument("--procs", type=int, default=32); ap.add_argument("--relax-h", type=float, default=None); ap.add_argument("--ramp-iters", type=int, default=300); ap.add_argument("--tmin", type=float, default=None); ap.add_argument("--tmax", type=float, default=None); ap.add_argument("--rhomin", type=float, default=None); ap.add_argument("--rhomax", type=float, default=None); ap.add_argument("--upwind", action="store_true", help="first-order bounded upwind for momentum (robustness)")
a = ap.parse_args(); api = SimScale(); SP = "/Users/trasomi/dev/cfd/simscale_sealed"; J = json.load(open(f"{SP}/m12_project.json")); P = J["new_project"]; flow = J["flow"]; mesh_id = J["mesh_id"]
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
for fl in m["materials"]["fluids"]: repoint(fl, [flow["region"]])
for fm in (m.get("resultControl", {}).get("forcesMoments") or []): repoint(fm, walls)
tid = api.import_table(P, f"t,ux,uy,uz\n0,0,0,-50\n{a.ramp_iters},0,0,-{V:g}\n1000000,0,0,-{V:g}\n".encode())
inl = next(b for b in m["boundaryConditions"] if b["type"].startswith("VELOCITY_INLET")); inl["velocity"]["value"]["value"]["tableId"] = tid
m["initialConditions"]["velocity"]["global"]["value"] = {"x": 0, "y": 0, "z": -50.0}
m["simulationControl"]["endTime"] = {"value": a.endtime, "unit": "s"}; m["simulationControl"]["numProcessors"] = a.procs
if a.relax_h: m["numerics"]["relaxationFactor"]["enthalpyEquation"] = a.relax_h
fl = m["numerics"].setdefault("stabilization", {}).setdefault("fieldLimits", {})
if a.tmin: fl["lowerTemperatureBound"] = {"value": a.tmin, "unit": "K"}
if a.tmax: fl["upperTemperatureBound"] = {"value": a.tmax, "unit": "K"}
if a.rhomin: fl["lowerDensityBound"] = {"value": a.rhomin, "unit": "kg/m³"}
if a.rhomax: fl["upperDensityBound"] = {"value": a.rhomax, "unit": "kg/m³"}
lim = (f", T {a.tmin:g}-{a.tmax:g} K" if a.tmin else "") + (f", rho {a.rhomin:g}-{a.rhomax:g}" if a.rhomin else "") + (", 1st-order upwind U" if a.upwind else "")
if a.upwind: m["numerics"]["schemes"]["divergence"]["div_Phi_velocity"] = {"type": "BOUNDED_GAUSS_UPWIND"}
scheme_name = "upwind" if a.upwind else "linearUpwindV"
name = f"SEALED STEADY d15 M{a.mach:g} (sweep recipe: ramp 50->{V:g} over {a.ramp_iters} it, {scheme_name}, v4 relax, p 20-300 kPa{f', h {a.relax_h:g}' if a.relax_h else ''}{lim}, API)"
sims = api.embedded(f"/projects/{P}/simulations", limit=300); ex = [s for s in sims if s["name"] == name]
if ex: sid = ex[0]["simulationId"]; cur = api.simulation(P, sid); cur["model"] = m; cur["meshId"] = mesh_id; cur["geometryId"] = gid; api.update_simulation(P, cur); print("updated", sid)
else: sid = api.post(f"/projects/{P}/simulations", {"name": name, "geometryId": gid, "meshId": mesh_id, "model": m, "version": spec["version"]})["simulationId"]; print("created", sid)
errs, warns = check_entries(api.check_simulation(P, sid)); print("check errors", errs, "warnings", len(warns))
if errs: sys.exit(1)
J["steady_sim_id"] = sid; json.dump(J, open(f"{SP}/m12_project.json", "w"), indent=1)
runs = api.embedded(f"/projects/{P}/simulations/{sid}/runs", limit=50); done = [r for r in runs if r.get("status") == "FINISHED"]
if done: rid = done[-1]["runId"]; print("reusing FINISHED run", rid[:8])
else:
    rid = api.create_run(P, sid, f"sealed d15 M{a.mach:g} steady (sweep recipe)")["runId"]; api.start_run(P, sid, rid); print(time.strftime("%H:%M:%S"), "steady run", rid[:8], "started", flush=True)
    J["steady_run_id"] = rid; json.dump(J, open(f"{SP}/m12_project.json", "w"), indent=1)
    while True:
        r = api.run(P, sid, rid); s = r.get("status")
        if s in ("FINISHED", "FAILED", "CANCELED", "ERROR"): print(time.strftime("%H:%M:%S"), "steady run", s, "CPUh", (r.get("computeResource") or {}).get("value"), flush=True); break
        time.sleep(180)
    if s != "FINISHED":
        try: ev = api.request("GET", f"/projects/{P}/simulations/{sid}/runs/{rid}/eventlog", retries=1, timeout=30); print("eventlog:", [(e["severity"], e["message"][:200]) for e in ev["entries"] if e["severity"] == "ERROR"])
        except Exception as e: print("eventlog unavailable", e)
        sys.exit(2)
items = api.embedded(f"/projects/{P}/simulations/{sid}/runs/{rid}/results", limit=200)
def load(cat):
    it = [i for i in items if i.get("category") == cat]
    data = api.download(it[0]["download"]["url"]).decode("utf-8", "replace").replace("\x00", ""); rr = [x for x in csv.reader(io.StringIO(data)) if x and x[0].strip()]
    hdr = [h.strip() for h in rr[0]]; body = []
    for x in rr[1:]:
        if len(x) < len(hdr): continue
        try: body.append([float(v) for v in x[:len(hdr)]])
        except ValueError: pass
    return {h: i for i, h in enumerate(hdr)}, body
mi, M = load("MOMENT_PLOT"); ci, F = load("FORCE_PLOT"); ri, R = load("RESIDUALS_PLOT")
w = min(a.window, len(M)); roll = [-x[mi["TOTAL_MOMENT_Z"]] for x in M[-w:]]; mean = st.mean(roll); den = abs(mean) or 1e-12
blocks = [st.mean(roll[i:i + 250]) for i in range(0, len(roll) - 249, 250)]; block_std = 100 * st.pstdev(blocks) / den if len(blocks) > 1 else float("nan"); drift = 100 * abs(st.mean(roll[-w // 4:]) - st.mean(roll[:w // 4])) / den; sl = slice(-w, None)
res = dict(deflection=15.0, mach=a.mach, V_mps=V, project=P, sim=sid, run=rid, n_iterations=len(M), moments_Nm=dict(Mroll=mean, Mpitch=st.mean(x[mi["TOTAL_MOMENT_Y"]] for x in M[sl]), Myaw=st.mean(x[mi["TOTAL_MOMENT_X"]] for x in M[sl])),
           forces_N=dict(Fx=st.mean(x[ci["TOTAL_FORCE_X"]] for x in F[sl]), Fy=st.mean(x[ci["TOTAL_FORCE_Y"]] for x in F[sl]), Fz=st.mean(x[ci["TOTAL_FORCE_Z"]] for x in F[sl])),
           convergence=dict(std_rel_pct=100 * st.pstdev(roll) / den, block_std_pct=block_std, block_means=blocks, drift_pct=drift, window=w, p_residual=(R[-1][ri["p"]] if R and "p" in ri else None)), mesh_name="SimScale FINE sealed 1.6M (M1.2 project)", cofr_z=0.399)
res["convergence"]["flags"] = ([f"mroll_drift({drift:.1f}%)"] if drift > 3 else []) + ([f"mroll_noisy(block_std={block_std:.1f}%)"] if block_std > 3 else [])
os.makedirs(f"{SP}/results", exist_ok=True); out = f"{SP}/results/ss_m12_steady_d15.json"; json.dump(res, open(out, "w"), indent=2); print(json.dumps({k: res[k] for k in ("moments_Nm", "forces_N", "convergence")})); print("RESULT", out)
