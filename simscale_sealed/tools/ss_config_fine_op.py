"""ss_config_fine_op.py <tag> <op_id> [--set cfd]: turn a Workbench copy of the fine v3 mesh op into the <tag> fine mesh:
L4+L5 surface refinements and 4 layers on all walls, 'Fins+tab level 6' on walls minus the body faces (airframe/nose/boattail,
classified from the coarse mesh patch boxes in patches_<set>_<t>.json, or by the shared face names), a per-deflection tab-box
primitive (tab_boxes_<set>.json) for 'Tab box level 6', wake box kept. Generate must still be pressed in the Workbench."""
import os, sys, json, argparse
sys.path.insert(0, os.path.expanduser("~/.claude/skills/cfd-sweep/scripts"))
from simscale_api import SimScale, ApiError
ap = argparse.ArgumentParser(); ap.add_argument("tag"); ap.add_argument("op_id"); ap.add_argument("--set", default="cfd"); a = ap.parse_args()
api = SimScale(); COPY = "1269879333705405039"; SP = os.path.dirname(os.path.abspath(__file__))
flow = json.load(open(f"{SP}/flow_regions_{a.set}.json"))[a.tag]; walls = flow["walls"]; region = "B5_TE5"
short = a.tag.replace("d", "").lstrip("0") or "0"; short = ("d" + short) if not a.tag.startswith("dm") else "dm6"
pf = f"{SP}/patches_{a.set}_{short}.json"
if os.path.exists(pf):
    p = json.load(open(pf)); ks = [k for k in p if p[k]["type"] == "wall"]
    body = [k.split(region + "_")[-1] for k in ks if p[k]["max"][2] > 0.15 or (p[k]["min"][2] < 0.02 and max(abs(p[k]["min"][0]), abs(p[k]["max"][0])) > 0.025)]
    src = "patch boxes"
else:
    body = ["B5_TE2239", "B5_TE1746", "B5_TE2231", "B5_TE1731"]; src = "shared face names (unverified for this tag)"
missing = [b for b in body if b not in walls]
if missing: sys.exit(f"body faces not in the wall list: {missing}")
fins = [w for w in walls if w not in body]
print(f"{a.tag}: {len(walls)} walls, body {body} ({src}), fins+tab {len(fins)}")
op = api.mesh_op(COPY, a.op_id); m = op["model"]; refs = {r["name"]: r for r in m["refinements"]}
tb = json.load(open(f"{SP}/tab_boxes_{a.set}.json"))[a.tag]
prim = None
try:
    prim = api.create_primitive(COPY, {"type": "CARTESIAN_BOX", "name": f"tab box {a.tag}", "min": {"value": {"x": tb["min"][0], "y": tb["min"][1], "z": tb["min"][2]}, "unit": "m"}, "max": {"value": {"x": tb["max"][0], "y": tb["max"][1], "z": tb["max"][2]}, "unit": "m"}})
    print("tab-box primitive created:", prim)
except ApiError as e:
    print("primitive creation failed, keeping the copied 10-deg tab box:", str(e)[:300])
for name in ("Surface refinement 1", "Surface refinement 2", "Inflate boundary layer 6"): refs[name]["topologicalReference"] = {"entities": walls, "sets": []}
refs["Fins+tab level 6"]["topologicalReference"] = {"entities": fins, "sets": []}
if prim: refs["Tab box level 6 (local slotBox)"]["geometryPrimitiveUuids"] = [prim if isinstance(prim, str) else prim.get("geometryPrimitiveId") or prim.get("id")]
op["name"] = f"{a.tag} cfd FINE mesh (v3 mirror: L5 body, L6 fins+tab + tab box, 4 layers)"; op["model"] = m
try: api.update_mesh_op(COPY, op)
except ApiError as e: sys.exit("update failed: " + str(e)[:800])
op2 = api.mesh_op(COPY, a.op_id); print("updated:", op2["name"], "| refinements:", [(r["name"], len(r.get("topologicalReference", {}).get("entities", [])), r.get("geometryPrimitiveUuids")) for r in op2["model"]["refinements"]])
try: print("estimate", json.dumps(api.estimate_mesh_op(COPY, a.op_id))[:220])
except ApiError as e: print("estimate failed", str(e)[:200])
open(f"{SP}/sweep_fine_ops_{a.set}.txt", "a").write(f"{a.tag} {a.op_id}\n")
