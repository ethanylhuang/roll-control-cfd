#!/usr/bin/env python3
"""Build CFD surface groups for the camera-shroud geometry (Onshape "Full" assembly, Main workspace, 2026-09-23).

Input : tools/split4cam/onshape/{ps1/*.stl, runcam/*.stl, asm.json}  (Part Studio 1 zip + assembly definition)
Output: models_v5cam/d15/{rocket_body,rocket_fins,rocket_slot,rocket_tab}.stl + geometry_report.json + hinge.json

Frame = the v4 CFD frame (fin can at z 0.025..0.140 as in models_v4), nose +z, metres:
  - fin can + tab keep their Part Studio pose (identical to every v4 export; slot matches to 0.000 mm)
  - body parts take their ASSEMBLY pose + 20 mm (assembly puts the can flush with the tube end)
  - everything mirrored y -> -y so the CAD's tab (-15 deg) becomes the v4 +15 deg convention (d15)
Watertight outer skin (the CAD has screw holes, an open motor bore and no end plug):
  - tubes + motor flange -> one body of revolution (base capped flush at the motor flange face, bore closed; holes and
    seams gone), capped at the nose joint; nose = the CAD nose surface
  - camera shroud: CAD surface kept; flat cap over the aft camera opening at the rim plane (lens sits 0.8 mm inside),
    which encloses the pocket and the slivers around the camera
  - fin can: triangles inside the tube OD dropped (internal), rest split with the exporter's split_fincan
  - tab: CAD tab (6 mm, 1 mm end clearances) widened in x to the 8 mm slot = the sealed-CFD-branch convention
"""
import json, os, sys
import numpy as np
from scipy.spatial import ConvexHull

ROOT = '/Users/trasomi/dev/cfd'
SRC = os.path.join(ROOT, 'tools/split4cam/onshape')
BOATTAIL = '--boattail' in sys.argv          # add Part Studio 1 'Boattail' behind the motor flange (not instanced in the assembly)
OUT = os.path.join(ROOT, 'models_v5cam_bt/d15' if BOATTAIL else 'models_v5cam/d15')
sys.path.insert(0, os.path.expanduser('~/.claude/skills/cfd-sweep/scripts'))
from onshape_export import read_stl, write_stl, tri_areas, bbox, split_fincan, load_config  # noqa

R_TUBE = 0.028905
SHIFT = 0.020


def load(name):
    return read_stl(open(os.path.join(SRC, name), 'rb').read())[0]


def asm_transforms():
    a = json.load(open(os.path.join(SRC, 'asm.json')))
    ra = a['rootAssembly']
    names = {i['id']: i['name'] for i in ra['instances']}
    for s in a['subAssemblies']:
        for i in s['instances']:
            names[i['id']] = i['name']
    return {names[o['path'][-1]].rsplit(' <', 1)[0]: np.array(o['transform']).reshape(4, 4) for o in ra['occurrences']}


def apply(T, tris, dz=0.0):
    v = tris.reshape(-1, 3) @ T[:3, :3].T + T[:3, 3]
    v[:, 2] += dz
    return v.reshape(-1, 3, 3)


def mirror_y(tris):
    t = tris.copy()
    t[..., 1] *= -1
    return t[:, [0, 2, 1], :]           # keep outward winding


def normals(tris):
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-30)


def revolve(profile, n=256):
    """(z, r) polyline from base to tip; r == 0 at an end closes it. Outward winding by construction."""
    ang = np.linspace(0, 2 * np.pi, n, endpoint=False)
    ring = lambda z, r: np.stack([r * np.cos(ang), r * np.sin(ang), np.full(n, z)], 1)
    tris = []
    for (z0, r0), (z1, r1) in zip(profile[:-1], profile[1:]):
        a, b = ring(z0, r0), ring(z1, r1)
        for j in range(n):
            k = (j + 1) % n
            if r0 == 0:                                   # base disc fan, normal -z
                tris.append([a[0], b[k], b[j]])
            elif r1 == 0:                                 # tip fan
                tris.append([a[j], a[k], b[0]])
            else:
                tris += [[a[j], a[k], b[k]], [a[j], b[k], b[j]]]
    return np.array(tris)


