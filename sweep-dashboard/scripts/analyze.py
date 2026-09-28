"""Reproducible analysis of the sealed-tab (v5) fine-mesh sweep, 2026-09-11 .. 09-14.

First execution snapshots source JSONs into analysis/raw (SHA-256 manifest).
Subsequent executions use the snapshots; delete analysis/manifest.json to re-snapshot.
No solver, network, spreadsheet, or Git operations.

The previous (v4, 1 mm tab end clearance) sweep is frozen under analysis/legacy and
public/data/legacy-v4; it is only read here to compute sealed-vs-previous differences.
"""
from pathlib import Path
from datetime import datetime, timezone
import csv
import hashlib
import json
import math
import statistics as st

ROOT = Path(__file__).resolve().parents[1]
CFD = ROOT.parent
RAW = ROOT / 'analysis/raw'
OUT = ROOT / 'public/data'
LEGACY = ROOT / 'analysis/legacy/v4-gap-sweep.json'
STUDY = CFD / 'results/mesh_independence_sealed_20260911'
SS = CFD / 'simscale_sealed/results'
MACHS = [.3, .5, .6, .7, .8, .85, .9]
TAGS = ['dm06', 'd00', 'd03', 'd06', 'd09', 'd10', 'd12', 'd15']
RHO, AREA, LENGTH, ZREF = 1.18915, .0026248, .05781, .330
METRICS = ['roll', 'cl', 'yaw', 'cn', 'pitch', 'cm', 'axial', 'ca', 'side', 'cy', 'normal', 'cNormal']
# Transient restarts replace the steady M0.90 points whose steady mean drifted (as on the sheet).
TRANSIENT_M090 = {'d15': 'steady drift 30 %, std 18 %', 'dm06': 'steady drift 9.4 %'}
# Grid check (background refinement, same snappy levels): refined-case sources.
GRID_LOCAL = [('d03', .3), ('d10', .6), ('d15', .85)]
GRID_SS = [('d03', .3, 'ss_sweep_d03_M0.3_fine_sealed_h0.2', 'ss_sweep_d03_M0.3_refined_sealed_h0.2'),
           ('d15', .85, 'ss_sweep_d15_M0.85_fine_sealed', 'ss_sweep_d15_M0.85_refined_sealed_h0.2')]


def tag_of(angle):
    return f'dm{abs(int(angle)):02d}' if angle < 0 else f'd{int(angle):02d}'


def snapshot():
    RAW.mkdir(parents=True, exist_ok=True)
    manifest = []
    def add(path, solver, role, note='', name=None):
        content = path.read_bytes()
        name = name or path.name
        (RAW / name).write_bytes(content)
        manifest.append(dict(file=name, source=str(path), solver=solver, role=role,
                             note=note, sha256=hashlib.sha256(content).hexdigest()))
    for tag in TAGS:
        for mach in MACHS:
            steady = CFD / f'runs_v4/{tag}/M{mach:.2f}_sealedcad_fine_opensides/result.json'
            if mach == .9 and tag in TRANSIENT_M090:
                transient = CFD / f'runs_v4/{tag}/M0.90_sealedcad_fine_transient/result.json'
                add(transient, 'OpenFOAM', 'primary',
                    f'Transient rhoPimpleFoam restart (15 ms) replaces the steady mean ({TRANSIENT_M090[tag]}).',
                    f'openfoam_{tag}_M0.90_transient.json')
                add(steady, 'OpenFOAM', 'context', 'Steady mean superseded by the transient restart.',
                    f'openfoam_{tag}_M0.90_steady.json')
            else:
                add(steady, 'OpenFOAM', 'primary', name=f'openfoam_{tag}_M{mach:.2f}.json')
    for tag in TAGS:
        for mach in MACHS[:-1]:
            add(SS / f'ss_sweep_{tag}_M{mach:g}_fine_sealed.json', 'SimScale', 'primary')
    add(CFD / 'runs_v4/d15/M1.20_sealedcad_fine_transient/result.json', 'OpenFOAM', 'supersonic',
        'Recommended M1.2 value: transient restart from the SIMPLEC steady, 10 ms, flat from 1.5 ms.',
        'openfoam_d15_M1.20_transient.json')
    add(CFD / 'runs_v4/d15/M1.20_sealedcad_fine_restart/result.json', 'OpenFOAM', 'supersonic',
        'Steady transonic-SIMPLEC restart from M0.90; not a fixed point of the transient (upper bound, +8 %).',
        'openfoam_d15_M1.20_steady.json')
    for tag, mach in GRID_LOCAL:
        add(STUDY / f'local/{tag}/M{mach:.2f}_r30/result.json', 'OpenFOAM', 'grid',
            name=f'grid_openfoam_{tag}_M{mach:.2f}_r30.json')
        add(STUDY / f'local/{tag}/mesh_r30/mesh_report.json', 'OpenFOAM', 'grid-mesh',
            name=f'grid_openfoam_{tag}_mesh_r30.json')
        add(CFD / f'runs_v4/{tag}/mesh_sealedcad_fine/mesh_report.json', 'OpenFOAM', 'grid-mesh',
            name=f'grid_openfoam_{tag}_mesh_fine.json')
    for _, _, fine, refined in GRID_SS:
        for name in (fine, refined):
            if not (RAW / f'{name}.json').exists() or name.endswith('h0.2'):
                add(SS / f'{name}.json', 'SimScale', 'grid')
    (ROOT / 'analysis/manifest.json').write_text(json.dumps(manifest, indent=2))


