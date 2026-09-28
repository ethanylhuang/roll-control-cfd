"""anim_render.py <case_dir> [--times all|last|<t1,t2>] [--fps 12] [--dpi 120] [--no-video] [--ref steady_result.json]
Headless renderer for the transient animation output written by pipeline/animFO (surfaces FOs, ascii .vtp):
  postProcessing/animSlices/<t>/{tabPlane,wakePlane}.vtp + animRocket/<t>/rocketPlane.vtp -> anim/frames/frame_NNNN.png -> anim/<tag>_<case>.mp4
Panels: full-length rocket plane (Mach + sonic line; numerical schlieren), tab mid-span plane (Mach; schlieren), cross-flow plane
25 mm behind the TE (streamwise vorticity), roll-moment time trace with the current frame marked. No VTK/ParaView needed."""
import argparse, json, os, re, subprocess, sys, time
import xml.etree.ElementTree as ET
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection, PolyCollection
from matplotlib.gridspec import GridSpec
from matplotlib.colors import LogNorm
from matplotlib.tri import Triangulation, LinearTriInterpolator
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.expanduser("~/.claude/skills/cfd-sweep/scripts")); sys.path.insert(0, os.path.join(ROOT, "pipeline"))
import foamutil

def read_vtp(path):
    """ascii XML PolyData -> dict(points (N,3), tris (M,3) fan-triangulated, pdata/cdata {name: (N,) or (N,3)})"""
    root = ET.parse(path).getroot(); piece = root.find(".//Piece"); out = {"pdata": {}, "cdata": {}}
    def arr(da, dtype=float):
        n = int(da.get("NumberOfComponents", 1)); a = np.array(da.text.split(), dtype=dtype); return a.reshape(-1, n) if n > 1 else a
    out["points"] = arr(piece.find("Points/DataArray"))
    polys = piece.find("Polys"); conn = arr(polys.find("DataArray[@Name='connectivity']"), np.int64); offs = arr(polys.find("DataArray[@Name='offsets']"), np.int64)
    tris = []; start = 0
    for end in offs:
        poly = conn[start:end]; start = end
        for i in range(1, len(poly) - 1): tris.append((poly[0], poly[i], poly[i + 1]))
    out["tris"] = np.array(tris, dtype=np.int64).reshape(-1, 3)
    for sec, key in (("PointData", "pdata"), ("CellData", "cdata")):
        s = piece.find(sec)
        if s is not None:
            for da in s.findall("DataArray"): out[key][da.get("Name")] = arr(da)
    return out

def read_stl(path):
    b = open(path, "rb").read()
    if b"facet normal" in b[:2000]: v = np.array(re.findall(rb"vertex\s+(\S+)\s+(\S+)\s+(\S+)", b), dtype=float)
    else:
        n = (len(b) - 84) // 50; a = np.frombuffer(b[84:84 + n * 50], dtype=np.dtype([("n", "<3f4"), ("v", "<9f4"), ("a", "<u2")])); v = a["v"].reshape(-1, 3).astype(float)
    return v.reshape(-1, 3, 3)

def plane_cut(tri, axis, x0):
    """segments (K,2,2) of a triangle soup cut by the plane coord[axis]=x0, expressed in the two remaining coordinates (axis order)"""
    keep = [i for i in range(3) if i != axis]; segs = []
    d = tri[:, :, axis] - x0; s = np.sign(d)
    for t, dd, ss in zip(tri, d, s):
        if ss.max() <= 0 or ss.min() >= 0: continue
        pts = []
        for i in range(3):
            j = (i + 1) % 3
            if ss[i] * ss[j] < 0:
                f = dd[i] / (dd[i] - dd[j]); p = t[i] + f * (t[j] - t[i]); pts.append(p[keep])
        if len(pts) == 2: segs.append(pts)
    return np.array(segs).reshape(-1, 2, 2)

def find_mesh_dir(case):
    pm = os.path.join(case, "constant", "polyMesh"); target = os.path.realpath(pm) if os.path.islink(pm) else pm
    return os.path.dirname(os.path.dirname(target))

