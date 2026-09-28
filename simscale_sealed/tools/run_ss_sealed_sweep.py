"""run_ss_sealed_sweep.py --machs 0.3,0.7 [--tags d03,...] [--meshset fine|refined] [--name q] [--sheet]: SimScale sealed-tab deflection x Mach
queue. Mach-major; waits for each tag's mesh op (sweep_<meshset>_ops_sealed.txt) to FINISH; result json per point in results/; skips existing."""
import os, sys, json, time, argparse, subprocess
sys.path.insert(0, os.path.expanduser("~/.claude/skills/cfd-sweep/scripts"))
from simscale_api import SimScale
SP = "/Users/trasomi/dev/cfd/simscale_sealed"; COPY = "1269879333705405039"
DEFL = {"d00": 0, "d03": 3, "d06": 6, "d09": 9, "d12": 12, "d15": 15, "dm06": -6, "d10": 10}
ap = argparse.ArgumentParser(); ap.add_argument("--machs", required=True); ap.add_argument("--tags", default="d03,d06,d09,d12,d15,dm06,d10,d00"); ap.add_argument("--meshset", default="fine"); ap.add_argument("--name", default="q"); ap.add_argument("--sheet", action="store_true"); ap.add_argument("--procs", type=int, default=None); ap.add_argument("--relax-h", type=float, default=None)
a = ap.parse_args(); api = SimScale()
LABEL = {"fine": "FINE sealed 1.6M", "refined": "REFINED sealed 3.2M"}[a.meshset]
bases = json.load(open(f"{SP}/sweep_bases_sealed.json")); ops = dict(l.split() for l in open(f"{SP}/sweep_{a.meshset}_ops_sealed.txt").read().splitlines() if l.strip())
os.makedirs(f"{SP}/results", exist_ok=True)
def log(msg): print(f"{time.strftime('%H:%M:%S')} [{a.name}] {msg}", flush=True)
def mesh_id(tag):
    while True:
        op = api.mesh_op(COPY, ops[tag]); s = op.get("status")
        if s == "FINISHED" and op.get("meshId"): return op["meshId"]
        if s in ("FAILED", "CANCELED", "ERROR"): raise SystemExit(f"mesh op for {tag} is {s}")
        log(f"mesh {tag} {s}; waiting"); time.sleep(180)
for m in [float(x) for x in a.machs.split(",")]:
    for tag in a.tags.split(","):
        if tag not in ops: log(f"skip {tag}: no {a.meshset} mesh op recorded"); continue
        d = DEFL[tag]; out = f"{SP}/results/ss_sweep_{tag}_M{m:g}_{a.meshset}_sealed" + (f"_h{a.relax_h:g}" if a.relax_h else "") + ".json"
        if os.path.exists(out): log(f"skip {tag} M{m:g} (exists)"); continue
        mid = mesh_id(tag); log(f"start {tag} (d{d}) M{m:g} mesh {mid[:8]} base {bases[tag][:8]}")
        for attempt in range(12):
            lg = out.replace(".json", ".log")
            cmd = ["/Users/trasomi/dev/cfd/venv/bin/python", "-u", f"{SP}/tools/ss_sweep_run_sealed.py", "--mach", f"{m:g}", "--deflection", f"{d}", "--mesh", mid, "--base", bases[tag], "--label", LABEL, "--out", out] + (["--procs", str(a.procs)] if a.procs else []) + (["--relax-h", str(a.relax_h)] if a.relax_h else [])
            rc = subprocess.run(cmd, stdout=open(lg, "a"), stderr=subprocess.STDOUT, cwd="/Users/trasomi/dev/cfd").returncode
            if rc == 0: break
            log(f"{tag} M{m:g} attempt {attempt+1} rc={rc}: {open(lg).read().strip().splitlines()[-1][:200]}")
            if rc == 2 and attempt >= 1: break
            time.sleep(600)
        if os.path.exists(out):
            r = json.load(open(out)); c = r["convergence"]
            log(f"done {tag} M{m:g}: Mroll {r['moments_Nm']['Mroll']:.4f} Myaw {r['moments_Nm']['Myaw']:.3f} Fz {r['forces_N']['Fz']:.1f} block_std {c['block_std_pct']:.1f}% drift {c['drift_pct']:.1f}% {c['flags']}")
            if a.sheet:
                fs = subprocess.run(["/Users/trasomi/dev/cfd/venv/bin/python", "/Users/trasomi/dev/cfd/fill_coeff_row_ss_sealed.py", out], capture_output=True, text=True, cwd="/Users/trasomi/dev/cfd"); log("sheet: " + (fs.stdout.strip() or fs.stderr.strip()[-200:]))
        else: log(f"FAILED {tag} M{m:g}: no result")
log("QUEUE DONE")
