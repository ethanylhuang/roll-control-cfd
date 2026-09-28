"""ss_config_new_fine_copies.py <set>: find Workbench copies of the fine v3 op (have a 'Fins+tab level 6' refinement) on the <set> geometries
that are not yet recorded in sweep_fine_ops_<set>.txt, and configure them with ss_config_fine_op.py."""
import os, sys, json, subprocess
sys.path.insert(0, os.path.expanduser("~/.claude/skills/cfd-sweep/scripts"))
from simscale_api import SimScale
api = SimScale(); COPY = "1269879333705405039"; SP = os.path.dirname(os.path.abspath(__file__)); sset = sys.argv[1]
flow = json.load(open(f"{SP}/flow_regions_{sset}.json")); gid2tag = {v["geometry_id"]: k for k, v in flow.items()}
rec = f"{SP}/sweep_fine_ops_{sset}.txt"; done = dict(l.split() for l in open(rec).read().splitlines() if l.strip()) if os.path.exists(rec) else {}
for o in api.embedded(f"/projects/{COPY}/meshoperations", limit=300):
    full = api.mesh_op(COPY, o["meshOperationId"]); tag = gid2tag.get(full.get("geometryId"))
    if not tag or full["model"].get("type") != "FULL_SNAPPY_HEX_MESH" or tag in done: continue
    names = [r.get("name") for r in full["model"].get("refinements", [])]
    if "Fins+tab level 6" not in names: continue
    out = subprocess.run([sys.executable, f"{SP}/ss_config_fine_op.py", tag, full["meshOperationId"], "--set", sset], capture_output=True, text=True)
    print(tag, full["meshOperationId"][:8], "->", "\n   ".join(out.stdout.strip().splitlines()[-3:]), out.stderr[-300:] if out.returncode else "")
    if out.returncode == 0: done[tag] = full["meshOperationId"]
print("fine ops recorded:", sorted(done))