ap = argparse.ArgumentParser(); ap.add_argument("case"); ap.add_argument("--times", default="all"); ap.add_argument("--fps", type=int, default=12); ap.add_argument("--dpi", type=int, default=120)
ap.add_argument("--no-video", action="store_true"); ap.add_argument("--sonic", action="store_true", help="draw the Ma = 1 contour (off by default)"); ap.add_argument("--no-streamlines", action="store_true", help="omit the in-plane streamlines on the tab and wake panels"); ap.add_argument("--ref", help="steady result.json for the reference roll line"); ap.add_argument("--title", default=None); ap.add_argument("--out", default=None)
a = ap.parse_args(); case = os.path.abspath(a.case.rstrip("/")); name = os.path.basename(case); tag = os.path.basename(os.path.dirname(case))
outdir = os.path.join(case, "anim"); fdir = os.path.join(outdir, "frames"); os.makedirs(fdir, exist_ok=True)
sdir = os.path.join(case, "postProcessing", "animSlices"); rdir = os.path.join(case, "postProcessing", "animRocket")
tdirs = sorted([d for d in os.listdir(sdir) if re.match(r"^[0-9.e+-]+$", d) and os.path.exists(os.path.join(rdir, d, "rocketPlane.vtp"))], key=float)
if a.times == "last": tdirs = tdirs[-1:]
elif a.times != "all": tdirs = [t for t in tdirs if t in a.times.split(",")]
print(f"{name}: {len(tdirs)} frames in {sdir}")
mdir = find_mesh_dir(case); stl = {k: read_stl(os.path.join(mdir, "constant", "triSurface", f"rocket_{k}.stl")) for k in ("body", "fins", "tab")}
meta = {}
for f in (os.path.join(case, "result.json"), a.ref):
    if f and os.path.exists(f): meta.update(json.load(open(f))); break
try:
    fl = open(os.path.join(case, "system", "flowSettings")).read(); mach = meta.get("mach") or float(re.search(r"^mach\s+([0-9.]+)", fl, re.M).group(1))
except Exception: mach = meta.get("mach", float("nan"))
defl = meta.get("deflection", {"d00": 0, "d03": 3, "d06": 6, "d09": 9, "d10": 10, "d12": 12, "d15": 15, "dm06": -6}.get(tag, float("nan")))
title = a.title or f"goonmax roll tab, sealed CAD: {defl:g}° tab, M {mach:g}  —  {'rhoPimpleFoam transient (k-ω SST URANS)' if 'transient' in name else name}"
try:
    hdr, dat = foamutil.parse_dat(foamutil.find_fo_file(case, "forces_all", "moment.dat")); tcol = dat[:, 0]; roll = -dat[:, hdr.index("total_z")]
except Exception as e: print("no forces trace:", e); tcol = roll = None
is_time = tcol is not None and tcol.max() < 10
ref_roll = None
if a.ref and os.path.exists(a.ref): ref_roll = json.load(open(a.ref))["moments_Nm"]["Mroll"]
elif "transient" in name:
    for cand in (name.replace("_transient", "_restart"), name.replace("_transient", "_opensides")):   # the steady the transient restarted from
        rf = os.path.join(os.path.dirname(case), cand, "result.json")
        if os.path.exists(rf):
            rj = json.load(open(rf)); val = rj["moments_Nm"]["Mroll"]
            if rj.get("stop_reason", "endTime") == "endTime" and abs(val) < 100: ref_roll = val; break
def load_frame(t): return {"tabPlane": read_vtp(os.path.join(sdir, t, "tabPlane.vtp")), "wakePlane": read_vtp(os.path.join(sdir, t, "wakePlane.vtp")), "rocketPlane": read_vtp(os.path.join(rdir, t, "rocketPlane.vtp"))}
def pdat(v, key):
    if key in v["pdata"]: return v["pdata"][key]
    if key == "Ma" and all(k in v["pdata"] for k in ("p", "rho", "U")):   # Mach from the sampled state: a = sqrt(gamma p / rho)
        P_, R_, U_ = v["pdata"]["p"], v["pdata"]["rho"], v["pdata"]["U"]; a = np.sqrt(1.4 * np.maximum(P_, 1.0) / np.maximum(R_, 1e-3)); return np.linalg.norm(U_, axis=1) / a
    if key in v["cdata"]:
        c = v["cdata"][key]; n = len(v["points"]); acc = np.zeros(n if c.ndim == 1 else (n, c.shape[1])); cnt = np.zeros(n)
        for ti, tri in enumerate(v["tris"]):
            for p in tri: acc[p] += c[min(ti, len(c) - 1)]; cnt[p] += 1
        return acc / np.maximum(cnt, 1)[:, None] if acc.ndim == 2 else acc / np.maximum(cnt, 1)
    raise KeyError(key)
