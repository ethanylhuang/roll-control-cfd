import os, sys, json, zipfile, gzip, shutil, time
sys.path.insert(0, os.path.expanduser("~/.claude/skills/cfd-sweep/scripts"))
from simscale_api import SimScale
api = SimScale(); COPY = "1269879333705405039"; name_prefix, out = sys.argv[1], sys.argv[2]; os.makedirs(out, exist_ok=True)
sims = [s for s in api.embedded(f"/projects/{COPY}/simulations", limit=300) if s["name"].startswith(name_prefix)]; sid = sims[0]["simulationId"]
runs = [r for r in api.embedded(f"/projects/{COPY}/simulations/{sid}/runs", limit=10) if r.get("status") == "FINISHED"]; rid = runs[-1]["runId"]
items = api.embedded(f"/projects/{COPY}/simulations/{sid}/runs/{rid}/results", limit=200); sol = [i for i in items if i.get("category") == "SOLUTION"][0]
zp = os.path.join(out, "solution.zip")
if not os.path.exists(zp):
    data = api.download(sol["download"]["url"]); open(zp, "wb").write(data); print(f"{name_prefix}: downloaded {len(data)/1e6:.0f} MB", flush=True)
z = zipfile.ZipFile(zp)
for n in z.namelist():
    if "constant/polyMesh/" in n and n.split("/")[-1] in ("points.gz", "faces.gz", "boundary"):
        z.extract(n, out)
        if n.endswith(".gz"):
            with gzip.open(os.path.join(out, n), "rb") as fi, open(os.path.join(out, n[:-3]), "wb") as fo: shutil.copyfileobj(fi, fo)
print(f"{name_prefix}: polyMesh extracted to {out}/constant/polyMesh")
