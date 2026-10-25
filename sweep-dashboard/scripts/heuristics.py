"""Hand-method estimates of tab roll moment, compared against the sealed-tab CFD sweep.

Reads analysis/sweep.json (written by analyze.py) and writes analysis/heuristic.json
plus public/data/heuristic.csv. Run after analyze.py. Needs numpy; no network.

Geometry: Onshape document 4a303129, CFD workspace (44bb5cf8), Part Studio export of
2026-09-11 11:24 = the sealed-tab CAD meshed for the sweep (../models_v4/d00). Measured
by slicing rocket_fins.stl / rocket_tab.stl:
  fin root r = 28.75 mm, tip r = 111.9 mm (span 83.15 mm), 10 mm thick slab
  root chord 115 mm (z 25..140), tip chord 55 mm (z 25..80), LE swept, TE unswept at z = 25
  tab r = 81.41..89.41 mm (8 mm span), z = 26.0..52.5 (26.5 mm chord), hinge at z = 52.5

Methods (all inviscid, small-angle, linear in deflection):
  strip  Barrowman/Diederich fin lift slope x thin-airfoil flap effectiveness tau,
         applied to the fin strip behind the tab. Arm = tab mid-span radius.
  vlm    Vortex lattice of one fin with a reflection plane at the root (body as a wall),
         tab panels at +delta; Prandtl-Glauert via the Goethert rule. Subsonic only.
  linear Ackeret supersonic theory: each tab face carries Cp = 2 delta / beta, the
         side-edge spill lands on the neighbouring fin, so total = 4 delta / beta x S_tab.
"""
from pathlib import Path
import csv
import json
import math

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SWEEP = ROOT / 'analysis/sweep.json'
OUT_JSON = ROOT / 'analysis/heuristic.json'
OUT_CSV = ROOT / 'public/data/heuristic.csv'

# Geometry, metres (see docstring for provenance).
R_ROOT, R_TIP = .02875, .1119
SPAN = R_TIP - R_ROOT
Z_TE, Z_LE_ROOT, Z_LE_TIP = .025, .140, .080
TAB_R = (.08141, .08941)
TAB_Z = (.026, .0525)
HINGE_Z = TAB_Z[1]
TAB_SPAN = TAB_R[1] - TAB_R[0]
TAB_CHORD = TAB_Z[1] - TAB_Z[0]
TAB_AREA = TAB_SPAN * TAB_CHORD
TAB_ARM = sum(TAB_R) / 2
FIN_AREA = SPAN * ((Z_LE_ROOT - Z_TE) + (Z_LE_TIP - Z_TE)) / 2
RHO = 1.18915  # sweep reference density
SOUND = 339.1  # source velocities are Mach x 339.1 (analyze.py)


def z_le(r):
    return Z_LE_ROOT + (Z_LE_TIP - Z_LE_ROOT) * (r - R_ROOT) / SPAN


def beta(mach):
    return math.sqrt(abs(1 - mach * mach))


# ---- strip theory ---------------------------------------------------------------
def fin_lift_slope(mach):
    """Diederich/Barrowman fin normal-force slope per radian, on fin planform area."""
    aspect = 2 * SPAN ** 2 / FIN_AREA  # body acts as a reflection plane
    mid_root = (Z_LE_ROOT + Z_TE) / 2
    mid_tip = (Z_LE_TIP + Z_TE) / 2
    cos_mid = math.cos(math.atan((mid_root - mid_tip) / SPAN))
    return 2 * math.pi * aspect / (2 + math.sqrt(4 + (beta(mach) * aspect / cos_mid) ** 2))


def flap_tau(chord_fraction):
    theta = math.acos(2 * chord_fraction - 1)
    return 1 - (theta - math.sin(theta)) / math.pi


LOCAL_CHORD = z_le(TAB_ARM) - Z_TE
TAU = flap_tau(TAB_CHORD / LOCAL_CHORD)


def strip_roll_per_rad(mach, q):
    return q * fin_lift_slope(mach) * TAU * TAB_SPAN * LOCAL_CHORD * TAB_ARM


# ---- vortex lattice -------------------------------------------------------------
def _segment_w(p, a, b):
    """Downwash at points p (N,3) from unit-strength segments a->b (M,3): returns (N,M) z-velocity."""
    r1 = p[:, None, :] - a[None, :, :]
    r2 = p[:, None, :] - b[None, :, :]
    cross = np.cross(r1, r2)
    c2 = (cross ** 2).sum(-1)
    n1 = np.linalg.norm(r1, axis=-1)
    n2 = np.linalg.norm(r2, axis=-1)
    r0 = (b - a)[None, :, :]
    k = ((r0 * r1).sum(-1) / n1 - (r0 * r2).sum(-1) / n2) / (4 * math.pi * np.where(c2 < 1e-16, np.inf, c2))
    return k * cross[..., 2]


