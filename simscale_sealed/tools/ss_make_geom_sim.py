"""ss_make_geom_sim.py <tag> [--base <simId>] [--mesh <meshId>] [--name-suffix S]: create (or update) the per-deflection SimScale
simulation on the extracted 'filled2' flow region of <tag> (d00, d03, ...): model copied from the base sim (default = coarse
089e0368: linearUpwindV, fixed inlet turbulence, v4 relax, 20-300 kPa, ramp table), every BC / force-monitor entity list re-pointed
by face role: inlet = Max Z, outlet = Min Z, sides = Max/Min X/Y, walls = all other faces. Prints the sim id (used as --base for
ss_sweep_run.py once a mesh exists)."""
import os, sys, json, copy, argparse
sys.path.insert(0, os.path.expanduser("~/.claude/skills/cfd-sweep/scripts"))
from simscale_api import SimScale, check_entries, ApiError
ap = argparse.ArgumentParser(); ap.add_argument("tag"); ap.add_argument("--base", default="089e0368-5da9-4748-92ab-b1927ad95f5e"); ap.add_argument("--mesh", default=None); ap.add_argument("--name-suffix", default="")
a = ap.parse_args(); api = SimScale(); COPY = "1269879333705405039"
SP = os.path.dirname(os.path.abspath(__file__)); flow = json.load(open(f"{SP}/flow_regions_filled2.json"))[a.tag]
gid = flow["geometry_id"]; box = flow["box"]; walls = flow["walls"]
inlet = [box["Max Z@Flow region"]]; outlet = [box["Min Z@Flow region"]]; sides = [box[k] for k in ("Max X@Flow region", "Min X@Flow region", "Max Y@Flow region", "Min Y@Flow region")]
spec = api.simulation(COPY, a.base); m = copy.deepcopy(spec["model"])
def repoint(entities_holder, ents): entities_holder["topologicalReference"] = {"entities": ents, "sets": []}
for bc in m["boundaryConditions"]:
    t = bc["type"]; n = bc["name"].lower()
    if t.startswith("VELOCITY_INLET"): repoint(bc, inlet)
    elif t.startswith("PRESSURE_OUTLET") and "side" in n: repoint(bc, sides)
    elif t.startswith("PRESSURE_OUTLET"): repoint(bc, outlet)
    elif t.startswith("WALL"): repoint(bc, walls)
    else: print("unhandled BC", t, bc["name"])
for fm in (m.get("resultControl", {}).get("forcesMoments") or []): repoint(fm, walls)
for key in ("surfaceData", "probePoints"):
    for sd in (m.get("resultControl", {}).get(key) or []):
        if "topologicalReference" in sd: repoint(sd, walls)
name = f"{a.tag} filled2 base sim ({os.path.basename(a.base)[:8]} model, walls {len(walls)}){a.name_suffix}"
sims = api.embedded(f"/projects/{COPY}/simulations", limit=300); ex = [s for s in sims if s["name"] == name]
body = {"name": name, "geometryId": gid, "model": m, "version": spec["version"]}
if a.mesh: body["meshId"] = a.mesh
if ex:
    sid = ex[0]["simulationId"]; cur = api.simulation(COPY, sid); cur["model"] = m; cur["geometryId"] = gid
    if a.mesh: cur["meshId"] = a.mesh
    api.update_simulation(COPY, cur); print("updated", sid)
else:
    try: sid = api.post(f"/projects/{COPY}/simulations", body)["simulationId"]; print("created", sid)
    except ApiError as e: print("create failed:", getattr(e, "body", str(e))[:1500]); sys.exit(1)
g = api.simulation(COPY, sid); print("geometry", g["geometryId"][:8], "mesh", (g.get("meshId") or "none")[:8], "| BCs:", [(b["name"], len(b["topologicalReference"]["entities"])) for b in g["model"]["boundaryConditions"]], "| force sets:", [(f["name"], len(f["topologicalReference"]["entities"])) for f in g["model"]["resultControl"].get("forcesMoments", [])])
if a.mesh:
    errs, warns = check_entries(api.check_simulation(COPY, sid)); print("check errors", [e.get("message") for e in errs], "warnings", [(w.get("message") or "")[:100] for w in warns])
print("SIM", sid)
