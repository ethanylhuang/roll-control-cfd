"""ss_config_new_sealed_copies.py [--res X,Y,Z --record refined] [--tags d03,...]: find Workbench copies of the fine v3 op (they carry a
'Fins+tab level 6' refinement) on the sealed geometries that are not yet recorded in sweep_<record>_ops_sealed.txt, and configure them with
ss_config_fine_sealed.py (fine: default resolution; refined: --res 36,36,169)."""
import os, sys, json, subprocess, argparse
sys.path.insert(0, os.path.expanduser("~/.claude/skills/cfd-sweep/scripts"))
from simscale_api import SimScale
ap = argparse.ArgumentParser(); ap.add_argument("--res", default=None); ap.add_argument("--record", default="fine"); ap.add_argument("--tags", default=None); a = ap.parse_args()
api = SimScale(); COPY = "1269879333705405039"; SP = "/Users/trasomi/dev/cfd/simscale_sealed"
flow = json.load(open(f"{SP}/flow_regions_sealed.json")); gid2tag = {v["geometry_id"]: k for k, v in flow.items()}
recorded = set()
for rec in ("fine", "refined"):
    p = f"{SP}/sweep_{rec}_ops_sealed.txt"
    if os.path.exists(p): recorded |= {l.split()[1] for l in open(p).read().splitlines() if l.strip()}
done_tags = {l.split()[0] for l in open(f"{SP}/sweep_{a.record}_ops_sealed.txt").read().splitlines() if l.strip()} if os.path.exists(f"{SP}/sweep_{a.record}_ops_sealed.txt") else set()
want = set(a.tags.split(",")) if a.tags else set(flow)
for o in api.embedded(f"/projects/{COPY}/meshoperations", limit=400):
    if o["meshOperationId"] in recorded: continue
    full = api.mesh_op(COPY, o["meshOperationId"]); tag = gid2tag.get(full.get("geometryId"))
    if not tag or tag not in want or tag in done_tags or full["model"].get("type") != "FULL_SNAPPY_HEX_MESH": continue
    if "Fins+tab level 6" not in [r.get("name") for r in full["model"].get("refinements", [])]: continue
    if full.get("status") not in (None, "READY", "CREATED") and full.get("meshId"): continue
    cmd = [sys.executable, f"{SP}/tools/ss_config_fine_sealed.py", tag, full["meshOperationId"], "--record", a.record] + (["--res", a.res] if a.res else [])
    out = subprocess.run(cmd, capture_output=True, text=True)
    print(tag, full["meshOperationId"][:8], full.get("status"), "->", "\n   ".join(out.stdout.strip().splitlines()[-3:]), out.stderr[-300:] if out.returncode else "")
    if out.returncode == 0: done_tags.add(tag)
print(f"{a.record} ops recorded:", sorted(done_tags))