def _horseshoe_w(p, a, b, far=1e3):
    tail = np.array([far, 0, 0])
    return _segment_w(p, a + tail, a) + _segment_w(p, a, b) + _segment_w(p, b, b + tail)


def build_lattice(n_front=14, n_back=8):
    """Panels in fin coordinates: x downstream from the root LE, y outboard from the root."""
    tab_y = (TAB_R[0] - R_ROOT, TAB_R[1] - R_ROOT)
    edges = np.unique(np.concatenate([np.linspace(0, tab_y[0], 40), np.linspace(*tab_y, 9),
                                      np.linspace(tab_y[1], SPAN, 18)]))
    x_hinge, x_te = Z_LE_ROOT - HINGE_Z, Z_LE_ROOT - Z_TE
    panels = []
    for y0, y1 in zip(edges[:-1], edges[1:]):
        on_tab = y0 >= tab_y[0] - 1e-9 and y1 <= tab_y[1] + 1e-9
        xs = [np.concatenate([np.linspace(Z_LE_ROOT - z_le(R_ROOT + y), x_hinge, n_front + 1),
                              np.linspace(x_hinge, x_te, n_back + 1)[1:]]) for y in (y0, y1)]
        for i in range(n_front + n_back):
            panels.append(dict(y0=y0, y1=y1, xa0=xs[0][i], xb0=xs[0][i + 1], xa1=xs[1][i], xb1=xs[1][i + 1],
                               deflected=on_tab and i >= n_front))
    return panels


def vlm_roll_per_rad(mach, q, panels):
    b = beta(mach)
    y0 = np.array([p['y0'] for p in panels]); y1 = np.array([p['y1'] for p in panels])
    xa0 = np.array([p['xa0'] for p in panels]) / b; xb0 = np.array([p['xb0'] for p in panels]) / b
    xa1 = np.array([p['xa1'] for p in panels]) / b; xb1 = np.array([p['xb1'] for p in panels]) / b
    defl = np.array([p['deflected'] for p in panels], float)
    zero = np.zeros_like(y0)
    a = np.stack([xa0 + .25 * (xb0 - xa0), y0, zero], 1)       # bound vortex at panel quarter chord
    bb = np.stack([xa1 + .25 * (xb1 - xa1), y1, zero], 1)
    ym = (y0 + y1) / 2
    xc = (xa0 + .75 * (xb0 - xa0) + xa1 + .75 * (xb1 - xa1)) / 2
    ctrl = np.stack([xc, ym, zero], 1)
    mirror = np.array([1, -1, 1])
    aic = _horseshoe_w(ctrl, a, bb) + _horseshoe_w(ctrl, bb * mirror, a * mirror)  # image fin across the root
    gamma = np.linalg.solve(aic, -defl)          # per unit V and unit deflection (rad)
    v = math.sqrt(2 * q / RHO)
    force = RHO * v * v * gamma * (y1 - y0)       # Kutta-Joukowski, N per rad
    return float((force * (R_ROOT + ym)).sum()), float(force.sum())


# ---- supersonic linear theory ---------------------------------------------------
def ackeret_roll_per_rad(mach, q):
    return q * 4 / beta(mach) * TAB_AREA * TAB_ARM


