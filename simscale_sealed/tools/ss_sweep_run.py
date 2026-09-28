"""ss_sweep_run.py --mach M [--deflection 10] [--mesh <meshId>] [--base <simId>]: SimScale steady 2nd-order run with the validated settings
(linearUpwindV, fixed inlet k/omega 13.98/93500, v4 relax, p 20-300 kPa, ramp 50->V over 300 it, open sides) at a given Mach on a given mesh;
blocks until the run ends, then prints/saves the last-500 window forces + coefficients (json). Base model = sim b5476936 (fine mesh v3, 10 deg)."""
import os, sys, json, copy, argparse, time, csv, io, statistics as st
sys.path.insert(0, os.path.expanduser("~/.claude/skills/cfd-sweep/scripts"))
from simscale_api import SimScale, check_entries, ApiError
ap = argparse.ArgumentParser(); ap.add_argument("--mach", type=float, required=True); ap.add_argument("--deflection", type=float, default=10.0)
ap.add_argument("--mesh", default="efce4f58-2563-48dc-8ed6-40b461101024"); ap.add_argument("--base", default="b5476936-0b6b-426c-86d5-02ee972e2821"); ap.add_argument("--out", default=None)
a = ap.parse_args(); api = SimScale(); COPY = "1269879333705405039"
V = 305.0 if abs(a.mach - 0.9) < 1e-6 else round(a.mach * 339.1, 1)
NAME = f"SWEEP d{a.deflection:g} M{a.mach:g} FINE mesh, linearUpwindV, k/omega fixed, v4 relax, p 20-300 kPa (API)"
spec = api.simulation(COPY, a.base); m = copy.deepcopy(spec["model"])
tbl = api.import_table(COPY, f"t,ux,uy,uz\n0,0,0,-50\n300,0,0,-{V:g}\n1000000,0,0,-{V:g}\n".encode()); tid = tbl if isinstance(tbl, str) else (tbl.get("tableId") or tbl.get("id"))
inlet = next(b for b in m["boundaryConditions"] if b["type"] == "VELOCITY_INLET_V3"); inlet["velocity"]["value"]["value"]["tableId"] = tid
m["initialConditions"]["velocity"]["global"]["value"] = {"x": 0, "y": 0, "z": -50.0}
sims = api.embedded(f"/projects/{COPY}/simulations", limit=300); ex = [s for s in sims if s["name"] == NAME]
if ex: sid = ex[0]["simulationId"]; cur = api.simulation(COPY, sid); cur["model"] = m; cur["meshId"] = a.mesh; api.update_simulation(COPY, cur)
else: sid = api.post(f"/projects/{COPY}/simulations", {"name": NAME, "geometryId": spec["geometryId"], "meshId": a.mesh, "model": m, "version": spec["version"]})["simulationId"]
errs, _ = check_entries(api.check_simulation(COPY, sid))
if errs: print("check errors", errs); sys.exit(1)
runs = api.embedded(f"/projects/{COPY}/simulations/{sid}/runs", limit=50); done = [r for r in runs if r.get("status") == "FINISHED"]
if done: rid = done[-1]["runId"]; print(f"{time.strftime('%H:%M:%S')} sim {sid[:8]} already has a FINISHED run {rid[:8]} — reusing")
else:
    rid = api.start_run(COPY, sid, f"d{a.deflection:g} M{a.mach:g} sweep")["runId"]; print(f"{time.strftime('%H:%M:%S')} sim {sid[:8]} run {rid[:8]} started (V={V})", flush=True)
    while True:
        r = api.run(COPY, sid, rid); s = r.get("status")
        if s in ("FINISHED", "FAILED", "CANCELED", "ERROR"): print(f"{time.strftime('%H:%M:%S')} run {s} CPUh {(r.get('computeResource') or {}).get('value')}", flush=True); break
        time.sleep(120)
    if s != "FINISHED": sys.exit(2)
items = api.embedded(f"/projects/{COPY}/simulations/{sid}/runs/{rid}/results", limit=200)
def load(cat):
    it = [i for i in items if i.get("category") == cat]
    data = api.download(it[0]["download"]["url"]).decode("utf-8", "replace").replace("\x00", "")
    rr = [x for x in csv.reader(io.StringIO(data)) if x and x[0].strip()]
    hdr = [h.strip() for h in rr[0]]; body = []
    for x in rr[1:]:
        if len(x) < len(hdr): continue
        try: body.append([float(v) for v in x[:len(hdr)]])
        except ValueError: pass
    return {h: i for i, h in enumerate(hdr)}, body
mi, M = load("MOMENT_PLOT"); ci, F = load("FORCE_PLOT"); ri, R = load("RESIDUALS_PLOT")
w = slice(-500, None); roll = [-x[mi["TOTAL_MOMENT_Z"]] for x in M[w]]
res = dict(deflection=a.deflection, mach=a.mach, V_mps=V, sim=sid, run=rid, n_iterations=len(M),
           moments_Nm=dict(Mroll=st.mean(roll), Mpitch=st.mean(x[mi["TOTAL_MOMENT_Y"]] for x in M[w]), Myaw=st.mean(x[mi["TOTAL_MOMENT_X"]] for x in M[w])),
           forces_N=dict(Fx=st.mean(x[ci["TOTAL_FORCE_X"]] for x in F[w]), Fy=st.mean(x[ci["TOTAL_FORCE_Y"]] for x in F[w]), Fz=st.mean(x[ci["TOTAL_FORCE_Z"]] for x in F[w])),
           convergence=dict(std_rel_pct=100 * st.pstdev(roll) / abs(st.mean(roll)) if st.mean(roll) else 0, drift_pct=100 * abs(st.mean(roll[-125:]) - st.mean(roll[:125])) / abs(st.mean(roll)) if st.mean(roll) else 0, p_residual=R[-1][ri["p"]] if R else None),
           mesh_name="SimScale fine v3 (1.60M, local-mirror)", cofr_z=0.399)
res["convergence"]["flags"] = ([f"mroll_drift({res['convergence']['drift_pct']:.1f}%)"] if res["convergence"]["drift_pct"] > 3 else []) + ([f"mroll_noisy(std={res['convergence']['std_rel_pct']:.1f}%)"] if res["convergence"]["std_rel_pct"] > 5 else [])
out = a.out or os.path.join(os.path.dirname(os.path.abspath(__file__)), f"ss_sweep_d{a.deflection:g}_M{a.mach:g}.json"); json.dump(res, open(out, "w"), indent=2)
print(json.dumps({k: res[k] for k in ("moments_Nm", "forces_N", "convergence")})); print("RESULT", out)
