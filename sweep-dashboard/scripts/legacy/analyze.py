# LEGACY (v4 gap sweep, frozen 2026-09-10). Outputs go to analysis/legacy and public/data/legacy-v4.
"""Reproducible analysis of the latest CFD-branch steady fine-mesh sweep.

First execution snapshots source JSONs. Subsequent executions use the snapshots.
No solver, network, spreadsheet, or Git operations.
"""
from pathlib import Path
import csv
import hashlib
import json
import math
import statistics as st
from mesh_review import annotate

ROOT = Path(__file__).resolve().parents[2]
CFD = ROOT.parent
SCRATCH = Path('/private/tmp/claude-501/-Users-trasomi-dev-cfd/e77796e5-73f1-4b54-ac10-df1a9b566759/scratchpad')
RAW = ROOT / 'analysis/legacy/raw'
OUT = ROOT / 'public/data/legacy-v4'
MACHS = [.3, .5, .6, .7, .8, .85, .9]
TAGS = ['dm06', 'd00', 'd03', 'd06', 'd09', 'd10', 'd12', 'd15']
RHO, AREA, LENGTH, ZREF = 1.18915, .0026248, .05781, .330
METRICS = ['roll', 'cl', 'yaw', 'cn', 'pitch', 'cm', 'axial', 'ca', 'side', 'cy', 'normal', 'cNormal']


def snapshot():
    RAW.mkdir(parents=True, exist_ok=True)
    manifest = []
    def add(path, solver, role, note=''):
        content = path.read_bytes()
        name = f'{solver.lower()}_{path.parent.name}_{path.name}' if solver == 'OpenFOAM' else path.name
        (RAW / name).write_bytes(content)
        manifest.append(dict(file=name, source=str(path), solver=solver, role=role,
                             note=note, sha256=hashlib.sha256(content).hexdigest()))
    for tag in TAGS:
        for mach in MACHS:
            path = CFD / f'runs_v4/{tag}/M{mach:.2f}_filled_fine_opensides/result.json'
            long = path.parent.with_name(path.parent.name + '_long') / 'result.json'
            # Keep the same steady solver family; prefer the completed extension.
            chosen = long if long.exists() else path
            add(chosen, 'OpenFOAM', 'primary', '4,000-iteration extension' if chosen == long else '')
            # Include angle in archived filename (case directory itself omits it).
            old = RAW / manifest[-1]['file']
            new = RAW / (tag + '_' + old.name)
            old.rename(new)
            manifest[-1]['file'] = new.name
    fine = sorted(SCRATCH.glob('ss_sweep_*_fine_cfd.json'))
    assert len(fine) == 36, f'Expected 36 fine CFD-branch results, got {len(fine)}'
    for path in fine:
        add(path, 'SimScale', 'primary')
    for mach in MACHS[:-1]:
        add(SCRATCH / f'ss_sweep_d10_M{mach:g}.json', 'SimScale', 'primary',
            'Fine v3 check series; same CFD CAD and settings, promoted from separate check block')
    for path in sorted(SCRATCH.glob('ss_sweep_d00_M*_coarse3.json')):
        add(path, 'SimScale', 'context', 'Coarse zero-deflection check; excluded from fine-mesh plots and fits')
    add(CFD / 'runs_v4/d15/M0.90_filled_fine_transient/result.json', 'OpenFOAM', 'context',
        'Later transient diagnostic, separate from steady sweep; reference z=0.399 from restart case')
    (ROOT / 'analysis/legacy/manifest.json').write_text(json.dumps(manifest, indent=2))


