"""Hand-method estimates of tab roll moment, compared against the sealed-tab CFD sweep.

Reads analysis/sweep.json (written by analyze.py) and writes analysis/heuristic.json, whose
per-degree derivatives the dashboard overlays on its CFD charts. Run after analyze.py.
Needs numpy; no network.

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
Side force and yaw (about z = 0.330 m) count the fin load only: lift the tab induces on
the body has no roll arm and is not estimated, so CFD side force should come out higher.
"""
from pathlib import Path
import json
import math

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SWEEP = ROOT / 'analysis/sweep.json'
OUT_JSON = ROOT / 'analysis/heuristic.json'

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
AREA, LENGTH, ZREF = .0026248, .05781, .330  # sweep reference area, length, moment point


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


def vlm_per_rad(mach, q, panels):
    """Returns (roll N·m, side force N, yaw N·m about ZREF), each per radian of tab."""
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
    z_load = Z_LE_ROOT - b * (a[:, 0] + bb[:, 0]) / 2
    return float((force * (R_ROOT + ym)).sum()), float(force.sum()), float((force * (ZREF - z_load)).sum())


# ---- supersonic linear theory ---------------------------------------------------
def ackeret_per_rad(mach, q):
    force = q * 4 / beta(mach) * TAB_AREA
    return force * TAB_ARM, force, force * (ZREF - sum(TAB_Z) / 2)


def coefficients(q, roll, side=None, yaw=None):
    """Per-degree dimensional values plus the sweep's coefficients."""
    d = math.pi / 180
    out = dict(roll=roll * d, cl=roll * d / (q * AREA * LENGTH))
    if side is not None:
        out.update(side=side * d, cy=side * d / (q * AREA), yaw=yaw * d, cn=yaw * d / (q * AREA * LENGTH))
    return out


def main():
    sweep = json.loads(SWEEP.read_text())
    panels = build_lattice()
    q_of = {p['mach']: p['q'] for p in sweep['points']}
    roll_slope = lambda m: next(f['slope'] for f in sweep['fits'] if f['solver'] == 'OpenFOAM' and f['mach'] == m
                                and f['metric'] == 'roll' and f['minAngle'] == -6 and f['maxAngle'] == 15 and not f['excludeFlagged'])
    m12 = next(p for p in sweep['points'] if p['mach'] == 1.2 and p['method'] == 'transient')
    per_mach = []
    for m in sweep['machs'] + [1.2]:
        q = q_of[m]
        est = {}
        if m < 1:
            est['strip'] = coefficients(q, strip_roll_per_rad(m, q))
            est['vlm'] = coefficients(q, *vlm_per_rad(m, q, panels))
        else:
            est['linear'] = coefficients(q, *ackeret_per_rad(m, q))
        per_mach.append(dict(mach=m, q=q, est=est))
    calib = [r for r in per_mach if r['mach'] <= .6]
    eta = sum(roll_slope(r['mach']) / r['est']['vlm']['roll'] for r in calib) / len(calib)
    for r in per_mach:
        if 'vlm' in r['est']:
            r['est']['calibrated'] = {k: eta * r['est']['vlm'][k] for k in ('roll', 'cl')}
    sup = per_mach[-1]['est']['linear']
    eta_sup = m12['roll'] / 15 / sup['roll']
    geometry = dict(onshape='4a30312915205423304bc8d9 / CFD workspace 44bb5cf8 / export 2026-09-11 11:24',
                    span=SPAN, rootChord=Z_LE_ROOT - Z_TE, tipChord=Z_LE_TIP - Z_TE, finArea=FIN_AREA,
                    aspect=2 * SPAN ** 2 / FIN_AREA, tabSpan=TAB_SPAN, tabChord=TAB_CHORD, tabArm=TAB_ARM,
                    chordFraction=TAB_CHORD / LOCAL_CHORD, tau=TAU, panels=len(panels))
    OUT_JSON.write_text(json.dumps(dict(geometry=geometry, perMach=per_mach, etaSubsonic=eta, etaSupersonic=eta_sup), indent=1))
    print(f"tau={TAU:.3f}  E={TAB_CHORD / LOCAL_CHORD:.3f}  fin AR={geometry['aspect']:.2f}  eta_sub={eta:.3f}  eta_M1.2={eta_sup:.3f}")
    for r in per_mach:
        print(f"M{r['mach']:.2f}", {k: {mk: round(mv, 4) for mk, mv in v.items()} for k, v in r['est'].items()})


if __name__ == '__main__':
    main()