def load(entry):
    content = (RAW / entry['file']).read_bytes()
    assert hashlib.sha256(content).hexdigest() == entry['sha256'], entry['file']
    return json.loads(content)


def normalize(entry):
    r = load(entry)
    m, f = r['moments_Nm'], r['forces_N']
    v = r['V_mps']
    q = .5 * RHO * v * v
    shift = r.get('cofr_z', .399) - ZREF
    roll = m['Mroll']
    pitch = m['Mpitch'] + shift * f['Fx']
    yaw = m['Myaw'] - shift * f['Fy']
    c = r.get('convergence', {})
    transient = 'rhoPimpleFoam' in r.get('solver', '')
    window = r.get('window')
    if isinstance(window, dict) and 't_start' in window:
        window = f"{window['n']} steps, t {window['t_start']*1e3:.2f}–{window['t_end']*1e3:.2f} ms"
    elif isinstance(window, dict):
        window = f"{window['n']} iterations, {window['it_start']}–{window['it_end']}"
    return dict(id=entry['file'].removesuffix('.json'), solver=entry['solver'],
                role=entry['role'], mach=r['mach'], angle=r['deflection'], velocity=v, q=q,
                method='transient' if transient else 'steady',
                roll=roll, cl=roll/(q*AREA*LENGTH), yaw=yaw, cn=yaw/(q*AREA*LENGTH),
                pitch=pitch, cm=pitch/(q*AREA*LENGTH), axial=-f['Fz'], ca=-f['Fz']/(q*AREA),
                side=f['Fy'], cy=f['Fy']/(q*AREA), normal=f['Fx'], cNormal=f['Fx']/(q*AREA),
                flags=c.get('flags', []), rawStdPct=c.get('std_rel_pct'), blockStdPct=c.get('block_std_pct'),
                driftPct=c.get('drift_pct'), meanWindow=window or r.get('n_avg_samples', 'not recorded'),
                mesh=r.get('mesh_name', ''), run=r.get('run'), note=entry['note'],
                source=entry['source'], sha256=entry['sha256'], rawFile=entry['file'])


def fit(points, metric):
    n = len(points)
    if n < 3:
        return None
    x, y = [p['angle'] for p in points], [p[metric] for p in points]
    xb, yb = st.mean(x), st.mean(y)
    sxx = sum((v-xb)**2 for v in x)
    a = sum((xi-xb)*(yi-yb) for xi, yi in zip(x, y))/sxx
    b = yb-a*xb
    sse = sum((yi-a*xi-b)**2 for xi, yi in zip(x, y))
    sst = sum((yi-yb)**2 for yi in y)
    return dict(n=n, slope=a, slopePerRad=a*180/math.pi, intercept=b,
                r2=1-sse/sst if sst else None, rmse=math.sqrt(sse/n),
                slopeSE=math.sqrt(sse/(n-2)/sxx), angles=x)