# fixed colour scales from the first frame so the movie does not flicker
f0 = load_frame(tdirs[0]); sch_max = float(np.percentile(pdat(f0["tabPlane"], "mag(grad(rho))"), 99.5)); sch_max_r = float(np.percentile(pdat(f0["rocketPlane"], "mag(grad(rho))"), 99.7))
Pw = f0["wakePlane"]["points"]; wz = pdat(f0["wakePlane"], "vorticity")[:, 2]; wz_max = float(np.percentile(np.abs(wz[np.hypot(Pw[:, 0], Pw[:, 1]) > 0.038]), 99.7))
def has_ma(v): return "Ma" in v["pdata"] or all(k in v["pdata"] for k in ("p", "rho", "U"))
rocket_ma = has_ma(f0["rocketPlane"]); print("rocket plane Mach available:", rocket_ma)
ma_max = max(1.3, max(float(np.percentile(pdat(f0[k], "Ma"), 99.9)) for k in (("tabPlane", "rocketPlane") if rocket_ma else ("tabPlane",))) * 1.02)
print(f"scales: schlieren tab {sch_max:.0f} / rocket {sch_max_r:.0f} kg/m^4, |omega_z| {wz_max:.0f} 1/s, Ma max {ma_max:.2f}")
# panel windows (m): s = -z is the streamwise coordinate (flow left -> right); nose tip z = 1.337, fin/tab TE z = 0.025, tail z = -0.055
TAB = dict(s=(-0.165, 0.115), y=(-0.055, 0.055)); WAKE = dict(x=(-0.135, 0.06), y=(-0.10, 0.10)); RKT = dict(s=(-1.40, 0.28), x=(-0.125, 0.125))
fin_cut = plane_cut(stl["fins"], 0, -0.0854); tab_cut = plane_cut(stl["tab"], 0, -0.0854)      # tab plane: (y, z) pairs
def proj_sz(tri): return [[(-p[2] * 1e3, -p[0] * 1e3) for p in t] for t in tri]              # silhouette in the (−z, −x) rocket-plane view
def tri_plot(ax, v, vals, cmap, vmin, vmax, u, w, log=False):
    P = v["points"]
    if log: return ax.tripcolor(u(P), w(P), v["tris"], np.maximum(vals, vmin), shading="gouraud", cmap=cmap, norm=LogNorm(vmin=vmin, vmax=vmax), rasterized=True)
    return ax.tripcolor(u(P), w(P), v["tris"], vals, shading="gouraud", cmap=cmap, vmin=vmin, vmax=vmax, rasterized=True)
def streamlines(ax, v, u, w, cu, cw, xlim, ylim, density=1.3, color="0.15", n=(260, 110)):
    """in-plane streamlines of the sampled velocity: interpolate the cut-surface point data onto a regular grid (panel axes) and streamplot"""
    if a.no_streamlines or "U" not in v["pdata"]: return
    P = v["points"]; x = u(P); y = w(P); T = v["tris"]
    if len(T) < 3: return
    # the cut polygons' fan triangles overlap for non-convex cells (invalid for the tri-finder): use a Delaunay triangulation of the
    # unique points and mask the skinny triangles that span the body holes (max/min edge ratio > 6)
    key = np.round(np.column_stack([x, y]), 5); _, first = np.unique(key, axis=0, return_index=True); x, y = x[first], y[first]
    tri = Triangulation(x, y); Td = tri.triangles; e = np.stack([np.hypot(x[Td[:, i]] - x[Td[:, j]], y[Td[:, i]] - y[Td[:, j]]) for i, j in ((0, 1), (1, 2), (2, 0))], 1)
    tri.set_mask(e.max(1) / np.maximum(e.min(1), 1e-9) > 6)
    U = v["pdata"]["U"][first]; gx = np.linspace(xlim[0], xlim[1], n[0]); gy = np.linspace(ylim[0], ylim[1], n[1]); GX, GY = np.meshgrid(gx, gy)
    try: UU = LinearTriInterpolator(tri, cu(U))(GX, GY); WW = LinearTriInterpolator(tri, cw(U))(GX, GY)
    except Exception as e: print("streamlines skipped:", e); return
    ax.streamplot(gx, gy, np.ma.filled(UU, np.nan), np.ma.filled(WW, np.nan), density=density, color=color, linewidth=0.55, arrowsize=0.7, arrowstyle="->")
def sonic(ax, v, u, w):
    if not a.sonic: return   # off by default since 2026-09-16: at M>1 the Ma=1 contour outlines every boundary layer (user: "gray squiggly outline")
    P = v["points"]; ma = pdat(v, "Ma")
    if ma.max() > 1.0 > ma.min(): ax.tricontour(u(P), w(P), v["tris"], ma, levels=[1.0], colors="k", linewidths=0.7)
