"""Export Parasolid per deflection from the CFD branch and import into the SimScale project copy as 'dXX cfd rocket'."""
import os, sys, json, time
sys.path.insert(0, os.path.expanduser("~/.claude/skills/cfd-sweep/scripts"))
import simscale_onshape as so, onshape_export as oe
from simscale_api import SimScale
api = SimScale(); COPY = "1269879333705405039"
SP = "/private/tmp/claude-501/-Users-trasomi-dev-cfd/e77796e5-73f1-4b54-ac10-df1a9b566759/scratchpad"
out_json = f"{SP}/staged_cfd.json"; staged = json.load(open(out_json)) if os.path.exists(out_json) else {}
cfg = oe.load_config()
for tag, d in (("d00", 0.0), ("d03", 3.0), ("d06", 6.0), ("d09", 9.0), ("d12", 12.0), ("d15", 15.0), ("dm06", -6.0)):
    if tag in staged: print(tag, "already staged", staged[tag]["geometry_id"]); continue
    path = f"{SP}/parasolid_cfd/{tag}_cfd_rocket.x_t"
    info = so.export_parasolid(d, path, cfg); print(f"{tag}: exported {os.path.getsize(path)} bytes", flush=True)
    name = f"{tag} cfd rocket (delta={d:g}, CFD branch, API 2026-09-06)"
    with open(path, "rb") as f: gid = api.import_geometry(COPY, name, api.upload(f.read()), fmt="PARASOLID", unit="m")
    gid = gid if isinstance(gid, str) else (gid.get("geometryId") or gid)
    staged[tag] = {"geometry_id": gid, "name": name, "deflection": d}; json.dump(staged, open(out_json, "w"), indent=1)
    print(f"{tag}: imported geometry {gid}", flush=True)
print("STAGED", json.dumps({k: v["geometry_id"][:8] for k, v in staged.items()}))
