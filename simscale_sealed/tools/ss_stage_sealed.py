"""Export Parasolid per deflection from the sealed CFD-branch CAD and import into the SimScale project copy as 'dXX sealed rocket'.
State: simscale_sealed/staged_sealed.json (durable, in the repo; the old scratchpad copies were reaped by the 3-day tmp cleaner)."""
import os, sys, json
sys.path.insert(0, os.path.expanduser("~/.claude/skills/cfd-sweep/scripts"))
import simscale_onshape as so, onshape_export as oe
from simscale_api import SimScale
api = SimScale(); COPY = "1269879333705405039"
SP = "/Users/trasomi/dev/cfd/simscale_sealed"; os.makedirs(f"{SP}/parasolid_sealed", exist_ok=True)
out_json = f"{SP}/staged_sealed.json"; staged = json.load(open(out_json)) if os.path.exists(out_json) else {}
cfg = oe.load_config()
tags = [t for t in os.environ.get("TAGS", "d03,d15,d10,d00,d06,d09,d12,dm06").split(",") if t]
DEFL = {"d00": 0.0, "d03": 3.0, "d06": 6.0, "d09": 9.0, "d10": 10.0, "d12": 12.0, "d15": 15.0, "dm06": -6.0}
for tag in tags:
    d = DEFL[tag]
    if tag in staged: print(tag, "already staged", staged[tag]["geometry_id"]); continue
    path = f"{SP}/parasolid_sealed/{tag}_sealed_rocket.x_t"
    info = so.export_parasolid(d, path, cfg); print(f"{tag}: exported {os.path.getsize(path)} bytes, #deflection readback {info.get('deflection_readback')!r}, API requests {info.get('api_requests')}", flush=True)
    name = f"{tag} sealed rocket (delta={d:g}, CFD branch sealed tab, API 2026-09-11)"
    with open(path, "rb") as f: gid = api.import_geometry(COPY, name, api.upload(f.read()), fmt="PARASOLID", unit="m")
    gid = gid if isinstance(gid, str) else (gid.get("geometryId") or gid)
    staged[tag] = {"geometry_id": gid, "name": name, "deflection": d}; json.dump(staged, open(out_json, "w"), indent=1)
    print(f"{tag}: imported geometry {gid}", flush=True)
print("STAGED", json.dumps({k: v["geometry_id"][:8] for k, v in staged.items()}))
if os.environ.get("RESET", "1") == "1":
    print("#deflection reset ->", so.reset_deflection(cfg))
