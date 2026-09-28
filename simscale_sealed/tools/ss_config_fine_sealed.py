"""ss_config_fine_sealed.py <tag> <op_id> [--res 25,25,118] [--name-suffix S]: configure a Workbench copy of the fine v3 op on the sealed
<tag> flow region: L4+L5 surface refinements and the 4-layer inflation on all walls, 'Fins+tab level 6' on walls minus the 4 body faces,
a per-deflection tab-box primitive for 'Tab box level 6', optional background resolution override (refined grid check).
Body-face rule (validated on the old d00/d03/d15/dm06 sets): sort wall names by their TE number; curved faces consume 8 ids instead of 7,
and the body = the two early 8-step faces (boattail cone + aft face) + the last two faces (airframe cylinder + nose). Verify in the Workbench."""
import os, sys, re, json, argparse
sys.path.insert(0, os.path.expanduser("~/.claude/skills/cfd-sweep/scripts"))
from simscale_api import SimScale, ApiError
ap = argparse.ArgumentParser(); ap.add_argument("tag"); ap.add_argument("op_id"); ap.add_argument("--res", default=None); ap.add_argument("--name-suffix", default=""); ap.add_argument("--record", default="fine")
a = ap.parse_args(); api = SimScale(); COPY = "1269879333705405039"; SP = "/Users/trasomi/dev/cfd/simscale_sealed"
flow = json.load(open(f"{SP}/flow_regions_sealed.json"))[a.tag]; walls = flow["walls"]
num = lambda n: int(re.sub(r"\D", "", n.split("TE")[-1])); ws = sorted(walls, key=num); nums = [num(w) for w in ws]
steps = [nums[i + 1] - nums[i] for i in range(len(nums) - 1)]
eights = [i for i, s in enumerate(steps) if s == 8]
early = [ws[i] for i in eights if i < len(ws) // 2]
j = max(eights)   # the airframe cylinder (curved) is the last 8-step; the nose follows it; d00 has two extra tab faces after that
assert j >= len(ws) - 4, f"last 8-step at {j} of {len(ws)} walls: rule not applicable ({eights})"
body = early + [ws[j], ws[j + 1]]
assert len(body) == 4 and len(set(body)) == 4, f"body-face rule failed: early 8-steps {early}, all 8-steps at {eights}"
fins = [w for w in walls if w not in body]
print(f"{a.tag}: {len(walls)} walls; body {body} (positions {[ws.index(b) for b in body]}); fins+tab {len(fins)}")
op = api.mesh_op(COPY, a.op_id); m = op["model"]; refs = {r["name"]: r for r in m["refinements"]}
assert op.get("geometryId") == flow["geometry_id"], f"op geometry {op.get('geometryId')} != flow region {flow['geometry_id']}"
tb = json.load(open(f"{SP}/tab_boxes_sealed.json"))[a.tag]
prim = api.create_primitive(COPY, {"type": "CARTESIAN_BOX", "name": f"tab box {a.tag} sealed", "min": {"value": {"x": tb["min"][0], "y": tb["min"][1], "z": tb["min"][2]}, "unit": "m"}, "max": {"value": {"x": tb["max"][0], "y": tb["max"][1], "z": tb["max"][2]}, "unit": "m"}})
pid = prim if isinstance(prim, str) else (prim.get("geometryPrimitiveId") or prim.get("id")); print("tab-box primitive:", pid)
for name in ("Surface refinement 1", "Surface refinement 2", "Inflate boundary layer 6"): refs[name]["topologicalReference"] = {"entities": walls, "sets": []}
refs["Fins+tab level 6"]["topologicalReference"] = {"entities": fins, "sets": []}
refs["Tab box level 6 (local slotBox)"]["geometryPrimitiveUuids"] = [pid]
label = "FINE"
if a.res:
    x, y, z = (int(v) for v in a.res.split(",")); m["boundingBoxResolution"] = {"x": x, "y": y, "z": z}; label = f"REFINED {x}x{y}x{z}"
op["name"] = f"{a.tag} sealed {label} mesh (v3 mirror: L5 body, L6 fins+tab + tab box, 4 layers){a.name_suffix}"; op["model"] = m
try: api.update_mesh_op(COPY, op)
except ApiError as e: sys.exit("update failed: " + str(e)[:800])
op2 = api.mesh_op(COPY, a.op_id); print("updated:", op2["name"], "| res", op2["model"].get("boundingBoxResolution"), "| refinements:", [(r["name"], len(r.get("topologicalReference", {}).get("entities", [])), r.get("geometryPrimitiveUuids")) for r in op2["model"]["refinements"]])
try: print("estimate", json.dumps(api.estimate_mesh_op(COPY, a.op_id))[:220])
except ApiError as e: print("estimate failed", str(e)[:200])
rec = f"{SP}/sweep_{a.record}_ops_sealed.txt"; lines = [l for l in (open(rec).read().splitlines() if os.path.exists(rec) else []) if l.strip() and not l.startswith(a.tag + " ")]
open(rec, "w").write("\n".join(lines + [f"{a.tag} {a.op_id}"]) + "\n"); print("recorded in", rec)
