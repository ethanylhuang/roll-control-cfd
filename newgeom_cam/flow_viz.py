#!/usr/bin/env python3
"""Camera-shroud flow pictures from the M0.6 / 15 deg run on the current CAD (runs_v5cam).

Reads the cut planes written by system/vizDict (postProcessing/viz/2000/*.vtp) and the wall patch VTK
(VTK/rocket_body, p + wallShearStress). Frame: z = rocket axis (nose +z), flow along -z, shroud at x=0, y<0
(mirrored), aft rim z=0.750. Pictures show flow left -> right (s = -z) with the shroud side on top (v = -y).
Solid surfaces appear as the dark grey background (the planes only carry data in the fluid).
Usage: flow_viz.py <case> [--out DIR]
"""
import argparse, os, sys
import numpy as np
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from matplotlib.tri import Triangulation, LinearTriInterpolator
import xml.etree.ElementTree as ET


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



U_INF, P_INF, RHO_INF = 203.5, 97690.0, 1.1892
Q_INF = 0.5 * RHO_INF * U_INF ** 2
SOLID = '#4a4a4a'
ap = argparse.ArgumentParser(); ap.add_argument('case'); ap.add_argument('--out', default=None)
a = ap.parse_args()
OUT = a.out or os.path.join(a.case, 'viz'); os.makedirs(OUT, exist_ok=True)
S = {n: read_vtp(os.path.join(a.case, 'postProcessing/viz/2000', n + '.vtp'))
     for n in ('sidePlane', 'topPlane', 'cutZ790', 'cutZ745', 'cutZ700', 'cutZ600', 'cutZ400')}

# plane -> (horizontal, vertical) coordinates [mm] and in-plane velocity components
VIEW = {
    'side': (lambda P: -P[:, 2] * 1e3, lambda P: -P[:, 1] * 1e3, lambda U: -U[:, 2], lambda U: -U[:, 1]),
    'top': (lambda P: -P[:, 2] * 1e3, lambda P: P[:, 0] * 1e3, lambda U: -U[:, 2], lambda U: U[:, 0]),
    'cross': (lambda P: P[:, 0] * 1e3, lambda P: -P[:, 1] * 1e3, lambda U: U[:, 0], lambda U: -U[:, 1]),
}


def field(v, name):
    d = v['pdata']
    if name == 'Umag': return np.linalg.norm(d['U'], axis=1) / U_INF
    if name == 'Cp': return (d['p'] - P_INF) / Q_INF
    if name == 'wmag': return np.linalg.norm(d['vorticity'], axis=1)
    if name == 'wz': return d['vorticity'][:, 2]
    if name == 'Ma': return d['Ma']
    raise KeyError(name)


STYLE = {
    'Umag': dict(cmap='viridis', vmin=0.0, vmax=1.25, label='|U| / U$_\\infty$'),
    'Cp': dict(cmap='RdBu_r', vmin=-0.8, vmax=0.8, label='pressure coefficient C$_p$'),
    'wmag': dict(cmap='magma', vmin=2e2, vmax=2e5, log=True, label='vorticity |ω| [1/s]'),
    'wake': dict(cmap='viridis', vmin=0.55, vmax=1.08, label='|U| / U$_\\infty$ (wake deficit)'),
}


def panel(ax, view, v, fname, xlim, ylim, stream=False, sdensity=1.2, sgrid=(360, 160), title=None, emax=8.0):
    u, w, cu, cw = VIEW[view]
    P = v['points']
    st = STYLE[fname]
    vals = field(v, 'Umag' if fname == 'wake' else fname)
    ax.set_facecolor(SOLID)
    kw = dict(shading='gouraud', cmap=st['cmap'], rasterized=True)
    if st.get('log'):
        im = ax.tripcolor(u(P), w(P), v['tris'], np.clip(vals, st['vmin'], st['vmax']), norm=LogNorm(st['vmin'], st['vmax']), **kw)
    else:
        im = ax.tripcolor(u(P), w(P), v['tris'], vals, vmin=st['vmin'], vmax=st['vmax'], **kw)
    if stream:
        streamlines(ax, v, u, w, cu, cw, xlim, ylim, sdensity, sgrid, emax)
    ax.set_xlim(*xlim); ax.set_ylim(*ylim); ax.set_aspect('equal')
    if title: ax.set_title(title, fontsize=10, loc='left')
    return im


