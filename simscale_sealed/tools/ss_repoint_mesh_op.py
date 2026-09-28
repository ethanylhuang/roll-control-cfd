"""ss_repoint_mesh_op.py <mesh_op_id> <tag> [--name NAME]: point every SURFACE / LAYER refinement of a Workbench-made mesh-op copy
at the <tag> flow region's wall faces (all faces except the 6 box faces); region refinements keep their (cloned) primitives.
Then prints the estimate. Generate must still be pressed in the Workbench."""
import os, sys, json, argparse
sys.path.insert(0, os.path.expanduser("~/.claude/skills/cfd-sweep/scripts"))
from simscale_api import SimScale, ApiError
ap = argparse.ArgumentParser(); ap.add_argument("op_id"); ap.add_argument("tag"); ap.add_argument("--name", default=None); a = ap.parse_args()
api = SimScale(); COPY = "1269879333705405039"; SP = os.path.dirname(os.path.abspath(__file__))
flow = json.load(open(f"{SP}/flow_regions_filled2.json"))[a.tag]; walls = flow["walls"]
op = api.mesh_op(COPY, a.op_id); m = op["model"]; print("op:", op["name"], "| geometry", op.get("geometryId", "")[:8], "| flow region", flow["geometry_id"][:8])
n = 0
for r in m["refinements"]:
    if r["type"] in ("SURFACE_V3", "LAYER_ADDITION"):
        r["topologicalReference"] = {"entities": walls, "sets": []}; n += 1
    elif r["type"] == "REGION_LEVELS": print("   region refinement", r["name"], "primitives", r.get("geometryPrimitiveUuids"))
op["name"] = a.name or f"{a.tag} filled2 mesh (from {op['name']})"; op["model"] = m
try: api.update_mesh_op(COPY, op)
except ApiError as e: print("update failed:", getattr(e, "body", str(e))[:1200]); sys.exit(1)
op2 = api.mesh_op(COPY, a.op_id); print("updated:", op2["name"], "|", n, "refinements re-pointed to", len(walls), "walls")
try: print("estimate", json.dumps(api.estimate_mesh_op(COPY, a.op_id))[:200])
except ApiError as e: print("estimate failed", str(e)[:200])
