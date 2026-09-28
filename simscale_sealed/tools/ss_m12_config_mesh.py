"""ss_m12_config_mesh.py <op_id> [--bg -0.7,-0.7,-4.5,0.7,0.7,2.1] [--res 25,25,118] [--wake x0,y0,z0,x1,y1,z1] [--procs 64]
Configure a Workbench-made mesh-op copy (which carries the material point) in the M1.2 project to the sweep's d15 sealed FINE
settings (simscale_sealed/m12_fine_meshop_from_sweep_d15.json): same castellated/snap/layer/quality controls and refinements,
entity lists re-pointed to the new flow region (body-face rule as ss_config_fine_sealed.py), new box primitives (background,
wake region, tab box). Then Generate in the Workbench (API start of hex meshes = 500)."""
import os, sys, re, json, argparse, copy
sys.path.insert(0, os.path.expanduser("~/.claude/skills/cfd-sweep/scripts"))
from simscale_api import SimScale, ApiError
ap = argparse.ArgumentParser(); ap.add_argument("op_id"); ap.add_argument("--bg", default="-0.7,-0.7,-4.5,0.7,0.7,2.1"); ap.add_argument("--res", default="25,25,118"); ap.add_argument("--wake", required=True)
ap.add_argument("--procs", type=int, default=64); ap.add_argument("--name", default="d15 sealed FINE mesh (sweep mirror: L5 body, L6 fins+tab + tab box, 4 layers)")
a = ap.parse_args(); api = SimScale(); SP = "/Users/trasomi/dev/cfd/simscale_sealed"; J = json.load(open(f"{SP}/m12_project.json")); P = J["new_project"]; flow = J["flow"]; walls = flow["walls"]
num = lambda n: int(re.sub(r"\D", "", n.split("TE")[-1])); ws = sorted(walls, key=num); nums = [num(w) for w in ws]
steps = [nums[i + 1] - nums[i] for i in range(len(nums) - 1)]; eights = [i for i, s in enumerate(steps) if s == 8]
early = [ws[i] for i in eights if i < len(ws) // 2]; j = max(eights)
assert j >= len(ws) - 4, f"last 8-step at {j} of {len(ws)} walls: rule not applicable ({eights})"
body = early + [ws[j], ws[j + 1]]; assert len(body) == 4 and len(set(body)) == 4, f"body-face rule failed: {early} {eights}"
fins = [w for w in walls if w not in body]; print(f"{len(walls)} walls; body {body}; fins+tab {len(fins)}")
sweep = json.load(open(f"{SP}/flow_regions_sealed.json"))["d15"]
if set(sweep["walls"]) == set(walls):
    ref = json.load(open(f"{SP}/m12_fine_meshop_from_sweep_d15.json"))["model"]; sw_fins = next(r for r in ref["refinements"] if r["name"] == "Fins+tab level 6")["topologicalReference"]["entities"]
    print("wall names identical to the sweep's d15 region; sweep fins+tab list", len(sw_fins), "vs rule", len(fins), "->", "SAME" if set(sw_fins) == set(fins) else "DIFFERENT (rule kept)")
op = api.mesh_op(P, a.op_id); assert op.get("geometryId") == flow["geometry_id"], f"op geometry {op.get('geometryId')} != flow region {flow['geometry_id']}"
ref = json.load(open(f"{SP}/m12_fine_meshop_from_sweep_d15.json"))["model"]; m = copy.deepcopy(ref)
def box(name, v):
    x0, y0, z0, x1, y1, z1 = (float(t) for t in v.split(","))
    r = api.create_primitive(P, {"type": "CARTESIAN_BOX", "name": name, "min": {"value": {"x": x0, "y": y0, "z": z0}, "unit": "m"}, "max": {"value": {"x": x1, "y": y1, "z": z1}, "unit": "m"}})
    pid = r if isinstance(r, str) else (r.get("geometryPrimitiveId") or r.get("id")); print("primitive", name, pid, (x0, y0, z0), (x1, y1, z1)); return pid
tb = json.load(open(f"{SP}/tab_boxes_sealed.json"))["d15"]
bg = box("background box", a.bg); wk = box("wake box level 2", a.wake); tbx = box("tab box d15 sealed", ",".join(str(v) for v in tb["min"] + tb["max"]))
m["boundingBoxUuid"] = bg; x, y, z = (int(v) for v in a.res.split(",")); m["boundingBoxResolution"] = {"x": x, "y": y, "z": z}; m["numOfProcessors"] = a.procs
refs = {r["name"]: r for r in m["refinements"]}
for name in ("Surface refinement 1", "Surface refinement 2", "Inflate boundary layer 6"): refs[name]["topologicalReference"] = {"entities": walls, "sets": []}
refs["Fins+tab level 6"]["topologicalReference"] = {"entities": fins, "sets": []}
refs["Region refinement 5"]["geometryPrimitiveUuids"] = [wk]; refs["Tab box level 6 (local slotBox)"]["geometryPrimitiveUuids"] = [tbx]
op["name"] = a.name; op["model"] = m
try: api.update_mesh_op(P, op)
except ApiError as e: sys.exit("update failed: " + str(e)[:1200])
op2 = api.mesh_op(P, a.op_id); print("updated:", op2["name"], "| res", op2["model"].get("boundingBoxResolution"), "| procs", op2["model"].get("numOfProcessors"), "| refinements:", [(r["name"], len(r.get("topologicalReference", {}).get("entities", [])), r.get("geometryPrimitiveUuids")) for r in op2["model"]["refinements"]])
try: print("estimate", json.dumps(api.estimate_mesh_op(P, a.op_id))[:300])
except ApiError as e: print("estimate failed", str(e)[:200])
J["mesh_op"] = a.op_id; json.dump(J, open(f"{SP}/m12_project.json", "w"), indent=1); print("recorded mesh_op in m12_project.json")