def fluid_mask(v, u, w, gx, gy):
    """True where a grid point lies inside a sampled (fluid) cut triangle: streamlines never enter solids."""
    P = v['points']; x = u(P); y = w(P); T = v['tris']
    M = np.zeros((len(gy), len(gx)), bool)
    dx, dy = gx[1] - gx[0], gy[1] - gy[0]
    tx, ty = x[T], y[T]
    keep = (tx.max(1) >= gx[0]) & (tx.min(1) <= gx[-1]) & (ty.max(1) >= gy[0]) & (ty.min(1) <= gy[-1])
    for (x0, x1, x2), (y0, y1, y2) in zip(tx[keep], ty[keep]):
        i0 = max(int(np.floor((min(x0, x1, x2) - gx[0]) / dx)), 0); i1 = min(int(np.ceil((max(x0, x1, x2) - gx[0]) / dx)), len(gx) - 1)
        j0 = max(int(np.floor((min(y0, y1, y2) - gy[0]) / dy)), 0); j1 = min(int(np.ceil((max(y0, y1, y2) - gy[0]) / dy)), len(gy) - 1)
        if i1 < i0 or j1 < j0: continue
        X, Y = np.meshgrid(gx[i0:i1 + 1], gy[j0:j1 + 1])
        d = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(d) < 1e-14: continue
        l1 = ((y1 - y2) * (X - x2) + (x2 - x1) * (Y - y2)) / d; l2 = ((y2 - y0) * (X - x2) + (x0 - x2) * (Y - y2)) / d
        M[j0:j1 + 1, i0:i1 + 1] |= (l1 >= -1e-9) & (l2 >= -1e-9) & (l1 + l2 <= 1 + 1e-9)
    return M


def streamlines(ax, v, u, w, cu, cw, xlim, ylim, density, n, emax):
    P = v['points']; x = u(P); y = w(P)
    key = np.round(np.column_stack([x, y]), 4); _, first = np.unique(key, axis=0, return_index=True)
    x, y = x[first], y[first]
    pad = 0.1 * max(xlim[1] - xlim[0], ylim[1] - ylim[0])
    sel = (x > xlim[0] - pad) & (x < xlim[1] + pad) & (y > ylim[0] - pad) & (y < ylim[1] + pad)
    x, y, Uf = x[sel], y[sel], v['pdata']['U'][first][sel]
    tri = Triangulation(x, y)
    gx = np.linspace(*xlim, n[0]); gy = np.linspace(*ylim, n[1]); GX, GY = np.meshgrid(gx, gy)
    UU = np.ma.filled(LinearTriInterpolator(tri, cu(Uf))(GX, GY), np.nan)
    WW = np.ma.filled(LinearTriInterpolator(tri, cw(Uf))(GX, GY), np.nan)
    solid = ~fluid_mask(v, u, w, gx, gy)
    UU[solid] = np.nan; WW[solid] = np.nan
    ax.streamplot(gx, gy, UU, WW, density=density, color='white', linewidth=0.5, arrowsize=0.6, arrowstyle='->',
                  broken_streamlines=True)


def cbar(fig, im, ax, fname, **kw):
    cb = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.01, **kw); cb.set_label(STYLE[fname]['label'], fontsize=9)
    cb.ax.tick_params(labelsize=8)


# ------------------------------------------------------------------ figure 1: whole rocket
side = S['sidePlane']
XL, YL = (-1530, 90), (-125, 125)                      # s = -z: nose tip at -1495, base at -20
fig, axes = plt.subplots(4, 1, figsize=(20, 13.5), constrained_layout=True)
rows = [('Umag', False, 'Velocity magnitude'), ('Umag', True, 'Velocity magnitude + streamlines'),
        ('wmag', False, 'Vorticity magnitude (log): boundary layers, the shroud wake, the fin/tab wakes'),
        ('Cp', False, 'Pressure coefficient')]