def write_csv(name, rows):
    with (OUT / name).open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def grid_study(manifest, primary):
    by = {e['file'].removesuffix('.json'): e for e in manifest}
    cases = []
    for tag, mach in GRID_LOCAL:
        r = load(by[f'grid_openfoam_{tag}_M{mach:.2f}_r30'])
        fine, ref = load(by[f'grid_openfoam_{tag}_mesh_fine']), load(by[f'grid_openfoam_{tag}_mesh_r30'])
        d = r['relativeDeltaPct']
        cases.append(dict(solver='OpenFOAM', angle=r['deflection'], mach=r['mach'],
            baselineRoll=r['baseline']['metrics']['roll']['mean'], refinedRoll=r['refined']['metrics']['roll']['mean'],
            rollDeltaPct=d['roll'], yawDeltaPct=d['yaw'], axialDeltaPct=d['axial'], sideDeltaPct=d['side'],
            baselineCells=fine['cells'], refinedCells=ref['cells'],
            grid='21×21×112 → 30×30×160 background', stable=bool(r['meanStable'])))
    for tag, mach, fine_name, ref_name in GRID_SS:
        a, b = load(by[fine_name]), load(by[ref_name])
        pct = lambda get: 100*(get(b)/get(a)-1)
        cases.append(dict(solver='SimScale', angle=a['deflection'], mach=a['mach'],
            baselineRoll=a['moments_Nm']['Mroll'], refinedRoll=b['moments_Nm']['Mroll'],
            rollDeltaPct=pct(lambda r: r['moments_Nm']['Mroll']), yawDeltaPct=pct(lambda r: r['moments_Nm']['Myaw']),
            axialDeltaPct=pct(lambda r: r['forces_N']['Fz']), sideDeltaPct=pct(lambda r: r['forces_N']['Fy']),
            baselineCells=1.60e6, refinedCells=3.22e6, grid='25×25×118 → 36×36×169 background',
            stable=(b['convergence'].get('block_std_pct') or 99) < 1))
    for c in cases:
        c['pass'] = abs(c['rollDeltaPct']) <= 2
    return dict(updated=datetime.now(timezone.utc).isoformat(), cases=cases,
        conclusion='Local OpenFOAM: roll changes ≤1.5 % at all three test points, so the fine mesh is adopted. '
                   'SimScale: 15°/M0.85 passes (−1.4 %); 3°/M0.30 does not (−45 %), and that failure is unexplained.',
        notes=[
            'The sealed CAD fills the tab end clearances, so refinement no longer re-opens a gap (the previous study\'s −30 % came from that).',
            'Axial force: local OpenFOAM changes by about 1–3 % on refinement; SimScale 15°/M0.85 by −7.7 % (toward the local value). Treat CA as grid-sensitive.',
            'Yaw and side force at 3° are near-cancellations (+53 % / +40 %) and are not resolved on either grid.',
            'The SimScale 3°/M0.30 refined mesh captures every wall face with the same area as the fine mesh; the drop tracks a stronger limit cycle (raw scatter 22.7 % vs 8.8 %) and is attributed to the solver on that mesh, not to geometry.',
            'M0.90 and M1.2 were not grid-checked.'],
        policy='Roll-moment pass threshold ±2 %. Relative changes are not accuracy bounds.')


if not (ROOT / 'analysis/manifest.json').exists():
    snapshot()
manifest = json.loads((ROOT / 'analysis/manifest.json').read_text())
swept = [e for e in manifest if e['role'] in ('primary', 'context', 'supersonic')]
points = sorted([normalize(e) for e in swept], key=lambda p: (p['solver'], p['mach'], p['angle'], p['role']))
primary = [p for p in points if p['role'] == 'primary']
assert len(primary) == 104, len(primary)
assert len({(p['solver'], p['mach'], p['angle']) for p in primary}) == 104
assert all(math.isfinite(p[k]) for p in primary for k in METRICS)

grid = grid_study(manifest, primary)
checked = {(c['solver'], c['mach'], c['angle']): c for c in grid['cases']}
for p in points:
    c = checked.get((p['solver'], p['mach'], p['angle']))
    if c:
        p['verificationStatus'] = 'GRID_PASS' if c['pass'] else 'GRID_FAIL'
        p['verificationNote'] = f"Grid-check point: refinement changes roll by {c['rollDeltaPct']:+.2f} %."
    elif p['mach'] > .85:
        p['verificationStatus'] = 'NOT_CHECKED'
        p['verificationNote'] = 'Transonic/supersonic: outside the grid check (M0.30–0.85).'
    else:
        p['verificationStatus'] = 'FINE_MESH_ADOPTED'
        p['verificationNote'] = ('Inside the grid-checked envelope (M0.30–0.85). '
                                 + ('Local grid check passed at all three corners.' if p['solver'] == 'OpenFOAM'
                                    else 'SimScale check: 15°/M0.85 passed, 3°/M0.30 failed.'))
    p['qualified'] = p['verificationStatus'] in ('GRID_PASS', 'FINE_MESH_ADOPTED') and p['solver'] == 'OpenFOAM'

