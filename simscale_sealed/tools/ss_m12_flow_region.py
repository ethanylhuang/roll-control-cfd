"""ss_m12_flow_region.py: resolve the extracted flow region of the sealed d15 geometry in the M1.2 project (by name, newest first),
verify 1 region + 6 named box faces, write simscale_sealed/m12_flow_region.json and compare wall names with the sweep's d15 set."""
import os, sys, json
sys.path.insert(0, os.path.expanduser("~/.claude/skills/cfd-sweep/scripts"))
from simscale_api import SimScale
api = SimScale(); SP = "/Users/trasomi/dev/cfd/simscale_sealed"; J = json.load(open(f"{SP}/m12_project.json")); P = J["new_project"]
BOX = ["Max X", "Min X", "Max Y", "Min Y", "Max Z", "Min Z"]
geoms = [g for g in api.embedded(f"/projects/{P}/geometries", limit=300) if "sealed" in g["name"]]
found = None
for g in geoms:
    gid = g["geometryId"]; regions = api.mappings(P, gid, "region"); bodies = [(r.get("originateFrom") or [{}])[0].get("body", "") for r in regions]
    print(g["name"][:50], gid[:8], "regions", len(regions), bodies)
    if len(regions) == 1 and any("flow" in b.lower() for b in bodies): found = gid; region = regions[0]["name"]
if not found: sys.exit("no extracted flow region yet")
faces = api.mappings(P, found, "face"); box = {}; walls = []
for f in faces:
    ent = (f.get("originateFrom") or [{}])[0].get("entity", ""); key = next((b for b in BOX if ent.startswith(b + "@")), None)
    (box.__setitem__(key + "@Flow region", f["name"]) if key else walls.append(f["name"]))
assert len(box) == 6, f"box faces {box}"
J["flow"] = dict(geometry_id=found, region=region, box=box, walls=sorted(walls), n_faces=len(faces)); json.dump(J, open(f"{SP}/m12_project.json", "w"), indent=1)
old = json.load(open(f"{SP}/flow_regions_sealed.json"))["d15"]
ow = set(old["walls"]); nw = set(walls); cmp = "IDENTICAL names" if ow == nw else f"differ ({len(ow - nw)} missing, {len(nw - ow)} new)"
print(f"flow region {found} region {region} faces {len(faces)} walls {len(walls)} inlet {box['Max Z@Flow region']} outlet {box['Min Z@Flow region']} | sweep d15 walls {len(ow)}: {cmp} | box same: {old['box'] == box}")