def normalize(entry):
    content = (RAW / entry['file']).read_bytes()
    assert hashlib.sha256(content).hexdigest() == entry['sha256']
    r = json.loads(content)
    m, f = r['moments_Nm'], r['forces_N']
    v = r['V_mps']
    assert abs(v - (305 if r['mach'] == .9 else round(r['mach'] * 339.1, 1))) < 1e-6
    q = .5 * RHO * v * v
    shift = r.get('cofr_z', .399) - ZREF
    roll = m['Mroll']
    pitch = m['Mpitch'] + shift * f['Fx']
    yaw = m['Myaw'] - shift * f['Fy']
    c = r.get('convergence', {})
    return dict(id=entry['file'].removesuffix('.json'), solver=entry['solver'],
                role=entry['role'], mach=r['mach'], angle=r['deflection'], velocity=v, q=q,
                roll=roll, cl=roll/(q*AREA*LENGTH), yaw=yaw, cn=yaw/(q*AREA*LENGTH),
                pitch=pitch, cm=pitch/(q*AREA*LENGTH), axial=-f['Fz'], ca=-f['Fz']/(q*AREA),
                side=f['Fy'], cy=f['Fy']/(q*AREA), normal=f['Fx'], cNormal=f['Fx']/(q*AREA),
                flags=c.get('flags', []), rawStdPct=c.get('std_rel_pct'), blockStdPct=c.get('block_std_pct'),
                driftPct=c.get('drift_pct'), meanWindow=c.get('window', r.get('n_avg_samples', 'not recorded')),
                mesh=r['mesh_name'], run=r.get('run'), note=entry['note'],
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


if not (ROOT / 'analysis/legacy/manifest.json').exists():
    snapshot()
manifest = json.loads((ROOT / 'analysis/legacy/manifest.json').read_text())
points = sorted([normalize(e) for e in manifest], key=lambda p: (p['solver'], p['mach'], p['angle']))
mesh_review = annotate(points)
primary = [p for p in points if p['role'] == 'primary']
assert len(primary) == 98
assert len({(p['solver'], p['mach'], p['angle']) for p in primary}) == 98
assert all(math.isfinite(p[k]) for p in primary for k in METRICS)
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
                                         maxAngle=hi, excludeFlagged=exclude, qualification='PROVISIONAL_NOT_DESIGN_QUALIFIED', **result))
    for angle in common:
        a = next(p for p in of if p['angle'] == angle)
        b = next(p for p in ss if p['angle'] == angle)
        for metric in METRICS:
            delta = b[metric]-a[metric]
            # Relative errors near zero are not useful; use per-Mach 1% magnitude floor.
            floor = max(abs(p[metric]) for p in of)*.01
            pairs.append(dict(mach=mach, angle=angle, metric=metric, openfoam=a[metric], simscale=b[metric],
                              delta=delta, percent=100*delta/abs(a[metric]) if abs(a[metric]) > floor else None,
                              flagged=bool(a['flags'] or b['flags']),qualification='PROVISIONAL_NOT_DESIGN_QUALIFIED'))
OUT.mkdir(parents=True, exist_ok=True)
data = dict(snapshot='2026-09-09', reference=dict(rho=RHO, area=AREA, length=LENGTH, z=ZREF),
            reviewed=mesh_review['updated'],qualification='PROVISIONAL_NOT_DESIGN_QUALIFIED',
            machs=MACHS, angles=[-6, 0, 3, 6, 9, 10, 12, 15], points=points, fits=fits, pairs=pairs)
(OUT / 'sweep.json').write_text(json.dumps(data, indent=2, allow_nan=False))
(ROOT / 'analysis/legacy/v4-gap-sweep.json').write_text(json.dumps(data, separators=(',', ':'), allow_nan=False))
write_csv('normalized.csv', primary)
write_csv('fits.csv', fits)
write_csv('comparison.csv', pairs)
(OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2))
print(f'{len(primary)} fine-mesh points; {len(pairs)//len(METRICS)} paired conditions; {len(points)-len(primary)} context points')
for mach in MACHS[:-1]:
    fs = [f for f in fits if f['mach'] == mach and f['metric'] == 'roll' and f['minAngle'] == -6 and not f['excludeFlagged']]
    a,b = fs
    print(f'M{mach:.2f}: roll slopes OF {a["slope"]:.7f}, SS {b["slope"]:.7f} Nm/deg; delta {100*(b["slope"]/a["slope"]-1):+.2f}%; R2 {a["r2"]:.5f}/{b["r2"]:.5f}')
print('Flagged primary points:',sum(bool(p['flags']) for p in primary))
