"""run_ss_coarse_sweep.py --machs 0.3,0.7 [--tags d00,d03,...] [--name qA]
SimScale deflection x Mach sweep on the per-deflection COARSE hex meshes (922k, 'coarse settings from Mesh 48 lineage'),
validated steady second-order settings (ss_sweep_run.py). Mach-major order so complete fixed-Mach sets land first.
Waits for each deflection's mesh to finish, runs, then fills the 'v4 coeff sweep SimScale' tab. Skips (mach, tag) pairs whose result json exists."""
import os, sys, json, time, argparse, subprocess
sys.path.insert(0, os.path.expanduser("~/.claude/skills/cfd-sweep/scripts"))
from simscale_api import SimScale
SP = "/private/tmp/claude-501/-Users-trasomi-dev-cfd/e77796e5-73f1-4b54-ac10-df1a9b566759/scratchpad"
COPY = "1269879333705405039"; SET = os.environ.get("SS_SET", "filled2"); MESHSET = os.environ.get("SS_MESHSET", "coarse")
LABEL = f"COARSE {SET} 922k" if MESHSET == "coarse" else f"FINE {SET} 1.6M"; SUFFIX = ({"filled2": "coarse2", "cfd": "coarse3"}.get(SET, "coarse_" + SET)) if MESHSET == "coarse" else f"fine_{SET}"
DEFL = {"d00": 0, "d03": 3, "d06": 6, "d09": 9, "d12": 12, "d15": 15, "dm06": -6, "d10": 10}
ap = argparse.ArgumentParser(); ap.add_argument("--machs", required=True); ap.add_argument("--tags", default="d00,d03,d06,d09,d12,d15,dm06,d10"); ap.add_argument("--name", default="q")
a = ap.parse_args(); api = SimScale()
bases = json.load(open(f"{SP}/sweep_bases{'' if SET == 'filled2' else '_' + SET}.json")); ops = dict(l.split() for l in open(f"{SP}/sweep_mesh_ops{'' if SET == 'filled2' else '_' + SET}.txt" if MESHSET == "coarse" else f"{SP}/sweep_fine_ops_{SET}.txt").read().splitlines() if l.strip())
def log(msg): print(f"{time.strftime('%H:%M:%S')} [{a.name}] {msg}", flush=True)
def mesh_id(tag):
    while True:
        op = api.mesh_op(COPY, ops[tag]); s = op.get("status")
        if s == "FINISHED" and op.get("meshId"): return op["meshId"]
        if s in ("FAILED", "CANCELED", "ERROR"): raise SystemExit(f"mesh op for {tag} is {s}")
        log(f"mesh {tag} {s}; waiting"); time.sleep(180)
for m in [float(x) for x in a.machs.split(",")]:
    for tag in a.tags.split(","):
        d = DEFL[tag]; out = f"{SP}/ss_sweep_{tag}_M{m:g}_{SUFFIX}.json"
        if os.path.exists(out): log(f"skip {tag} M{m:g} (exists)"); continue
        mid = mesh_id(tag); log(f"start {tag} (d{d}) M{m:g} mesh {mid[:8]} base {bases[tag][:8]}")
        for attempt in range(12):
            lg = f"{SP}/ss_sweep_{tag}_M{m:g}_{SUFFIX}.log"
            rc = subprocess.run(["./venv/bin/python", "-u", f"{SP}/ss_sweep_run.py", "--mach", f"{m:g}", "--deflection", f"{d}", "--mesh", mid, "--base", bases[tag], "--label", LABEL, "--out", out], stdout=open(lg, "a"), stderr=subprocess.STDOUT).returncode
            if rc == 0: break
            log(f"{tag} M{m:g} attempt {attempt+1} rc={rc}: {open(lg).read().strip().splitlines()[-1][:160]}")
            if rc == 2 and attempt >= 1: break     # run FAILED twice: give up on this point
            time.sleep(600)
        if os.path.exists(out):
            r = json.load(open(out)); c = r["convergence"]
            log(f"done {tag} M{m:g}: Mroll {r['moments_Nm']['Mroll']:.4f} Myaw {r['moments_Nm']['Myaw']:.3f} Fz {r['forces_N']['Fz']:.1f} std {c['std_rel_pct']:.1f}% drift {c['drift_pct']:.1f}% {c['flags']}")
            fs = subprocess.run(["./venv/bin/python", "fill_coeff_row_ss.py", out], capture_output=True, text=True); log("sheet: " + (fs.stdout.strip() or fs.stderr.strip()[-200:]))
        else: log(f"FAILED {tag} M{m:g}: no result")
log("QUEUE DONE")