def plug_side_holes(sh, z_hole=0.7633 + 0.0, y_hole=0.0315):
    """The shroud's two side screw holes (x-axis, ~2 mm, they open into the camera pocket): a disc in each wall's
    mid-plane, radius = measured hole radius + 0.6 mm so its rim is buried in the wall material."""
    c = sh.mean(1)
    n = normals(sh)
    discs = []
    for sgn in (1, -1):
        near = (np.sign(c[:, 0]) == sgn) & (np.abs(c[:, 0]) > 0.0068) & (np.abs(c[:, 0]) < 0.0098) & \
               (np.hypot(c[:, 1] - y_hole, c[:, 2] - z_hole) < 0.003) & (np.abs(n[:, 0]) < 0.2)
        v = sh[near].reshape(-1, 3)
        yc, zc = v[:, 1].mean(), v[:, 2].mean()
        rh = np.hypot(v[:, 1] - yc, v[:, 2] - zc).mean()
        xw = sgn * 0.5 * (np.abs(v[:, 0]).min() + np.abs(v[:, 0]).max())
        ang = np.linspace(0, 2 * np.pi, 25)
        ring = np.stack([np.full(25, xw), yc + (rh + 6e-4) * np.cos(ang), zc + (rh + 6e-4) * np.sin(ang)], 1)
        ctr = np.array([xw, yc, zc])
        discs += [[ctr, ring[k], ring[k + 1]] for k in range(24)]
        print(f'shroud hole plug x {xw*1e3:+.2f} mm: hole r {rh*1e3:.2f} mm at y {yc*1e3:.2f} z {zc*1e3:.2f} mm ({near.sum()} wall tris)')
    return np.array(discs)


def cap_opening(sh):
    """Planar cap (normal -z) over the camera opening in the shroud's aft face: the aft face is a U (two legs + top
    bar, legs run down into the tube), the cap spans its inner edge chain and is closed along the legs' foot line."""
    from collections import Counter, defaultdict
    n = normals(sh)
    c = sh.mean(1)
    zr = sh[..., 2].min()
    aft = sh[(n[:, 2] < -0.999) & (np.abs(c[:, 2] - zr) < 1e-5)]
    key = lambda p: tuple(np.round(p * 1e7).astype(np.int64))
    E = Counter()
    for t in aft:
        k = [key(p) for p in t]
        for i in range(3):
            E[tuple(sorted((k[i], k[(i + 1) % 3])))] += 1
    adj = defaultdict(list)
    for (p, q), m in E.items():
        if m == 1:
            adj[p].append(q); adj[q].append(p)
    start = next(iter(adj)); loop = [start]; prev = None
    while True:
        nxt = [x for x in adj[loop[-1]] if x != prev]
        if not nxt or nxt[0] == start:
            break
        prev = loop[-1]; loop.append(nxt[0])
    L = np.array(loop, float) / 1e7
    ymin = L[:, 1].min()
    feet = np.nonzero(np.abs(L[:, 1] - ymin) < 1e-6)[0]
    inner = [i for i in feet if abs(L[i, 0]) < 0.5 * np.abs(L[feet, 0]).max()]   # the two inner foot corners
    assert len(inner) == 2, inner
    i0, i1 = sorted(inner, key=lambda i: L[i, 0])
    # walk from the left inner corner the way that climbs (inner wall), to the right inner corner
    n_ = len(L)
    for step in (1, -1):
        chain = [i0]
        while chain[-1] != i1 and len(chain) <= n_:
            chain.append((chain[-1] + step) % n_)
        pts = L[chain]
        if np.abs(pts[:, 0]).max() < 0.5 * np.abs(L[feet, 0]).max():   # inner chain never reaches the outer feet
            break
    ctr = np.array([0.5 * (pts[:, 0].min() + pts[:, 0].max()), 0.5 * (pts[:, 1].min() + pts[:, 1].max()), zr])
    cap = np.array([[ctr, pts[k], pts[(k + 1) % len(pts)]] for k in range(len(pts))])
    nz = normals(cap)[:, 2]
    cap[nz > 0] = cap[nz > 0][:, [0, 2, 1]]
    print(f'shroud cap: {len(cap)} tris, {tri_areas(cap).sum()*1e4:.2f} cm2 at z {zr:.4f}, opening x {pts[:,0].min()*1e3:.1f}..'
          f'{pts[:,0].max()*1e3:.1f} mm, top y {pts[:,1].max()*1e3:.1f} mm')
    return cap


