"""patch_bboxes.py <polyMesh dir> <out.json>: bounding box of every boundary patch (face name) of an OpenFOAM ascii polyMesh."""
import re, sys, json, numpy as np, os
base, outp = sys.argv[1], sys.argv[2]
lines = open(os.path.join(base, "faces")).read().split("\n"); i0 = next(i for i, l in enumerate(lines) if l.strip() == "(") + 1
pl = open(os.path.join(base, "points")).read().split("\n"); p0 = next(i for i, l in enumerate(pl) if l.strip() == "(") + 1; npts = int(pl[p0 - 2].strip())
pts = np.array([[float(x) for x in l.strip("()").split()] for l in pl[p0:p0 + npts]])
bt = open(os.path.join(base, "boundary")).read()
patches = re.findall(r"\n\s*(\S+)\s*\{\s*type\s+(\w+);.*?nFaces\s+(\d+);\s*startFace\s+(\d+);", bt, flags=re.S)
out = {}
for name, typ, nfc, start in patches:
    nfc, start = int(nfc), int(start); ids = set()
    for k in range(start, start + nfc):
        l = lines[i0 + k]; ids.update(int(x) for x in l[l.index("(") + 1:l.index(")")].split())
    P = pts[list(ids)]; out[name] = {"type": typ, "nFaces": nfc, "min": P.min(0).round(5).tolist(), "max": P.max(0).round(5).tolist()}
json.dump(out, open(outp, "w"), indent=1); print("patches:", len(out), "->", outp)