def render(t, idx):
    fr = load_frame(t); tt = float(t)
    if rocket_ma:
        fig = plt.figure(figsize=(16, 14.2), dpi=a.dpi); fig.patch.set_facecolor("white")
        gs = GridSpec(5, 2, figure=fig, width_ratios=[0.28, 0.20], height_ratios=[0.105, 0.105, 0.11, 0.11, 0.055], left=0.045, right=0.965, top=0.95, bottom=0.045, hspace=0.45, wspace=0.28)
        axr1 = fig.add_subplot(gs[0, :]); axr2 = fig.add_subplot(gs[1, :]); ax1 = fig.add_subplot(gs[2, 0]); ax2 = fig.add_subplot(gs[3, 0]); ax4 = fig.add_subplot(gs[2:4, 1]); ax5 = fig.add_subplot(gs[4, :])
    else:
        fig = plt.figure(figsize=(16, 12.2), dpi=a.dpi); fig.patch.set_facecolor("white")
        gs = GridSpec(4, 2, figure=fig, width_ratios=[0.28, 0.20], height_ratios=[0.105, 0.11, 0.11, 0.055], left=0.045, right=0.965, top=0.945, bottom=0.05, hspace=0.45, wspace=0.28)
        axr1 = None; axr2 = fig.add_subplot(gs[0, :]); ax1 = fig.add_subplot(gs[1, 0]); ax2 = fig.add_subplot(gs[2, 0]); ax4 = fig.add_subplot(gs[1:3, 1]); ax5 = fig.add_subplot(gs[3, :])
    # full-length rocket plane
    v = fr["rocketPlane"]; u = lambda P: -P[:, 2] * 1e3; w = lambda P: -P[:, 0] * 1e3
    if axr1 is not None: m = tri_plot(axr1, v, pdat(v, "Ma"), "turbo", 0, ma_max, u, w); sonic(axr1, v, u, w); fig.colorbar(m, ax=axr1, pad=0.01, fraction=0.02, label="Mach")
    m = tri_plot(axr2, v, pdat(v, "mag(grad(rho))"), "gray_r", max(sch_max_r / 300, 0.3), sch_max_r, u, w, log=True); fig.colorbar(m, ax=axr2, pad=0.01, fraction=0.02, label="|∇ρ| (kg/m⁴, log scale)")
    for ax in ((axr1, axr2) if axr1 is not None else (axr2,)):
        ax.add_collection(PolyCollection(proj_sz(stl["tab"]), facecolors="crimson", edgecolors="none", alpha=0.8))   # grey body/fin silhouettes removed (user request 2026-09-14)
        ax.set_xlim(RKT["s"][0] * 1e3, RKT["s"][1] * 1e3); ax.set_ylim(RKT["x"][0] * 1e3, RKT["x"][1] * 1e3); ax.set_aspect("equal"); ax.set_ylabel("−x (mm)")
    if axr1 is not None: axr1.set_title("Whole rocket, plane 1 mm above the tab fin (y = 6 mm): Mach number; flow left → right, nose at left, tab fin on top (tab red)", fontsize=10, loc="left")
    axr2.set_title(("Same plane" if axr1 is not None else "Whole rocket, plane 1 mm above the tab fin (y = 6 mm), flow left → right, nose at left, tab fin on top (tab red)") + ": numerical schlieren |∇ρ| on a log scale (weak far-field shocks visible; strongest gradients black)", fontsize=10, loc="left"); axr2.set_xlabel("−z, streamwise (mm)")
    # tab mid-span plane
    v = fr["tabPlane"]; u = lambda P: -P[:, 2] * 1e3; w = lambda P: P[:, 1] * 1e3
    m = tri_plot(ax1, v, pdat(v, "Ma"), "turbo", 0, ma_max, u, w); sonic(ax1, v, u, w); fig.colorbar(m, ax=ax1, pad=0.01, fraction=0.03, label="Mach")
    streamlines(ax1, v, u, w, lambda U: -U[:, 2], lambda U: U[:, 1], (TAB["s"][0] * 1e3, TAB["s"][1] * 1e3), (TAB["y"][0] * 1e3, TAB["y"][1] * 1e3), density=1.2)
    m = tri_plot(ax2, v, pdat(v, "mag(grad(rho))"), "gray_r", 0, sch_max, u, w); fig.colorbar(m, ax=ax2, pad=0.01, fraction=0.03, label="|∇ρ| (kg/m⁴)")
    for ax in (ax1, ax2):
        for segs, col, lw in ((tab_cut, "crimson", 1.6),):   # fin-section grey lines removed (user request 2026-09-14)
            if len(segs): ax.add_collection(LineCollection([[(-s[1] * 1e3, s[0] * 1e3) for s in seg] for seg in segs], colors=col, linewidths=lw))
        ax.set_xlim(TAB["s"][0] * 1e3, TAB["s"][1] * 1e3); ax.set_ylim(TAB["y"][0] * 1e3, TAB["y"][1] * 1e3); ax.set_aspect("equal"); ax.set_ylabel("y (mm)")
    ax1.set_title("Tab mid-span plane (x = −85.4 mm): Mach with in-plane streamlines; tab section in red", fontsize=10, loc="left")
    ax2.set_title("Same plane: numerical schlieren |∇ρ| (shocks sharp, shear layers/wake soft)", fontsize=10, loc="left"); ax2.set_xlabel("−z, streamwise (mm)")
    # cross-flow wake plane
    v = fr["wakePlane"]; u = lambda P: P[:, 0] * 1e3; w = lambda P: P[:, 1] * 1e3
    m = tri_plot(ax4, v, pdat(v, "vorticity")[:, 2], "RdBu_r", -wz_max, wz_max, u, w); fig.colorbar(m, ax=ax4, pad=0.02, fraction=0.035, label="ω_z (1/s)")
    streamlines(ax4, v, u, w, lambda U: U[:, 0], lambda U: U[:, 1], (WAKE["x"][0] * 1e3, WAKE["x"][1] * 1e3), (WAKE["y"][0] * 1e3, WAKE["y"][1] * 1e3), density=1.6, n=(200, 200))
    for k, col, al in (("tab", "crimson", 0.8),): ax4.add_collection(PolyCollection([[(p[0] * 1e3, p[1] * 1e3) for p in tri] for tri in stl[k]], facecolors=col, edgecolors="none", alpha=al))   # grey body/fin fills removed
    ax4.set_xlim(WAKE["x"][0] * 1e3, WAKE["x"][1] * 1e3); ax4.set_ylim(WAKE["y"][0] * 1e3, WAKE["y"][1] * 1e3); ax4.set_aspect("equal"); ax4.set_xlabel("x (mm)"); ax4.set_ylabel("y (mm)")
    ax4.set_title("Cross-flow plane 25 mm behind the TE (z = 0): vorticity ω_z, cross-flow streamlines", fontsize=10, loc="left")
    # roll-moment trace
    if tcol is not None:
        xs = tcol * 1e3 if is_time else tcol; ax5.plot(xs, roll, color="0.3", lw=0.8)
        if ref_roll is not None: ax5.axhline(ref_roll, color="tab:blue", ls="--", lw=0.9, label=f"steady-run mean {ref_roll:.3f} N·m")
        xt = tt * 1e3 if is_time else tt; k = int(np.searchsorted(tcol, tt)); k = min(max(k, 0), len(roll) - 1)
        ax5.plot([xt], [roll[k]], "o", color="crimson", ms=6); ax5.axvline(xt, color="crimson", lw=0.6, alpha=0.6)
        ax5.set_xlabel("t (ms)" if is_time else "iteration"); ax5.set_title(f"Total roll moment (N·m); now {roll[k]:.3f}", fontsize=10, loc="left"); ax5.grid(alpha=0.3)
        if ref_roll is not None: ax5.legend(fontsize=8, loc="best")
    fig.suptitle(f"{title}      t = {tt * 1e3:.3f} ms" if is_time else f"{title}      time {t}", fontsize=13, x=0.045, ha="left")
    fn = os.path.join(fdir, f"frame_{idx:04d}.png"); fig.savefig(fn, facecolor="white"); plt.close(fig); return fn
t0 = time.time()
for i, t in enumerate(tdirs):
    fn = render(t, i)
    if i % 10 == 0 or i == len(tdirs) - 1: print(f"  frame {i + 1}/{len(tdirs)} t={t} -> {os.path.basename(fn)} ({time.time() - t0:.0f}s)", flush=True)
if not a.no_video and len(tdirs) > 1:
    mp4 = a.out or os.path.join(outdir, f"{tag}_{name}.mp4")
    cmd = ["/opt/homebrew/bin/ffmpeg", "-y", "-loglevel", "error", "-framerate", str(a.fps), "-i", os.path.join(fdir, "frame_%04d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", mp4]
    rc = subprocess.run(cmd).returncode; print(f"ffmpeg rc={rc}: {mp4} ({os.path.getsize(mp4) / 1e6:.1f} MB)" if rc == 0 else f"ffmpeg failed rc={rc}")