fits, pairs = [], []
for mach in MACHS:
    of = [p for p in primary if p['mach'] == mach and p['solver'] == 'OpenFOAM']
    ss = [p for p in primary if p['mach'] == mach and p['solver'] == 'SimScale']
    common = sorted(set(p['angle'] for p in of) & set(p['angle'] for p in ss))
    for lo, hi in [(-6, 15), (0, 10), (0, 15)]:
        for exclude in [False, True]:
            allowed = common if ss else [p['angle'] for p in of]
            if exclude:
                flagged = {p['angle'] for p in of+ss if p['flags']}
                allowed = [a for a in allowed if a not in flagged]
            for solver, rows in [('OpenFOAM', of), ('SimScale', ss)]:
                selected = [p for p in rows if p['angle'] in allowed and lo <= p['angle'] <= hi]
                for metric in METRICS:
                    result = fit(selected, metric)
                    if result:
                        fits.append(dict(solver=solver, mach=mach, metric=metric, minAngle=lo,
                                         maxAngle=hi, excludeFlagged=exclude, **result))
    for angle in common:
        a = next(p for p in of if p['angle'] == angle)
        b = next(p for p in ss if p['angle'] == angle)
        for metric in METRICS:
            delta = b[metric]-a[metric]
            # Ratio form, so a larger magnitude reads positive at negative deflections too.
            # Relative errors near zero are not useful; use per-Mach 1% magnitude floor.
            floor = max(abs(p[metric]) for p in of)*.01
            pairs.append(dict(mach=mach, angle=angle, metric=metric, openfoam=a[metric], simscale=b[metric],
                              delta=delta, percent=100*(b[metric]/a[metric]-1) if abs(a[metric]) > floor else None,
                              flagged=bool(a['flags'] or b['flags'])))

# Sealed vs previous (v4, 1 mm end clearance) sweep: same solver, Mach, deflection.
legacy = json.loads(LEGACY.read_text())
old = {(p['solver'], p['mach'], p['angle']): p for p in legacy['points'] if p['role'] == 'primary'}
previous = []
for p in primary:
    o = old.get((p['solver'], p['mach'], p['angle']))
    if not o:
        continue
    for metric in METRICS:
        floor = max(abs(q[metric]) for q in primary if q['solver'] == p['solver'] and q['mach'] == p['mach'])*.01
        previous.append(dict(solver=p['solver'], mach=p['mach'], angle=p['angle'], metric=metric,
                             sealed=p[metric], previous=o[metric], delta=p[metric]-o[metric],
                             percent=100*(p[metric]/o[metric]-1) if abs(o[metric]) > floor else None,
                             sealedMethod=p['method'], previousFlagged=bool(o['flags'])))

OUT.mkdir(parents=True, exist_ok=True)
data = dict(snapshot='2026-09-14', dataset='v5 sealed-tab sweep',
            reference=dict(rho=RHO, area=AREA, length=LENGTH, z=ZREF),
            reviewed=datetime.now().date().isoformat(),
            machs=MACHS, angles=[-6, 0, 3, 6, 9, 10, 12, 15], points=points, fits=fits, pairs=pairs,
            previous=previous, grid=grid,
            media=[dict(title='15° / M0.90 transient', src='/media/d15_M0.90_sealedcad_fine_transient.mp4'),
                   dict(title='15° / M1.2 transient', src='/media/d15_M1.20_sealedcad_fine_transient.mp4')])
(OUT / 'sweep.json').write_text(json.dumps(data, indent=2, allow_nan=False))
(ROOT / 'analysis/sweep.json').write_text(json.dumps(data, separators=(',', ':'), allow_nan=False))
(OUT / 'mesh-study.json').write_text(json.dumps(grid, indent=2, allow_nan=False) + '\n')
write_csv('normalized.csv', [{k: v for k, v in p.items()} for p in points])
write_csv('fits.csv', fits)
write_csv('comparison.csv', pairs)
write_csv('previous-sweep.csv', previous)
(OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2))
print(f'{len(primary)} primary points; {len(pairs)//len(METRICS)} paired conditions; '
      f'{len(previous)//len(METRICS)} sealed-vs-previous pairs; {len(points)-len(primary)} context/supersonic points')
for mach in MACHS[:-1]:
    a, b = [f for f in fits if f['mach'] == mach and f['metric'] == 'roll' and f['minAngle'] == -6 and not f['excludeFlagged']]
    print(f'M{mach:.2f}: roll slopes OF {a["slope"]:.6f}, SS {b["slope"]:.6f} N·m/deg; delta {100*(b["slope"]/a["slope"]-1):+.2f}%; R2 {a["r2"]:.4f}/{b["r2"]:.4f}')
for c in grid['cases']:
    print(f"grid {c['solver']:8} {c['angle']:>4}°/M{c['mach']:.2f}: roll {c['rollDeltaPct']:+.2f}% {'PASS' if c['pass'] else 'FAIL'}")
print('Flagged primary points:', sum(bool(p['flags']) for p in primary))