for ax, (fn, stc, t) in zip(axes, rows):
    im = panel(ax, 'side', side, fn, XL, YL, stream=stc, sdensity=(4.0, 1.2), sgrid=(1600, 250), title=t, emax=45.0)
    cbar(fig, im, ax, fn)
    ax.annotate('camera shroud', xy=(-771, 44), xytext=(-900, 105), color='w', fontsize=10,
                arrowprops=dict(arrowstyle='->', color='w', lw=1.2))
    ax.tick_params(labelsize=8)
axes[-1].set_xlabel('distance aft of z = 0 plane, flow left → right  [mm]   (nose tip at −1495, base at −20)', fontsize=9)
fig.suptitle('Current CAD, M0.6, tab 15°: side plane through the camera shroud centre-line (shroud side up)', fontsize=13)
p1 = os.path.join(OUT, 'flow_whole_rocket.png'); fig.savefig(p1, dpi=110); plt.close(fig)

# ------------------------------------------------------------------ figure 2: the shroud up close
top = S['topPlane']
ZX, ZY = (-840, -610), (22, 72)                       # side window: 60 mm ahead of the shroud to 140 mm behind it
TX, TY = (-840, -610), (-38, 38)
fig = plt.figure(figsize=(20, 21), constrained_layout=True)
gs = fig.add_gridspec(5, 4, height_ratios=[1, 1, 1, 1.25, 1.25])
r0 = [fig.add_subplot(gs[0, :2]), fig.add_subplot(gs[0, 2:])]
r1 = [fig.add_subplot(gs[1, :2]), fig.add_subplot(gs[1, 2:])]
r2 = [fig.add_subplot(gs[2, :2]), fig.add_subplot(gs[2, 2:])]
im = panel(r0[0], 'side', side, 'Umag', ZX, ZY, title='Side view: velocity'); cbar(fig, im, r0[0], 'Umag')
im = panel(r0[1], 'side', side, 'Umag', ZX, ZY, stream=True, sdensity=1.6, sgrid=(700, 160), emax=14.0, title='Side view: velocity + streamlines (separation bubble behind the lens face)'); cbar(fig, im, r0[1], 'Umag')
im = panel(r1[0], 'side', side, 'wmag', ZX, ZY, title='Side view: vorticity (log)'); cbar(fig, im, r1[0], 'wmag')
im = panel(r1[1], 'side', side, 'Cp', ZX, ZY, title='Side view: pressure (stagnation on the front, suction over the top, low base pressure)'); cbar(fig, im, r1[1], 'Cp')
im = panel(r2[0], 'top', top, 'Umag', TX, TY, stream=True, sdensity=1.6, sgrid=(700, 240), emax=14.0, title='Top view, plane 6.6 mm above the tube (shroud mid-height): velocity + streamlines'); cbar(fig, im, r2[0], 'Umag')
im = panel(r2[1], 'top', top, 'wmag', TX, TY, title='Top view, same plane: vorticity (log): shear layers off both side edges'); cbar(fig, im, r2[1], 'wmag')
for ax in r0 + r1:
    ax.set_xlabel('streamwise [mm] →', fontsize=8); ax.set_ylabel('height, tube surface at 28.9 [mm]', fontsize=8)
for ax in r2:
    ax.set_xlabel('streamwise [mm] →', fontsize=8); ax.set_ylabel('sideways [mm]', fontsize=8)
cuts = [('cutZ790', 'through the shroud (25 mm ahead of its aft face)'), ('cutZ745', '5 mm behind the aft face'),
        ('cutZ700', '50 mm behind'), ('cutZ600', '150 mm behind')]
CX, CY = (-45, 45), (-5, 65)
for k, (n, t) in enumerate(cuts):
    ax = fig.add_subplot(gs[3, k])
    im = panel(ax, 'cross', S[n], 'wake', CX, CY, stream=True, sdensity=1.4, sgrid=(200, 160), title=f'Cross-section {t}')
    ax.set_xlabel('[mm]', fontsize=8)
    if k == 3: cbar(fig, im, ax, 'wake')
