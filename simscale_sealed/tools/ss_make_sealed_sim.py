"""ss_make_sealed_sim.py <tag>: per-deflection base simulation on the sealed flow region: model copied from the old 'dXX cfd base sim'
(fine-sweep settings: linearUpwindV, fixed inlet turbulence, v4 relax, 20-300 kPa, ramp table, open sides), BCs / force monitors
re-pointed by face role (inlet Max Z, outlet Min Z, sides +-X/+-Y, walls = rest). Records the id in sweep_bases_sealed.json."""
import os, sys, json, copy
sys.path.insert(0, os.path.expanduser("~/.claude/skills/cfd-sweep/scripts"))
from simscale_api import SimScale, ApiError
api = SimScale(); COPY = "1269879333705405039"; SP = "/Users/trasomi/dev/cfd/simscale_sealed"; tag = sys.argv[1]
OLD_BASE = {"d00": "6f746ff9-59d1-421d-9ebf-0206956e158e", "d03": "211a48e4-cf5b-4f6a-8af2-73474cd4524d", "d06": "0015652e-ab2c-4a81-9f82-086670ae14db", "d09": "11541749-4568-4559-9b63-3e111743834f", "d12": "9afd9844-d7ff-403c-bf4b-451fe96a1a05", "d15": "8769b659-ef09-4abd-9880-e52aeb51cc85", "dm06": "73b003c4-11dd-41fb-85c2-1df6a4b8440e", "d10": "211a48e4-cf5b-4f6a-8af2-73474cd4524d"}
flow = json.load(open(f"{SP}/flow_regions_sealed.json"))[tag]; gid = flow["geometry_id"]; box = flow["box"]; walls = flow["walls"]
inlet = [box["Max Z@Flow region"]]; outlet = [box["Min Z@Flow region"]]; sides = [box[k + "@Flow region"] for k in ("Max X", "Min X", "Max Y", "Min Y")]
spec = api.simulation(COPY, OLD_BASE[tag]); m = copy.deepcopy(spec["model"])
def repoint(h, ents): h["topologicalReference"] = {"entities": ents, "sets": []}
for bc in m["boundaryConditions"]:
    t = bc["type"]; n = bc["name"].lower()
    if t.startswith("VELOCITY_INLET"): repoint(bc, inlet)
    elif t.startswith("PRESSURE_OUTLET") and "side" in n: repoint(bc, sides)
    elif t.startswith("PRESSURE_OUTLET"): repoint(bc, outlet)
    elif t.startswith("WALL"): repoint(bc, walls)
    else: print("unhandled BC", t, bc["name"])
for fl in m["materials"]["fluids"]: repoint(fl, [flow["region"]])
for fm in (m.get("resultControl", {}).get("forcesMoments") or []): repoint(fm, walls)
for key in ("surfaceData", "probePoints"):
    for sd in (m.get("resultControl", {}).get(key) or []):
        if "topologicalReference" in sd: repoint(sd, walls)
name = f"{tag} sealed base sim (fine model, walls {len(walls)})"
sims = api.embedded(f"/projects/{COPY}/simulations", limit=300); ex = [s for s in sims if s["name"] == name]
body = {"name": name, "geometryId": gid, "model": m, "version": spec["version"]}
if ex:
    sid = ex[0]["simulationId"]; cur = api.simulation(COPY, sid); cur["model"] = m; cur["geometryId"] = gid; api.update_simulation(COPY, cur); print("updated", sid)
else:
    try: sid = api.post(f"/projects/{COPY}/simulations", body)["simulationId"]; print("created", sid)
    except ApiError as e: print("create failed:", getattr(e, "body", str(e))[:1500]); sys.exit(1)
g = api.simulation(COPY, sid)
print("geometry", g["geometryId"][:8], "| material", [f["topologicalReference"]["entities"] for f in g["model"]["materials"]["fluids"]], "| BCs:", [(b["name"], len(b["topologicalReference"]["entities"])) for b in g["model"]["boundaryConditions"]], "| force sets:", [(f["name"], len(f["topologicalReference"]["entities"])) for f in g["model"]["resultControl"].get("forcesMoments", [])])
p = f"{SP}/sweep_bases_sealed.json"; bases = json.load(open(p)) if os.path.exists(p) else {}; bases[tag] = sid; json.dump(bases, open(p, "w"), indent=1)
print("SIM", sid)
