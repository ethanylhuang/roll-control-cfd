"""ss_m12_run.py: wait for the M1.2 project's fine mesh, attach it to the transient sim, check/estimate, create+start the run,
poll to the end, download MOMENT/FORCE/RESIDUALS plots, write simscale_sealed/results/ss_m12_transient_d15.json (+ roll trace PNG/CSV).
Transient statistics: mean over the last 25 % of the run, quarter means, std/drift over that window."""
import os, sys, json, time, csv, io, statistics as st
sys.path.insert(0, os.path.expanduser("~/.claude/skills/cfd-sweep/scripts")); from simscale_api import SimScale, check_entries, ApiError
SP = "/Users/trasomi/dev/cfd/simscale_sealed"; JP = f"{SP}/m12_project.json"; api = SimScale()
def J(): return json.load(open(JP))
def save(j): json.dump(j, open(JP, "w"), indent=1)
def log(m): print(time.strftime("%H:%M:%S"), m, flush=True)
j = J(); P = j["new_project"]; sid = j["sim_id"]; op_id = j["mesh_op"]
t0 = time.time()
while "mesh_id" not in J():
    op = api.mesh_op(P, op_id); s = op.get("status")
    if s == "FINISHED" and op.get("meshId"): j = J(); j["mesh_id"] = op["meshId"]; save(j); break
    if s in ("FAILED", "CANCELED", "ERROR"): sys.exit(f"mesh op {s}")
    if time.time() - t0 > 6 * 3600: sys.exit("mesh timeout")
    time.sleep(120)
j = J(); mesh_id = j["mesh_id"]; log(f"mesh {mesh_id} ready; attaching to sim {sid[:8]}")
cur = api.simulation(P, sid); cur["meshId"] = mesh_id; api.update_simulation(P, cur); saved = api.simulation(P, sid); assert saved["meshId"] == mesh_id
errs, warns = check_entries(api.check_simulation(P, sid)); log(f"check: {len(errs)} errors {len(warns)} warnings {errs[:3] if errs else ''} {warns[:2] if warns else ''}")
if errs: sys.exit(1)
try: log("estimate: " + json.dumps(api.estimate_simulation(P, sid))[:300])
except ApiError as e: log("estimate failed: " + str(e)[:200])
runs = api.embedded(f"/projects/{P}/simulations/{sid}/runs", limit=50); done = [r for r in runs if r.get("status") == "FINISHED"]
if done: rid = done[-1]["runId"]; log(f"reusing FINISHED run {rid[:8]}")
else:
    rid = api.create_run(P, sid, os.environ.get("M12_RUN_NAME", "sealed d15 M1.2 transient"))["runId"]; api.start_run(P, sid, rid); log(f"run {rid[:8]} started")
    j = J(); j["run_id"] = rid; save(j)
    while True:
        r = api.run(P, sid, rid); s = r.get("status")
        if s in ("FINISHED", "FAILED", "CANCELED", "ERROR"): log(f"run {s} CPUh {(r.get('computeResource') or {}).get('value')}"); break
        time.sleep(180)
    if s != "FINISHED":
        try: ev = api.request("GET", f"/projects/{P}/simulations/{sid}/runs/{rid}/eventlog", retries=1, timeout=30); print("eventlog:", [(e["severity"], e["message"][:160]) for e in ev["entries"] if e["severity"] in ("ERROR", "WARNING")])
        except Exception as e: print("eventlog unavailable", e)
        sys.exit(2)
items = api.embedded(f"/projects/{P}/simulations/{sid}/runs/{rid}/results", limit=200)
def load(cat):
    it = [i for i in items if i.get("category") == cat]
    if not it: return {}, []
    data = api.download(it[0]["download"]["url"]).decode("utf-8", "replace").replace("\x00", "")
    rr = [x for x in csv.reader(io.StringIO(data)) if x and x[0].strip()]
    hdr = [h.strip() for h in rr[0]]; body = []
    for x in rr[1:]:
        if len(x) < len(hdr): continue
        try: body.append([float(v) for v in x[:len(hdr)]])
        except ValueError: pass
    return {h: i for i, h in enumerate(hdr)}, body
mi, M = load("MOMENT_PLOT"); ci, F = load("FORCE_PLOT"); ri, R = load("RESIDUALS_PLOT")
log(f"moment rows {len(M)} cols {list(mi)[:6]}")
tcol_name = next((k for k in mi if k.upper().startswith("TIME")), list(mi)[0]); t = [x[mi[tcol_name]] for x in M]
roll = [-x[mi["TOTAL_MOMENT_Z"]] for x in M]; n = len(roll); tw = t[-1] - 0.25 * (t[-1] - t[0]); w = max(sum(1 for tt in t if tt >= tw), 10); wr = roll[-w:]; mean = st.mean(wr); den = abs(mean) or 1e-12
quarters = [st.mean(wr[i * len(wr) // 4:(i + 1) * len(wr) // 4]) for i in range(4)]
res = dict(deflection=15.0, mach=1.2, V_mps=406.9, project=P, sim=sid, run=rid, n_rows=n, t_last=t[-1], window=dict(t_start=t[-w], t_end=t[-1], n=w),
           moments_Nm=dict(Mroll=mean, Mpitch=st.mean(x[mi["TOTAL_MOMENT_Y"]] for x in M[-w:]), Myaw=st.mean(x[mi["TOTAL_MOMENT_X"]] for x in M[-w:])),
           forces_N=dict(Fx=st.mean(x[ci["TOTAL_FORCE_X"]] for x in F[-w:]), Fy=st.mean(x[ci["TOTAL_FORCE_Y"]] for x in F[-w:]), Fz=st.mean(x[ci["TOTAL_FORCE_Z"]] for x in F[-w:])) if F else None,
           convergence=dict(std_rel_pct=100 * st.pstdev(wr) / den, drift_pct=100 * abs(quarters[-1] - quarters[0]) / den, quarter_means=quarters, roll_min=min(wr), roll_max=max(wr),
                            p_residual_last=(R[-1][ri["p"]] if R and "p" in ri else None)),
           solver="SimScale compressible transient (Euler, PIMPLE 2x2, dt 4e-6, ramp 1.5 ms), sealed d15 fine mesh 25x25x118 mirror", cofr_z=0.399)
os.makedirs(f"{SP}/results", exist_ok=True); out = f"{SP}/results/ss_m12_transient_d15.json"; json.dump(res, open(out, "w"), indent=2)
with open(f"{SP}/results/ss_m12_transient_d15_trace.csv", "w") as f:
    f.write("t,Mroll,Mpitch,Myaw\n"); [f.write(f"{tt},{-x[mi['TOTAL_MOMENT_Z']]},{x[mi['TOTAL_MOMENT_Y']]},{x[mi['TOTAL_MOMENT_X']]}\n") for tt, x in zip(t, M)]
try:
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(10, 4)); ax.plot([tt * 1e3 for tt in t], roll, lw=0.8); ax.axhline(mean, ls="--", color="tab:red", label=f"last-25 % mean {mean:.3f} N·m")
    ax.set_xlabel("t (ms)"); ax.set_ylabel("roll moment (N·m)"); ax.set_title("SimScale sealed 15° / M1.2 transient: total roll moment"); ax.grid(alpha=0.3); ax.legend(); fig.tight_layout(); fig.savefig(f"{SP}/results/ss_m12_transient_d15_trace.png", dpi=120)
except Exception as e: log(f"plot failed: {e}")
print(json.dumps({k: res[k] for k in ("t_last", "window", "moments_Nm", "forces_N", "convergence")}, indent=1)); print("RESULT", out)
