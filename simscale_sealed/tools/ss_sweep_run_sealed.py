"""ss_sweep_run_sealed.py --mach M --deflection D --mesh <meshId> --base <simId> --label L --out <json>: one SimScale steady 2nd-order run on
the sealed geometry (model = the tag's sealed base sim: linearUpwindV, fixed inlet k/omega, v4 relax, p 20-300 kPa, open sides) with a
per-Mach inlet ramp table (50 -> V over 300 it), endTime 3000. Blocks until the run ends; reports the last-1500-iteration mean with
250-iteration block scatter (block_std_pct) and first/last-quarter drift; flags mroll_noisy if block scatter > 3 %, mroll_drift if drift > 3 %."""
import os, sys, json, copy, argparse, time, csv, io, statistics as st
sys.path.insert(0, os.path.expanduser("~/.claude/skills/cfd-sweep/scripts"))
from simscale_api import SimScale, check_entries, ApiError
ap = argparse.ArgumentParser(); ap.add_argument("--mach", type=float, required=True); ap.add_argument("--deflection", type=float, required=True)
ap.add_argument("--mesh", required=True); ap.add_argument("--base", required=True); ap.add_argument("--label", default="FINE sealed 1.6M"); ap.add_argument("--out", required=True)
ap.add_argument("--endtime", type=int, default=3000); ap.add_argument("--window", type=int, default=1500); ap.add_argument("--procs", type=int, default=None); ap.add_argument("--relax-h", type=float, default=None, help="enthalpy relaxation override (startup survival on refined meshes; converged mean unaffected)")
a = ap.parse_args(); api = SimScale(); COPY = "1269879333705405039"
V = 305.0 if abs(a.mach - 0.9) < 1e-6 else round(a.mach * 339.1, 1)
if a.relax_h: a.label = a.label + f" h{a.relax_h:g}"
NAME = f"SEALED {a.label} d{a.deflection:g} M{a.mach:g} (linearUpwindV, k/omega fixed, v4 relax, p 20-300 kPa, API)"
spec = api.simulation(COPY, a.base); m = copy.deepcopy(spec["model"])
tbl = api.import_table(COPY, f"t,ux,uy,uz\n0,0,0,-50\n300,0,0,-{V:g}\n1000000,0,0,-{V:g}\n".encode()); tid = tbl if isinstance(tbl, str) else (tbl.get("tableId") or tbl.get("id"))
inlet = next(b for b in m["boundaryConditions"] if b["type"] == "VELOCITY_INLET_V3"); inlet["velocity"]["value"]["value"]["tableId"] = tid
m["initialConditions"]["velocity"]["global"]["value"] = {"x": 0, "y": 0, "z": -50.0}
m["simulationControl"]["endTime"] = {"value": a.endtime, "unit": "s"}
if a.procs: m["simulationControl"]["numProcessors"] = a.procs
if a.relax_h: m["numerics"]["relaxationFactor"]["enthalpyEquation"] = a.relax_h
sims = api.embedded(f"/projects/{COPY}/simulations", limit=400); ex = [s for s in sims if s["name"] == NAME]
if ex: sid = ex[0]["simulationId"]; cur = api.simulation(COPY, sid); cur["model"] = m; cur["meshId"] = a.mesh; cur["geometryId"] = spec["geometryId"]; api.update_simulation(COPY, cur)
else: sid = api.post(f"/projects/{COPY}/simulations", {"name": NAME, "geometryId": spec["geometryId"], "meshId": a.mesh, "model": m, "version": spec["version"]})["simulationId"]
saved = api.simulation(COPY, sid); assert saved["meshId"] == a.mesh and saved["model"]["boundaryConditions"][0]["velocity"]["value"]["value"].get("tableId") == tid, "spec did not save as intended"
errs, warns = check_entries(api.check_simulation(COPY, sid))
if errs: print("check errors", errs); sys.exit(1)
runs = api.embedded(f"/projects/{COPY}/simulations/{sid}/runs", limit=50); done = [r for r in runs if r.get("status") == "FINISHED"]
if done: rid = done[-1]["runId"]; print(f"{time.strftime('%H:%M:%S')} sim {sid[:8]} already has a FINISHED run {rid[:8]} on this sealed sim - reusing")
else:
    created = [r for r in runs if r.get("status") in ("READY", "CREATED") and not r.get("startedAt")]
    rid = created[-1]["runId"] if created else api.create_run(COPY, sid, f"sealed d{a.deflection:g} M{a.mach:g} {a.label}")["runId"]
    api.start_run(COPY, sid, rid); print(f"{time.strftime('%H:%M:%S')} sim {sid[:8]} run {rid[:8]} started (V={V}, mesh {a.mesh[:8]})", flush=True)
    while True:
        r = api.run(COPY, sid, rid); s = r.get("status")
        if s in ("FINISHED", "FAILED", "CANCELED", "ERROR"): print(f"{time.strftime('%H:%M:%S')} run {s} CPUh {(r.get('computeResource') or {}).get('value')}", flush=True); break
        time.sleep(120)
    if s != "FINISHED":
        try: ev = api.request("GET", f"/projects/{COPY}/simulations/{sid}/runs/{rid}/eventlog", retries=1, timeout=30); print("eventlog:", [(e["severity"], e["message"][:120]) for e in ev["entries"] if e["severity"] in ("ERROR", "WARNING")])
        except Exception as e: print("eventlog unavailable", e)
        sys.exit(2)
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
w = a.window; roll = [-x[mi["TOTAL_MOMENT_Z"]] for x in M[-w:]]; mean = st.mean(roll); den = abs(mean) or 1e-12
blocks = [st.mean(roll[i:i + 250]) for i in range(0, len(roll) - 249, 250)]
block_std = 100 * st.pstdev(blocks) / den; drift = 100 * abs(st.mean(roll[-w // 4:]) - st.mean(roll[:w // 4])) / den
sl = slice(-w, None)
res = dict(deflection=a.deflection, mach=a.mach, V_mps=V, sim=sid, run=rid, n_iterations=len(M),
           moments_Nm=dict(Mroll=mean, Mpitch=st.mean(x[mi["TOTAL_MOMENT_Y"]] for x in M[sl]), Myaw=st.mean(x[mi["TOTAL_MOMENT_X"]] for x in M[sl])),
           forces_N=dict(Fx=st.mean(x[ci["TOTAL_FORCE_X"]] for x in F[sl]), Fy=st.mean(x[ci["TOTAL_FORCE_Y"]] for x in F[sl]), Fz=st.mean(x[ci["TOTAL_FORCE_Z"]] for x in F[sl])),
           convergence=dict(std_rel_pct=100 * st.pstdev(roll) / den, block_std_pct=block_std, block_means=blocks, drift_pct=drift, window=w, p_residual=(R[-1][ri["p"]] if R and "p" in ri else None)),
           mesh_name=f"SimScale {a.label}", cofr_z=0.399, geometry="sealed tab CAD 2026-09-11")
res["convergence"]["flags"] = ([f"mroll_drift({drift:.1f}%)"] if drift > 3 else []) + ([f"mroll_noisy(block_std={block_std:.1f}%)"] if block_std > 3 else [])
json.dump(res, open(a.out, "w"), indent=2)
print(json.dumps({k: res[k] for k in ("moments_Nm", "forces_N", "convergence")})); print("RESULT", a.out)
