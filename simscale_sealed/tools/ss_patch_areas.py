"""ss_patch_areas.py <result.json> <out_dir>: download the run's SOLUTION zip, extract constant/polyMesh, compute per-patch area, bbox and
face count, write <out_dir>/patch_areas.json and delete the zip (disk!)."""
import os, sys, json, zipfile, gzip, shutil, re
import numpy as np
sys.path.insert(0, os.path.expanduser("~/.claude/skills/cfd-sweep/scripts"))
from simscale_api import SimScale
api = SimScale(); COPY = "1269879333705405039"
res = json.load(open(sys.argv[1])); out = sys.argv[2]; os.makedirs(out, exist_ok=True)
items = api.embedded(f"/projects/{COPY}/simulations/{res['sim']}/runs/{res['run']}/results", limit=200)
sol = [i for i in items if i.get("category") == "SOLUTION"]
if not sol: sys.exit("no SOLUTION item")
zp = os.path.join(out, "solution.zip")
if not os.path.exists(os.path.join(out, "polyMesh", "boundary")):
    data = api.download(sol[0]["download"]["url"]); open(zp, "wb").write(data); print(f"downloaded {len(data)/1e6:.0f} MB", flush=True)
    z = zipfile.ZipFile(zp); os.makedirs(os.path.join(out, "polyMesh"), exist_ok=True)
    for n in z.namelist():
        base = n.split("/")[-1]
        if "constant/polyMesh/" in n and base.split(".")[0] in ("points", "faces", "boundary", "owner"):
            raw = z.read(n)
            if n.endswith(".gz"): raw = gzip.decompress(raw)
            open(os.path.join(out, "polyMesh", base.replace(".gz", "")), "wb").write(raw)
    os.remove(zp); print("polyMesh extracted, zip removed", flush=True)
pm = os.path.join(out, "polyMesh")
def read_list(path, kind):
    raw = open(path, "rb").read()
    hdr_end = raw.index(b"}", raw.index(b"FoamFile")) + 1
    body = raw[hdr_end:]
    m = re.search(rb"\n(\d+)\s*\n\(", body); n = int(m.group(1)); start = m.end()
    is_binary = b"format" in raw[:hdr_end] and b"binary" in raw[:hdr_end]
    if kind == "points":
        if is_binary: return np.frombuffer(body[start:start + n * 24], dtype="<f8").reshape(n, 3)
        txt = body[start:].decode("ascii", "ignore"); vals = re.findall(r"\(\s*([-\d.eE+]+)\s+([-\d.eE+]+)\s+([-\d.eE+]+)\s*\)", txt[:txt.rfind(")")])
        return np.array(vals[:n], dtype=float)
    if kind == "faces":
        if is_binary:  # faceCompactList: offsets then flat labels
            off = np.frombuffer(body[start:start + n * 4], dtype="<i4"); rest = body[start + n * 4:]
            m2 = re.search(rb"\n(\d+)\s*\n\(", rest); n2 = int(m2.group(1)); s2 = m2.end()
            lab = np.frombuffer(rest[s2:s2 + n2 * 4], dtype="<i4"); return off, lab
        txt = body[start:].decode("ascii", "ignore"); faces = re.findall(r"(\d+)\(([^)]*)\)", txt); 
        off = [0]; lab = []
        for cnt, s in faces[:n]:
            ids = [int(x) for x in s.split()]; lab += ids; off.append(off[-1] + len(ids))
        return np.array(off), np.array(lab)
pts = read_list(os.path.join(pm, "points"), "points"); off, lab = read_list(os.path.join(pm, "faces"), "faces")
bt = open(os.path.join(pm, "boundary")).read()
patches = re.findall(r"\n\s*(\S+)\s*\{\s*type\s+(\w+);.*?nFaces\s+(\d+);\s*startFace\s+(\d+);", bt, flags=re.S)
outp = {}
for name, typ, nf, sf in patches:
    nf, sf = int(nf), int(sf); area = 0.0; ids = set(); nrm = np.zeros(3)
    for k in range(sf, sf + nf):
        v = lab[off[k]:off[k + 1]]; P = pts[v]; ids.update(v.tolist())
        c = P.mean(axis=0); a = np.zeros(3)
        for i in range(len(P)): a += np.cross(P[i] - c, P[(i + 1) % len(P)] - c)
        area += 0.5 * np.linalg.norm(a); nrm += 0.5 * a
    Q = pts[list(ids)] if ids else np.zeros((1, 3))
    outp[name] = dict(type=typ, nFaces=nf, area_cm2=round(area * 1e4, 4), min=Q.min(0).round(5).tolist(), max=Q.max(0).round(5).tolist(), net_normal=(nrm / max(area, 1e-12)).round(3).tolist())
json.dump(outp, open(os.path.join(out, "patch_areas.json"), "w"), indent=1)
walls = {k: v for k, v in outp.items() if v["type"] == "wall"}
print("patches", len(outp), "walls", len(walls), "-> patch_areas.json")