for k, (n, t) in enumerate(cuts):
    ax = fig.add_subplot(gs[4, k])
    im = panel(ax, 'cross', S[n], 'wmag', CX, CY, title=f'Vorticity, {t}')
    ax.set_xlabel('[mm]', fontsize=8)
    if k == 3: cbar(fig, im, ax, 'wmag')
fig.suptitle('Camera shroud close-up (current CAD, M0.6, tab 15°). Flow left → right in side/top views; '
             'cross-sections look forward, shroud on top, with cross-flow streamlines', fontsize=13)
p2 = os.path.join(OUT, 'flow_shroud_closeup.png'); fig.savefig(p2, dpi=100); plt.close(fig)
print(p1); print(p2)

# ------------------------------------------------------------------ standalone: vortices + streamlines
fig, ax = plt.subplots(figsize=(16, 5.2), constrained_layout=True)
im = panel(ax, 'side', side, 'wmag', (-815, -660), (26, 60), stream=True, sdensity=2.4, sgrid=(900, 220), emax=14.0)
cbar(fig, im, ax, 'wmag')
ax.set_xlabel('streamwise [mm]  (flow left → right)', fontsize=10); ax.set_ylabel('height above axis [mm]  (tube surface 28.9)', fontsize=10)
ax.set_title('Camera shroud, side cut through its centre-line: vorticity + streamlines (current CAD, M0.6, tab 15°)', fontsize=12, loc='left')
ax.annotate('recirculation bubble\nin front of the lens', xy=(-742, 35), xytext=(-712, 52), color='w', fontsize=10,
            bbox=dict(boxstyle='round,pad=0.3', fc='black', alpha=0.6, ec='none'), arrowprops=dict(arrowstyle='->', color='w', lw=1.2))
p3 = os.path.join(OUT, 'shroud_vortices_side.png'); fig.savefig(p3, dpi=150); plt.close(fig)

fig, ax = plt.subplots(figsize=(9, 7.2), constrained_layout=True)
im = panel(ax, 'cross', S['cutZ700'], 'wmag', (-40, 40), (15, 56), stream=True, sdensity=2.2, sgrid=(400, 240), emax=14.0)
cbar(fig, im, ax, 'wmag')
ax.set_xlabel('[mm]', fontsize=10); ax.set_ylabel('height above axis [mm]', fontsize=10)
ax.set_title('50 mm behind the shroud, looking forward: vorticity + cross-flow streamlines\n(the shroud wake has rolled up into a counter-rotating vortex pair)', fontsize=11, loc='left')
p4 = os.path.join(OUT, 'shroud_vortices_cross50mm.png'); fig.savefig(p4, dpi=150); plt.close(fig)
print(p3); print(p4)

# ------------------------------------------------------------------ standalone: whole rocket, velocity + streamlines
fig, ax = plt.subplots(figsize=(22, 4.4), constrained_layout=True)
im = panel(ax, 'side', side, 'Umag', (-1530, 90), (-125, 125), stream=True, sdensity=(5.0, 1.6), sgrid=(1800, 280), emax=45.0)
cbar(fig, im, ax, 'Umag')
ax.annotate('camera shroud', xy=(-771, 44), xytext=(-900, 100), color='w', fontsize=11,
            bbox=dict(boxstyle='round,pad=0.3', fc='black', alpha=0.6, ec='none'), arrowprops=dict(arrowstyle='->', color='w', lw=1.2))
ax.annotate('base wake\n(flat base)', xy=(40, 0), xytext=(-150, -105), color='w', fontsize=11,
            bbox=dict(boxstyle='round,pad=0.3', fc='black', alpha=0.6, ec='none'), arrowprops=dict(arrowstyle='->', color='w', lw=1.2))
ax.set_xlabel('streamwise [mm]  (flow left → right; nose tip at −1495, base at −20)', fontsize=10); ax.set_ylabel('[mm]', fontsize=10)
ax.set_title('Whole rocket, side cut through the camera shroud centre-line: velocity + streamlines (current CAD, M0.6, tab 15°)', fontsize=12, loc='left')
p5 = os.path.join(OUT, 'whole_rocket_streamlines.png'); fig.savefig(p5, dpi=140); plt.close(fig)
print(p5)
