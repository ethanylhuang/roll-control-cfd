"""ss_repoint_new_copies.py <set>: for every geometry in flow_regions_<set>.json, find FULL_SNAPPY_HEX_MESH ops (Workbench copies) not yet
recorded in sweep_mesh_ops_<set>.txt, re-point them to the geometry's walls (ss_repoint_mesh_op.py) and record them."""
import os, sys, json, subprocess
sys.path.insert(0, os.path.expanduser("~/.claude/skills/cfd-sweep/scripts"))
from simscale_api import SimScale
api = SimScale(); COPY = "1269879333705405039"; SP = os.path.dirname(os.path.abspath(__file__)); sset = sys.argv[1]
os.environ["SS_SET"] = sset
flow = json.load(open(f"{SP}/flow_regions_{sset}.json")); gid2tag = {v["geometry_id"]: k for k, v in flow.items()}
rec = f"{SP}/sweep_mesh_ops_{sset}.txt"; done = dict(l.split() for l in open(rec).read().splitlines() if l.strip()) if os.path.exists(rec) else {}
for o in api.embedded(f"/projects/{COPY}/meshoperations", limit=300):
    full = api.mesh_op(COPY, o["meshOperationId"]); tag = gid2tag.get(full.get("geometryId"))
    if tag and full["model"].get("type") == "FULL_SNAPPY_HEX_MESH" and tag not in done:
        out = subprocess.run([sys.executable, f"{SP}/ss_repoint_mesh_op.py", full["meshOperationId"], tag, "--name", f"{tag} cfd mesh (coarse settings from Mesh 48 lineage)"], capture_output=True, text=True, env=dict(os.environ, SS_SET=sset))
        print(tag, full["meshOperationId"][:8], "->", [l for l in out.stdout.splitlines() if l.startswith("updated") or l.startswith("estimate")][:2], out.stderr[-200:] if out.returncode else "")
        if out.returncode == 0:
            open(rec, "a").write(f"{tag} {full['meshOperationId']}\n"); done[tag] = full["meshOperationId"]
print("recorded:", sorted(done))