def main():
    sweep = json.loads(SWEEP.read_text())
    panels = build_lattice()
    cfd = {}
    for p in sweep['points']:
        if p['role'] in ('primary', 'supersonic') and not (p['role'] == 'supersonic' and p['method'] != 'transient'):
            cfd[(p['solver'], p['mach'], p['angle'])] = p
    machs = sweep['machs'] + [1.2]
    per_mach, rows = [], []
    for m in machs:
        q = next(p['q'] for k, p in cfd.items() if k[1] == m)
        strip = strip_roll_per_rad(m, q) if m < 1 else None
        vlm = vlm_roll_per_rad(m, q, panels)[0] if m < 1 else None
        lin = ackeret_roll_per_rad(m, q) if m > 1 else None
        fit = next((f for f in sweep['fits'] if f['solver'] == 'OpenFOAM' and f['mach'] == m and f['metric'] == 'roll'
                    and f['minAngle'] == -6 and f['maxAngle'] == 15 and not f['excludeFlagged']), None)
        fit_ss = next((f for f in sweep['fits'] if f['solver'] == 'SimScale' and f['mach'] == m and f['metric'] == 'roll'
                       and f['minAngle'] == -6 and f['maxAngle'] == 15 and not f['excludeFlagged']), None)
        of15 = cfd.get(('OpenFOAM', m, 15.0))
        per_deg = lambda v: None if v is None else v * math.pi / 180
        cfd_slope = fit['slope'] if fit else (of15['roll'] / 15 if of15 else None)
        per_mach.append(dict(mach=m, q=q, beta=beta(m), cfdSlope=cfd_slope, cfdSlopeSimScale=fit_ss['slope'] if fit_ss else None,
                             cfdSlopeSource='OpenFOAM OLS −6°…15°' if fit else 'OpenFOAM 15° transient ÷ 15',
                             strip=per_deg(strip), vlm=per_deg(vlm), linear=per_deg(lin),
                             finLiftSlope=fin_lift_slope(m) if m < 1 else None))
        for angle in sweep['angles']:
            of = cfd.get(('OpenFOAM', m, float(angle)))
            ss = cfd.get(('SimScale', m, float(angle)))
            if of is None and ss is None:
                continue
            est = {k: (None if v is None else v * math.radians(angle)) for k, v in (('strip', strip), ('vlm', vlm), ('linear', lin))}
            ref = of['roll'] if of else None
            ratio = lambda v: None if v is None or ref is None or abs(ref) < 1e-3 else v / ref
            rows.append(dict(mach=m, angle=angle, openfoam=ref, simscale=ss['roll'] if ss else None,
                             openfoamMethod=of['method'] if of else None, **est,
                             stripRatio=ratio(est['strip']), vlmRatio=ratio(est['vlm']), linearRatio=ratio(est['linear'])))
    sub = [r for r in per_mach if r['vlm'] and r['cfdSlope']]
    eta = sum(r['cfdSlope'] / r['vlm'] for r in sub if r['mach'] <= .6) / len([r for r in sub if r['mach'] <= .6])
    sup = next(r for r in per_mach if r['mach'] == 1.2)
    eta_sup = sup['cfdSlope'] / sup['linear']
    # Flight extrapolation: Ackeret scaled by the M1.2 calibration, at the sweep's sea-level density.
    extrap = [dict(mach=m, q=.5 * RHO * (m * SOUND) ** 2, beta=beta(m),
                   linear=ackeret_roll_per_rad(m, .5 * RHO * (m * SOUND) ** 2) * math.pi / 180,
                   calibrated=eta_sup * ackeret_roll_per_rad(m, .5 * RHO * (m * SOUND) ** 2) * math.pi / 180)
              for m in (1.2, 1.45, 1.9)]
    geometry = dict(onshape='4a30312915205423304bc8d9 / CFD workspace 44bb5cf8 / export 2026-09-11 11:24',
                    rootRadius=R_ROOT, tipRadius=R_TIP, span=SPAN, rootChord=Z_LE_ROOT - Z_TE, tipChord=Z_LE_TIP - Z_TE,
                    leSweepDeg=math.degrees(math.atan((Z_LE_ROOT - Z_LE_TIP) / SPAN)), finArea=FIN_AREA, finThickness=.010,
                    aspect=2 * SPAN ** 2 / FIN_AREA, tabSpan=TAB_SPAN, tabChord=TAB_CHORD, tabArea=TAB_AREA, tabArm=TAB_ARM,
                    localChord=LOCAL_CHORD, chordFraction=TAB_CHORD / LOCAL_CHORD, tau=TAU, panels=len(panels))
    OUT_JSON.write_text(json.dumps(dict(geometry=geometry, perMach=per_mach, rows=rows, etaSubsonic=eta,
                                        etaSupersonic=eta_sup, extrapolation=extrap), indent=1))
    with OUT_CSV.open('w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    print(f"tau={TAU:.3f}  E={TAB_CHORD / LOCAL_CHORD:.3f}  fin AR={geometry['aspect']:.2f}  eta_sub={eta:.3f}  eta_M1.2={eta_sup:.3f}")
    for r in per_mach:
        f = lambda v: '   —   ' if v is None else f'{v:7.4f}'
        print(f"M{r['mach']:.2f}  CFD {f(r['cfdSlope'])}  strip {f(r['strip'])}  VLM {f(r['vlm'])}  linear {f(r['linear'])}  N·m/deg")


if __name__ == '__main__':
    main()
