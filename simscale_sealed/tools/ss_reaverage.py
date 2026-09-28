"""ss_reaverage.py <result.json> [--window N] [--write]: download the run's MOMENT/FORCE plots and print roll statistics over several
iteration windows (last 500 / 1000 / 1500 / 2000) plus a coarse oscillation analysis; --write rewrites the json with the --window mean."""
import os, sys, json, csv, io, statistics as st, argparse
sys.path.insert(0, os.path.expanduser("~/.claude/skills/cfd-sweep/scripts"))
from simscale_api import SimScale
ap = argparse.ArgumentParser(); ap.add_argument("result"); ap.add_argument("--window", type=int, default=1500); ap.add_argument("--write", action="store_true"); a = ap.parse_args()
api = SimScale(); COPY = "1269879333705405039"; r = json.load(open(a.result)); sid, rid = r["sim"], r["run"]
items = api.embedded(f"/projects/{COPY}/simulations/{sid}/runs/{rid}/results", limit=200)
def load(cat):
    it = [i for i in items if i.get("category") == cat]; data = api.download(it[0]["download"]["url"]).decode("utf-8", "replace").replace("\x00", "")
    rr = [x for x in csv.reader(io.StringIO(data)) if x and x[0].strip()]; hdr = [h.strip() for h in rr[0]]; body = []
    for x in rr[1:]:
        try: body.append([float(v) for v in x[:len(hdr)]])
        except ValueError: pass
    return {h: i for i, h in enumerate(hdr)}, body
mi, M = load("MOMENT_PLOT"); fi, F = load("FORCE_PLOT"); roll = [-x[mi["TOTAL_MOMENT_Z"]] for x in M]; n = len(roll)
print(f"{os.path.basename(a.result)}: {n} iterations; stored (last 500) Mroll {r['moments_Nm']['Mroll']:.4f}")
for w in (500, 1000, 1500, 2000):
    seg = roll[-w:]; m = st.mean(seg); sd = st.pstdev(seg); drift = abs(st.mean(seg[-w//4:]) - st.mean(seg[:w//4])) / abs(m) * 100 if m else 0
    print(f"  last {w:4d}: Mroll {m:.4f}  std {100*sd/abs(m):5.1f}%  drift {drift:5.1f}%  min/max {min(seg):.4f}/{max(seg):.4f}")
# block means of 250 iterations over the second half
blocks = [st.mean(roll[i:i+250]) for i in range(n//2, n - 249, 250)]; print("  250-it block means (2nd half):", [round(b, 4) for b in blocks])
# dominant period from zero crossings of the demeaned last-1500 signal
seg = roll[-1500:]; m = st.mean(seg); zc = [i for i in range(1, len(seg)) if (seg[i-1]-m) * (seg[i]-m) < 0]; print(f"  zero crossings in last 1500: {len(zc)} -> mean half-period {1500/max(len(zc),1):.0f} it")
if a.write:
    w = a.window; seg = roll[-w:]; sl = slice(-w, None); m = st.mean(seg)
    r["moments_Nm"] = dict(Mroll=m, Mpitch=st.mean(x[mi["TOTAL_MOMENT_Y"]] for x in M[sl]), Myaw=st.mean(x[mi["TOTAL_MOMENT_X"]] for x in M[sl]))
    r["forces_N"] = dict(Fx=st.mean(x[fi["TOTAL_FORCE_X"]] for x in F[sl]), Fy=st.mean(x[fi["TOTAL_FORCE_Y"]] for x in F[sl]), Fz=st.mean(x[fi["TOTAL_FORCE_Z"]] for x in F[sl]))
    sd = 100 * st.pstdev(seg) / abs(m) if m else 0; drift = abs(st.mean(seg[-w//4:]) - st.mean(seg[:w//4])) / abs(m) * 100 if m else 0
    r["convergence"].update(std_rel_pct=sd, drift_pct=drift, window=w, flags=([f"mroll_drift({drift:.1f}%)"] if drift > 3 else []) + ([f"mroll_noisy(std={sd:.1f}%)"] if sd > 5 else []))
    json.dump(r, open(a.result, "w"), indent=2); print(f"  written: window {w} Mroll {m:.4f} std {sd:.1f}% drift {drift:.1f}%")
