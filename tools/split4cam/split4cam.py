#!/usr/bin/env python3
"""split4cam — render what a RunCam Split 4 would record from a camera mounted on your rocket.

Uses a measured Gyroflow calibration of the Split 4 (OpenCV fisheye model: fx != fy captures the
~1.1x horizontal squeeze of its 16:9 recording) and ray-traces your exported geometry (STL/OBJ/PLY)
with Open3D, over a procedural or image-textured ground and a sky gradient.

  python split4cam.py config.toml            # render using a config file
  python split4cam.py --demo [--lens-height 5 --tilt 7 --altitude 300 --out demo.png]

Coordinates: meshes and camera pose are given in the SAME model frame as your CAD export (mm by default).
The rocket is placed nose-up (model `rocket.axis` -> world +Z), with the lens `altitude_m` above flat ground.
Camera frame convention: z = lens axis (where it looks), image x = right, image y = down.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import tomllib
from pathlib import Path

import numpy as np
import open3d as o3d
from PIL import Image

HERE = Path(__file__).resolve().parent
DEFAULT_PROFILE = HERE / 'lens' / 'RunCam_Split 4___2.7k_16by9_2704x1520-60.00fps.json'


# ----------------------------------------------------------------------------- lens model
def load_lens(profile: Path, width: int, height: int):
    """Return (fx, fy, cx, cy, D[4]) scaled to the requested output resolution."""
    d = json.loads(Path(profile).read_text())
    K = np.array(d['fisheye_params']['camera_matrix'], float)
    D = np.array(d['fisheye_params']['distortion_coeffs'], float)
    cw, ch = d['calib_dimension']['w'], d['calib_dimension']['h']
    sx, sy = width / cw, height / ch
    return K[0, 0] * sx, K[1, 1] * sy, K[0, 2] * sx, K[1, 2] * sy, D


def theta_max(D, limit=math.radians(89.0)):
    """Largest incidence angle for which theta_d(theta) is still increasing (model is valid)."""
    th = np.linspace(0, limit, 4000)
    k1, k2, k3, k4 = D
    dd = 1 + 3 * k1 * th**2 + 5 * k2 * th**4 + 7 * k3 * th**6 + 9 * k4 * th**8
    bad = np.nonzero(dd <= 0)[0]
    return th[bad[0] - 1] if len(bad) else limit


def pixel_rays(width, height, lens, ss=1):
    """Unit ray directions in camera frame for every (sub)pixel; invalid (outside lens model) -> NaN."""
    fx, fy, cx, cy, D = lens
    k1, k2, k3, k4 = D
    W, H = width * ss, height * ss
    u = (np.arange(W, dtype=np.float64) + 0.5) / ss
    v = (np.arange(H, dtype=np.float64) + 0.5) / ss
    uu, vv = np.meshgrid(u, v)
    xd = (uu - cx) / fx
    yd = (vv - cy) / fy
    rd = np.hypot(xd, yd)                           # = theta_d
    # The calibration polynomial folds over past ~tmax (extrapolated beyond the calibrated range).
    # Invert it up to t_ref, then continue linearly with the slope at t_ref (smooth, monotonic corners).
    tmax = theta_max(D)
    t_ref = 0.9 * tmax
    tr2 = t_ref * t_ref
    thd_ref = t_ref * (1 + tr2 * (k1 + tr2 * (k2 + tr2 * (k3 + tr2 * k4))))
    slope = 1 + tr2 * (3 * k1 + tr2 * (5 * k2 + tr2 * (7 * k3 + tr2 * 9 * k4)))
    th = np.clip(rd, 0, t_ref)
    for _ in range(25):                             # Newton: theta*(1+k1 t^2+...) = rd
        t2 = th * th
        f = th * (1 + t2 * (k1 + t2 * (k2 + t2 * (k3 + t2 * k4)))) - rd
        fp = 1 + t2 * (3 * k1 + t2 * (5 * k2 + t2 * (7 * k3 + t2 * 9 * k4)))
        th = np.clip(th - f / fp, 0, t_ref)
    far = rd > thd_ref
    th = np.where(far, t_ref + (rd - thd_ref) / slope, th)
    valid = th < math.radians(89.5)
    s = np.where(rd > 1e-12, np.sin(th) / np.maximum(rd, 1e-12), 1.0)
    dirs = np.stack([xd * s, yd * s, np.cos(th)], axis=-1)
    dirs[~valid] = np.nan
    return dirs.astype(np.float32), math.degrees(tmax)


# ----------------------------------------------------------------------------- geometry helpers
def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def rot_a_to_b(a, b):
    a, b = unit(a), unit(b)
    v = np.cross(a, b)
    c = float(np.dot(a, b))
    if np.linalg.norm(v) < 1e-12:
        if c > 0:
            return np.eye(3)
        p = unit(np.cross(a, [1, 0, 0] if abs(a[0]) < 0.9 else [0, 1, 0]))
        return 2 * np.outer(p, p) - np.eye(3)
    vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + vx + vx @ vx * (1 / (1 + c))


def rot_x(deg):
    a = math.radians(deg)
    return np.array([[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]])


def mesh_from_arrays(V, F):
    m = o3d.geometry.TriangleMesh(o3d.utility.Vector3dVector(np.asarray(V, float)),
                                  o3d.utility.Vector3iVector(np.asarray(F, np.int32)))
    return m


def revolve(profile_zr, n=128):
    """Surface of revolution about +Z from (z, r) polyline."""
    zr = np.asarray(profile_zr, float)
    ang = np.linspace(0, 2 * np.pi, n, endpoint=False)
    V = np.array([[r * math.cos(a), r * math.sin(a), z] for z, r in zr for a in ang])
    F = []
    for i in range(len(zr) - 1):
        for j in range(n):
            a, b = i * n + j, i * n + (j + 1) % n
            c, d = a + n, b + n
            F += [[a, b, d], [a, d, c]]
    return mesh_from_arrays(V, F)


def extrude_polygon_xz(poly_xz, thickness, y_center=0.0):
    """Planar polygon in the x-z plane (convex fan triangulation) extruded along y."""
    P = np.asarray(poly_xz, float)
    n = len(P)
    h = thickness / 2
    V = [[x, y_center - h, z] for x, z in P] + [[x, y_center + h, z] for x, z in P]
    F = []
    for i in range(1, n - 1):
        F += [[0, i, i + 1], [n, n + i + 1, n + i]]
    for i in range(n):
        j = (i + 1) % n
        F += [[i, j, n + j], [i, n + j, n + i]]
    return mesh_from_arrays(V, F)


# ----------------------------------------------------------------------------- demo rocket (from aero-control.ork)
def demo_rocket(lens_height_mm, tilt_deg, cam_z_mm, booster_mm=721.0, upper_mm=445.0):
    """Nose-up rocket in mm, model axis = +Z, tail at z=0. Returns (meshes, camera dict)."""
    R = 28.905                                   # tube outer radius (G12-2.1)
    body = booster_mm + upper_mm
    nose_len = 270.0
    # Von Karman (Haack C=0) nose
    xs = np.linspace(0, 1, 60)
    th = np.arccos(1 - 2 * xs)
    rn = R * np.sqrt((th - np.sin(2 * th) / 2) / np.pi)
    nose = [(body + nose_len * (1 - x), r) for x, r in zip(xs, rn)][::-1]
    tube = revolve([(0.0, R), (body, R)], n=160)
    nose_m = revolve(sorted(nose, key=lambda p: p[0]), n=160)
    motor = revolve([(-20.0, 20.0), (0.0, 27.0)], n=96)               # nozzle/retainer stub
    meshes = [(tube, (205, 212, 222)), (nose_m, (205, 212, 222)), (motor, (60, 60, 64))]
    # 4 fins: freeform root LE (0,0) -> tip LE (60,80) -> tip TE (115.2,80) -> root TE (115.2,0); TE 17 mm above tail
    root_te = 17.0
    root_le = root_te + 115.2
    fin = [(R, root_le), (R + 80.0, root_le - 60.0), (R + 80.0, root_te), (R, root_te)]
    for k in range(4):
        f = extrude_polygon_xz(fin, 12.7)
        f.rotate(o3d.geometry.get_rotation_matrix_from_xyz((0, 0, k * math.pi / 2)), center=(0, 0, 0))
        meshes.append((f, (35, 38, 48)))
    # camera midway between fins (45 deg), lens centre lens_height above skin, looking aft & tilted outward
    radial = unit([math.cos(math.pi / 4), math.sin(math.pi / 4), 0])
    pos = radial * (R + lens_height_mm) + np.array([0, 0, cam_z_mm])
    cam = dict(position=pos.tolist(), radial=radial.tolist(), tilt_deg=tilt_deg)
    return meshes, cam


# ----------------------------------------------------------------------------- procedural ground
def _hash2(ix, iy, seed):
    h = (ix * 374761393 + iy * 668265263 + seed * 144269504) & 0xFFFFFFFF
    h = (h ^ (h >> 13)) * 1274126177 & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFF) / 65535.0


def value_noise(x, y, scale, seed):
    gx, gy = x / scale, y / scale
    ix, iy = np.floor(gx).astype(np.int64), np.floor(gy).astype(np.int64)
    fx, fy = gx - ix, gy - iy
    sx, sy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a, b = _hash2(ix, iy, seed), _hash2(ix + 1, iy, seed)
    c, d = _hash2(ix, iy + 1, seed), _hash2(ix + 1, iy + 1, seed)
    return (a + (b - a) * sx) * (1 - sy) + (c + (d - c) * sx) * sy


def ground_color(x, y, tex=None):
    """x,y in metres (ground plane). Returns RGB 0..1."""
    if tex is not None:
        img, mpp = tex
        h, w, _ = img.shape
        px = np.clip((x / mpp + w / 2).astype(np.int64), 0, w - 1)
        py = np.clip((-y / mpp + h / 2).astype(np.int64), 0, h - 1)
        return img[py, px]
    base = np.array([0.72, 0.62, 0.47])
    n = (0.55 * value_noise(x, y, 400.0, 1) + 0.3 * value_noise(x, y, 60.0, 2) + 0.15 * value_noise(x, y, 8.0, 3))
    col = base[None, :] * (0.75 + 0.45 * n[:, None])
    bush = (value_noise(x, y, 2.5, 7) > 0.9) & (value_noise(x, y, 90.0, 9) > 0.35)   # sparse shrub patches
    col[bush] *= 0.55
    road = np.abs(y - 0.35 * x - 120) < 3.0                     # a dirt road for scale/orientation
    col[road] = [0.80, 0.74, 0.62]
    pad = (np.abs(x) < 6) & (np.abs(y) < 6)                     # launch pad
    col[pad] = [0.85, 0.85, 0.85]
    return col


# ----------------------------------------------------------------------------- render
def render(meshes, cam, cfg):
    out = cfg.get('output', {})
    W, H = int(out.get('width', 3840)), int(out.get('height', 2160))
    ss = int(out.get('supersample', 1))
    world = cfg.get('world', {})
    units = float(cfg.get('units_to_m', 0.001))
    lens = load_lens(Path(cfg.get('lens', {}).get('profile', DEFAULT_PROFILE)), W, H)

    # model -> world: rocket axis to +Z, optional pitch from vertical, lens at altitude
    axis = unit(cfg.get('rocket', {}).get('axis', [0, 0, 1]))
    Rm = rot_x(float(world.get('pitch_deg', 0.0))) @ rot_a_to_b(axis, [0, 0, 1])
    p_cam_model = np.asarray(cam['position'], float)
    alt = float(world.get('altitude_m', 300.0))
    def to_world(P):
        return ((np.asarray(P, float) - p_cam_model) * units) @ Rm.T + np.array([0, 0, alt])

    # camera orientation in model frame
    if 'look' in cam:
        look = unit(cam['look'])
        up_hint = unit(cam.get('up', cam.get('radial', [1, 0, 0])))
    else:
        radial = unit(cam['radial'])
        t = math.radians(float(cam.get('tilt_deg', 7.0)))
        look = unit(-axis * math.cos(t) + radial * math.sin(t))   # aft, tilted outward
        up_hint = radial                                           # image top = away from tube
    up = unit(up_hint - np.dot(up_hint, look) * look)
    roll = math.radians(float(cam.get('roll_deg', 0.0)))
    right0 = np.cross(-up, look)          # x = y(down) x z(forward)
    right = unit(right0 * math.cos(roll) + up * math.sin(roll))
    down = np.cross(look, right)          # y = z x x
    Rc = np.stack([right, down, look], axis=1)                       # camera->model
    Rcw = Rm @ Rc                                                    # camera->world

    # scene
    scene = o3d.t.geometry.RaycastingScene()
    colors = []
    for m, col in meshes:
        V = to_world(np.asarray(m.vertices))
        F = np.asarray(m.triangles, np.int32)
        tm = o3d.t.geometry.TriangleMesh()
        tm.vertex.positions = o3d.core.Tensor(V.astype(np.float32))
        tm.triangle.indices = o3d.core.Tensor(F)
        colors.append(np.array(col, float) / 255.0)
        scene.add_triangles(tm)

    dirs_c, tmax = pixel_rays(W, H, lens, ss)
    valid = ~np.isnan(dirs_c[..., 0])
    d = np.nan_to_num(dirs_c.reshape(-1, 3)) @ Rcw.T.astype(np.float32)
    o = np.zeros_like(d)
    o[:, 2] = alt
    ans = scene.cast_rays(o3d.core.Tensor(np.hstack([o, d]).astype(np.float32)))
    t_hit = ans['t_hit'].numpy()
    gid = ans['geometry_ids'].numpy()
    nrm = ans['primitive_normals'].numpy()

    sun_el, sun_az = math.radians(world.get('sun_elevation_deg', 55)), math.radians(world.get('sun_azimuth_deg', 30))
    sun = np.array([math.cos(sun_el) * math.cos(sun_az), math.cos(sun_el) * math.sin(sun_az), math.sin(sun_el)], np.float32)
    amb = 0.38

    img = np.zeros((d.shape[0], 3), np.float32)
    # sky
    zen = np.clip(d[:, 2], -1, 1)
    horizon, top = np.array([0.80, 0.85, 0.90]), np.array([0.33, 0.52, 0.80])
    k = np.clip(zen, 0, 1)[:, None] ** 0.5
    img[:] = horizon * (1 - k) + top * k
    # ground
    tg = np.where(d[:, 2] < -1e-6, -alt / np.minimum(d[:, 2], -1e-6), np.inf)
    rocket = np.isfinite(t_hit) & (t_hit < tg)
    gsel = np.isfinite(tg) & ~rocket
    tex = None
    if world.get('ground_texture'):
        timg = np.asarray(Image.open(world['ground_texture']).convert('RGB'), np.float32) / 255.0
        tex = (timg, float(world.get('ground_m_per_px', 0.5)))
    gp = o[gsel] + d[gsel] * tg[gsel][:, None]
    gcol = ground_color(gp[:, 0], gp[:, 1], tex) * (amb + (1 - amb) * max(sun[2], 0))
    haze = 1 - np.exp(-tg[gsel] / 25000.0)
    img[gsel] = gcol * (1 - haze[:, None]) + horizon * haze[:, None]
    # rocket
    if rocket.any():
        idx = np.nonzero(rocket)[0]
        n = nrm[idx]
        n = np.where((np.sum(n * d[idx], 1) > 0)[:, None], -n, n)
        base = np.stack(colors)[gid[idx]]
        lam = np.clip(n @ sun, 0, 1)
        hp = o[idx] + d[idx] * t_hit[idx][:, None] + n * 1e-4
        sh = scene.test_occlusions(o3d.core.Tensor(np.hstack([hp, np.tile(sun, (len(idx), 1))]).astype(np.float32))).numpy()
        lam = np.where(sh, 0, lam)
        spec = np.clip(np.sum((sun - 2 * (sun @ n.T)[:, None] * n) * d[idx], 1), 0, 1) ** 24 * 0.25
        img[idx] = base * (amb + (1 - amb) * lam[:, None]) + spec[:, None] * (~sh)[:, None]

    img = img.reshape(H * ss, W * ss, 3)
    img[~valid] = 0.0                                                # outside the lens model
    if ss > 1:
        img = img.reshape(H, ss, W, ss, 3).mean(axis=(1, 3))
        valid = valid.reshape(H, ss, W, ss).any(axis=(1, 3))
        rocket_frac = rocket.reshape(H, ss, W, ss).mean()
    else:
        rocket_frac = rocket.mean()
    out_img = Image.fromarray((np.clip(img, 0, 1) ** (1 / 1.1) * 255).astype(np.uint8))
    stats = dict(rocket_fraction=float(rocket_frac), lens_theta_max_deg=tmax,
                 hfov_deg=_fov(lens, W, H, 'h'), vfov_deg=_fov(lens, W, H, 'v'))
    return out_img, stats


def _fov(lens, W, H, which):
    fx, fy, cx, cy, D = lens
    k1, k2, k3, k4 = D
    def ang(xd):
        rd, th = abs(xd), min(abs(xd), 1.5)
        for _ in range(30):
            t2 = th * th
            th -= (th * (1 + t2 * (k1 + t2 * (k2 + t2 * (k3 + t2 * k4)))) - rd) / (1 + t2 * (3 * k1 + t2 * (5 * k2 + t2 * (7 * k3 + t2 * 9 * k4))))
        return math.degrees(th)
    if which == 'h':
        return ang((0 - cx) / fx) + ang((W - cx) / fx)
    return ang((0 - cy) / fy) + ang((H - cy) / fy)


# ----------------------------------------------------------------------------- CLI
def load_meshes(cfg, base: Path):
    out = []
    for m in cfg.get('mesh', []):
        path = (base / m['file']).resolve()
        mesh = o3d.io.read_triangle_mesh(str(path))
        if len(mesh.triangles) == 0:
            sys.exit(f'could not read triangles from {path}')
        out.append((mesh, tuple(m.get('color', [200, 205, 215]))))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('config', nargs='?', help='TOML config (see example.toml)')
    ap.add_argument('--demo', action='store_true', help='render the built-in aero-control rocket')
    ap.add_argument('--lens-height', type=float, default=5.0, help='demo: lens centre above skin [mm]')
    ap.add_argument('--tilt', type=float, default=7.0, help='demo: outward tilt [deg]')
    ap.add_argument('--cam-z', type=float, default=795.0, help='demo: lens height above the tail [mm]')
    ap.add_argument('--altitude', type=float, default=None, help='override altitude [m]')
    ap.add_argument('--pitch', type=float, default=None, help='override rocket tilt from vertical [deg]')
    ap.add_argument('--roll', type=float, default=None, help='override camera roll about the lens axis [deg]')
    ap.add_argument('--sun-el', type=float, default=None, help='override sun elevation [deg]')
    ap.add_argument('--out', default=None, help='output PNG')
    ap.add_argument('--width', type=int, default=None)
    ap.add_argument('--supersample', type=int, default=None)
    a = ap.parse_args(argv)

    if a.demo:
        cfg = {'output': {'width': 1920, 'height': 1080, 'supersample': 2, 'file': 'demo.png'},
               'world': {'altitude_m': 300.0}}
        meshes, cam = demo_rocket(a.lens_height, a.tilt, a.cam_z)
    elif a.config:
        cpath = Path(a.config)
        cfg = tomllib.loads(cpath.read_text())
        if 'lens' in cfg and 'profile' in cfg['lens']:
            cfg['lens']['profile'] = str((cpath.parent / cfg['lens']['profile']).resolve())
        if cfg.get('world', {}).get('ground_texture'):
            cfg['world']['ground_texture'] = str((cpath.parent / cfg['world']['ground_texture']).resolve())
        meshes = load_meshes(cfg, cpath.parent)
        cam = cfg['camera']
        cfg['units_to_m'] = {'mm': 0.001, 'cm': 0.01, 'm': 1.0, 'in': 0.0254}[cfg.get('units', 'mm')]
    else:
        ap.error('give a config file or --demo')

    o = cfg.setdefault('output', {})
    if a.width:
        o['width'], o['height'] = a.width, round(a.width * 9 / 16)
    if a.supersample:
        o['supersample'] = a.supersample
    wld = cfg.setdefault('world', {})
    if a.altitude is not None:
        wld['altitude_m'] = a.altitude
    if a.pitch is not None:
        wld['pitch_deg'] = a.pitch
    if a.sun_el is not None:
        wld['sun_elevation_deg'] = a.sun_el
    if a.roll is not None:
        cam['roll_deg'] = a.roll
    out = a.out or o.get('file', 'frame.png')
    img, stats = render(meshes, cam, cfg)
    img.save(out)
    print(f'wrote {out}  {img.size[0]}x{img.size[1]}  rocket in frame: {stats["rocket_fraction"]*100:.1f}%  '
          f'FOV {stats["hfov_deg"]:.0f}x{stats["vfov_deg"]:.0f} deg')


if __name__ == '__main__':
    main()