def main():
    T = asm_transforms()
    ps = lambda p: load(f'ps1/Body - {p}.stl')
    # ---- body of revolution from tubes + nose + motor flange (assembly pose + 20 mm)
    body_parts = np.concatenate([apply(T[p], ps(p), SHIFT) for p in ('Booster Tube', 'Airframe Tube', 'Nose Cone', 'Motor')])
    v = body_parts.reshape(-1, 3)
    r = np.hypot(v[:, 0], v[:, 1])
    z_base = v[:, 2].min()
    tip = v[:, 2].max()
    # nose: the CAD nose surface itself (a max-radius-per-z profile of its tessellation zig-zags between staggered
    # rings and gave ~2 mm sawtooth ridges, run 2026-09-23 #1); the revolved tube ends in a flat cap at the joint,
    # which seals the nose shoulder / tube interior behind it
    nose_tris = apply(T['Nose Cone'], ps('Nose Cone'), SHIFT)
    z_tube_top = 1.2 + 0.005 + SHIFT                     # airframe tube forward end (assembly 1.205)
    profile = [(z_base, 0.0), (z_base, R_TUBE), (z_tube_top, R_TUBE), (z_tube_top, 0.0)]
    body = np.concatenate([revolve(profile), nose_tris])
    if BOATTAIL:   # Part Studio pose relative to the motor (flange aft face = boattail forward face) -> motor's assembly transform
        bt = apply(T['Motor'], ps('Boattail'), SHIFT)
        bv = bt.reshape(-1, 3)
        print(f'boattail: z {bv[:,2].min():.4f}..{bv[:,2].max():.4f}, r {np.hypot(bv[:,0],bv[:,1]).min()*1e3:.1f}..'
              f'{np.hypot(bv[:,0],bv[:,1]).max()*1e3:.1f} mm (hollow, open aft end: base cavity closed by the flange face)')
        body = np.concatenate([body, bt])
    nv = nose_tris.reshape(-1, 3)
    print(f'body: revolved tube z {z_base:.4f}..{z_tube_top:.4f} (capped) + CAD nose ({len(nose_tris)} tris, '
          f'r at joint {np.hypot(nv[:,0],nv[:,1])[np.abs(nv[:,2]-z_tube_top)<1e-4].max()*1e3:.3f} mm, tip {tip:.4f})')

    # ---- camera shroud: CAD surface + flat cap over the aft camera opening (pocket, slivers, lens enclosed)
    sh = apply(T['Camera Shroud'], ps('Camera Shroud'), SHIFT)
    ht = cap_opening(sh)
    keep = np.hypot(sh[..., 0], sh[..., 1]).max(1) >= R_TUBE - 1e-5          # drop parts wholly inside the tube
    ht = np.concatenate([sh[keep], ht, plug_side_holes(sh)])

    # ---- fin can (Part Studio pose), drop internal tris, split like the exporter
    cfg = load_config()
    fc = ps('Fin Can')
    c = fc.mean(1)
    fc = fc[np.hypot(c[:, 0], c[:, 1]) >= R_TUBE + 4e-5]
    # ---- tab: widen x to the slot, keep profile (Part Studio pose)
    tab = ps('Fin Tab')
    tx = tab[..., 0]
    xc, half = 0.5 * (tx.min() + tx.max()), 0.5 * (tx.max() - tx.min())
    slot_lo, slot_hi = -0.089411, -0.081411               # slot faces (identical to v4, measured)
    tab[..., 0] = 0.5 * (slot_lo + slot_hi) + (tx - xc) * (0.5 * (slot_hi - slot_lo) / half)
    print(f'tab: x {tx.min()*1e3:.2f}..{tx.max()*1e3:.2f} mm -> {tab[...,0].min()*1e3:.2f}..{tab[...,0].max()*1e3:.2f} mm (slot width)')

    # ---- mirror everything to the d15 convention
    body, ht, fc, tab = (mirror_y(x) for x in (body, ht, fc, tab))
    tab_lo, tab_hi = bbox(tab)
    cfg['split'] = dict(cfg['split'])
    fm, sm, bm, r_can = split_fincan(fc, normals(fc), tab_lo, tab_hi, cfg)
    R_CAN_V4 = 0.02875                                    # v4 exports' detected sleeve radius: sleeve OD goes to rocket_fins
    cc = fc.mean(1)
    fm = ~sm & (np.hypot(cc[:, 0], cc[:, 1]) > R_CAN_V4 + cfg['split']['fin_radius_margin_m'])
    bm = ~fm & ~sm
    r_can = R_CAN_V4
    groups = {
        'rocket_body': np.concatenate([body, ht, fc[bm]]),
        'rocket_fins': fc[fm],
        'rocket_slot': fc[sm],
        'rocket_tab': tab,
    }
    os.makedirs(OUT, exist_ok=True)
    rep = {'deflection_requested_deg': 15.0, 'source': 'Onshape Full assembly (Main ws 334e390e), built by newgeom_cam/build_geometry.py',
           'Dref': 2 * R_TUBE, 'r_can_detected': r_can, 'groups': {}, 'tab_bbox': [tab_lo, tab_hi], 'warnings': []}
    for g, t in groups.items():
        write_stl(os.path.join(OUT, g + '.stl'), t.astype(np.float32), normals(t), g)
        lo, hi = bbox(t)
        rep['groups'][g] = dict(tris=int(len(t)), area_m2=float(tri_areas(t).sum()), bbox=[lo, hi])
        print(f'{g:12s} {len(t):6d} tris  {tri_areas(t).sum()*1e4:8.1f} cm2  bbox z {lo[2]:.4f}..{hi[2]:.4f}')
    every = np.concatenate(list(groups.values()))
    rep['body_bbox'] = bbox(every)
    rep['L_body'] = rep['body_bbox'][1][2] - rep['body_bbox'][0][2]
    rep['fin_LE_z'] = rep['groups']['rocket_fins']['bbox'][1][2]
    # measured deflection vs the v4 d00 reference tab (same hinge; tab widened to the same 8 mm)
    from onshape_export import measure_against_reference
    ref, _ = read_stl(open(os.path.join(ROOT, 'models_v4/d00/rocket_tab.stl'), 'rb').read())
    meas, hyz, sign = measure_against_reference(tab, ref)
    rep['measured_deflection_deg'] = meas
    print(f'measured deflection {meas:.3f} deg (vs v4 d00 tab), hinge yz {hyz}')
    json.dump(rep, open(os.path.join(OUT, 'geometry_report.json'), 'w'), indent=2)
    hj = json.load(open(os.path.join(ROOT, 'models_v4/hinge.json')))
    json.dump(hj, open(os.path.join(os.path.dirname(OUT), 'hinge.json'), 'w'), indent=2)


if __name__ == '__main__':
    main()
