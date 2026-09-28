"""ss_flow_regions_sealed.py [tags]: resolve each staged sealed geometry's extracted flow region (by NAME; the CAD-mode extraction may save
under a new id), verify 1 region + 6 named box faces, list walls, write flow_regions_sealed.json, and compare the wall face names with the
old 'cfd' set (same tag) so the fine-op entity lists can be reused if identical."""
import os, sys, json
sys.path.insert(0, os.path.expanduser("~/.claude/skills/cfd-sweep/scripts"))
from simscale_api import SimScale
api = SimScale(); COPY = "1269879333705405039"; SP = "/Users/trasomi/dev/cfd/simscale_sealed"
staged = json.load(open(f"{SP}/staged_sealed.json")); outp = f"{SP}/flow_regions_sealed.json"
flow = json.load(open(outp)) if os.path.exists(outp) else {}
OLD_BASE = {"d00": "6f746ff9-59d1-421d-9ebf-0206956e158e", "d03": "211a48e4-cf5b-4f6a-8af2-73474cd4524d", "d06": "0015652e-ab2c-4a81-9f82-086670ae14db", "d09": "11541749-4568-4559-9b63-3e111743834f", "d12": "9afd9844-d7ff-403c-bf4b-451fe96a1a05", "d15": "8769b659-ef09-4abd-9880-e52aeb51cc85", "dm06": "73b003c4-11dd-41fb-85c2-1df6a4b8440e"}
BOX = ["Max X", "Min X", "Max Y", "Min Y", "Max Z", "Min Z"]
tags = sys.argv[1].split(",") if len(sys.argv) > 1 else list(staged)
geoms = api.embedded(f"/projects/{COPY}/geometries", limit=300)
for tag in tags:
    name = staged[tag]["name"]; cands = [g for g in geoms if g["name"].strip() == name.strip()]
    found = None
    for g in cands:
        gid = g["geometryId"]; regions = api.mappings(COPY, gid, "region")
        bodies = [(r.get("originateFrom") or [{}])[0].get("body", "") for r in regions]
        if len(regions) == 1 and any("flow" in b.lower() for b in bodies): found = gid; break
    if not found: print(f"{tag}: NO extracted flow region yet ({len(cands)} geometries named '{name}', regions per candidate: {[len(api.mappings(COPY, g['geometryId'], 'region')) for g in cands]})"); continue
    faces = api.mappings(COPY, found, "face"); box = {}; walls = []
    for f in faces:
        ent = (f.get("originateFrom") or [{}])[0].get("entity", ""); key = next((b for b in BOX if ent.startswith(b + "@")), None)
        (box.__setitem__(key + "@Flow region", f["name"]) if key else walls.append(f["name"]))
    region = regions[0]["name"]
    assert len(box) == 6, f"{tag}: box faces {box}"
    flow[tag] = dict(geometry_id=found, region=region, box=box, walls=sorted(walls), n_faces=len(faces))
    json.dump(flow, open(outp, "w"), indent=1)
    msg = f"{tag}: flow region {found[:8]} region {region} faces {len(faces)} walls {len(walls)} inlet {box['Max Z@Flow region']} outlet {box['Min Z@Flow region']}"
    if tag in OLD_BASE:
        old = api.simulation(COPY, OLD_BASE[tag]); oldwalls = set(next(b for b in old["model"]["boundaryConditions"] if b["type"].startswith("WALL"))["topologicalReference"]["entities"])
        msg += f" | old cfd walls {len(oldwalls)}: {'IDENTICAL names' if oldwalls == set(walls) else f'differ ({len(oldwalls - set(walls))} missing, {len(set(walls) - oldwalls)} new)'}"
    print(msg, flush=True)
