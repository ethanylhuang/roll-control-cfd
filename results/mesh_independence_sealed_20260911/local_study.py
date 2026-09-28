"""Sealed-CAD grid check (2026-09-11): background 21x21x112 -> 30x30x160 with snappy levels, layers and physics fixed.
Serial, isolated; never touches the sweep cases. Adapted from results/mesh_independence_20260909/local_study.py."""
import hashlib, json, os, re, shlex, shutil, subprocess, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT/'pipeline'), '/Users/trasomi/.claude/skills/cfd-sweep/scripts']
import numpy as np
import foamutil
import run_sweep as rs
NPROC = int(os.environ.get('NPROC', '8'))
FOAM = '/Applications/OpenFOAM-v2606.app/Contents/Resources/etc/openfoam'
MESH_NAME = 'mesh_sealedcad_fine'; CASE_SUFFIX = 'sealedcad_fine_opensides'
JOBS = [(t, float(m)) for t, m in (j.split(':') for j in os.environ.get('JOBS', 'd03:0.3,d15:0.85,d10:0.6').split(','))]
RES = tuple(int(x) for x in os.environ.get('RES', '30,30,160').split(',')); RES_TAG = os.environ.get('RES_TAG', 'r30')

def save(path, obj):
    temp = path.with_suffix(path.suffix+'.tmp'); temp.write_text(json.dumps(obj, indent=2, allow_nan=False)+'\n'); temp.replace(path)
def status(**kw):
    save(HERE/f'local_status_{RES_TAG}.json', dict(updated=time.time(), **kw)); print(time.strftime('%H:%M:%S'), json.dumps(kw), flush=True)
def run(case, command, label, timeout=10*3600):
    status(state='RUNNING', case=str(case), stage=label)
    with (case/f'log.{label}').open('w') as log:
        p = subprocess.run([FOAM, '-c', f'cd {shlex.quote(str(case))} && {command}'], stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
    if p.returncode: raise RuntimeError(f'{label} failed ({p.returncode}); see {case}/log.{label}')
def configure_procs(case):
    p = case/'system/flowSettings'; s, n = re.subn(r'^nProcs\s+[^;]+;', f'nProcs {NPROC};', p.read_text(), flags=re.M); assert n == 1; p.write_text(s)
def patch_faces(mesh):
    t = (mesh/'constant/polyMesh/boundary').read_text()
    return {name: int(nf) for name, nf in re.findall(r'\n\s*(\w+)\s*\{[^}]*?nFaces\s+(\d+);', t) if name.startswith('rocket')}

def mesh(tag):
    source = ROOT/f'runs_v4/{tag}/{MESH_NAME}'; target = HERE/f'local/{tag}/mesh_{RES_TAG}'
    if (target/'mesh_report.json').exists():
        report = json.loads((target/'mesh_report.json').read_text()); assert report['ok']; return target
    if target.exists(): raise RuntimeError(f'Incomplete mesh exists; inspect before restarting: {target}')
    if shutil.disk_usage(ROOT).free < 8*1024**3: raise RuntimeError('Less than 8 GiB free; no new mesh started')
    target.mkdir(parents=True)
    shutil.copytree(source/'system', target/'system')
    shutil.copytree(source/'constant', target/'constant', ignore=shutil.ignore_patterns('polyMesh', 'extendedFeatureEdgeMesh'))
    p = target/'system/blockMeshDict'; s = p.read_text(); assert s.count('(21 21 112)') == 1
    p.write_text(s.replace('(21 21 112)', '(%d %d %d)' % RES))
    configure_procs(target)
    manifest = {q.name: hashlib.sha256(q.read_bytes()).hexdigest() for q in (target/'constant/triSurface').glob('*.stl')}
    for name, digest in manifest.items(): assert hashlib.sha256((source/'constant/triSurface'/name).read_bytes()).hexdigest() == digest
    save(target/'source_audit.json', dict(source=str(source), geometrySHA256=manifest, baseResolution=[21, 21, 112], newResolution=list(RES),
         invariant='Same STL, domain, refinement levels and regions, snapping, relative layer and quality controls'))
    for cmd, label in [('surfaceFeatureExtract', 'surfaceFeatureExtract'), ('blockMesh', 'blockMesh'), ('decomposePar -force', 'decomposePar'),
                       (f'mpirun -np {NPROC} snappyHexMesh -parallel -overwrite', 'snappyHexMesh'), (f'mpirun -np {NPROC} checkMesh -parallel', 'checkMesh')]:
        run(target, cmd, label)
    check = (target/'log.checkMesh').read_text(); ok = 'Mesh OK.' in check
    if not ok:
        save(target/'mesh_report.json', dict(ok=False, checkLog=str(target/'log.checkMesh'))); raise RuntimeError('Refined mesh did not pass checkMesh; solver not started')
    cells = int(re.search(r'cells:\s+(\d+)', check).group(1))
    if cells > 7_000_000: raise RuntimeError(f'{cells} cells exceeds local memory guard')
    coverage = rs.parse_layer_coverage((target/'log.snappyHexMesh').read_text())
    run(target, 'reconstructParMesh -constant', 'reconstructParMesh'); run(target, 'renumberMesh -overwrite -constant', 'renumberMesh')
    for q in target.glob('processor[0-9]*'): shutil.rmtree(q)
    save(target/'mesh_report.json', dict(ok=True, cells=cells, layer_coverage=coverage, baseResolution=list(RES), source=str(source),
         patch_faces=patch_faces(target), source_patch_faces=patch_faces(source)))
    return target

def statistics(case):
    _, m = foamutil.parse_dat(foamutil.find_fo_file(str(case), 'forces_all', 'moment.dat'))
    _, f = foamutil.parse_dat(foamutil.find_fo_file(str(case), 'forces_all', 'force.dat'))
    m = m[-1000:]; f = f[-1000:]; assert len(m) == 1000 and len(f) == 1000 and np.allclose(m[:, 0], f[:, 0])
    series = {'roll': -m[:, 3], 'yaw': m[:, 1]-.069*f[:, 2], 'pitch': m[:, 2]+.069*f[:, 1], 'axial': -f[:, 3], 'side': f[:, 2], 'normal': f[:, 1]}
    stats = {}
    for key, a in series.items():
        assert np.isfinite(a).all()
        blocks = a.reshape(4, 250).mean(axis=1); mean = float(a.mean()); den = max(abs(mean), 1e-12)
        stats[key] = dict(mean=mean, rawStd=float(a.std()), blockMeans=blocks.tolist(), blockStdPct=float(100*blocks.std()/den), driftPct=float(100*abs(blocks[-1]-blocks[0])/den))
    acceptable = all(stats[k]['blockStdPct'] <= 1.0 and stats[k]['driftPct'] <= 1.0 for k in ['roll', 'axial']) and stats['yaw']['blockStdPct'] <= 3.0
    return dict(window=[float(m[0, 0]), float(m[-1, 0])], samples=len(m), metrics=stats, meanStable=acceptable)

def solve(tag, mach, refined):
    source = ROOT/f'runs_v4/{tag}/M{mach:.2f}_{CASE_SUFFIX}'; case = HERE/f'local/{tag}/M{mach:.2f}_{RES_TAG}'
    if (case/'result.json').exists(): return
    if case.exists(): raise RuntimeError(f'Incomplete case exists; inspect before restarting: {case}')
    assert (source/'result.json').exists(), f'baseline missing: {source}'
    case.mkdir(parents=True)
    for sub in ['system', '0.orig', 'constant']: shutil.copytree(source/sub, case/sub, ignore=shutil.ignore_patterns('polyMesh'))
    (case/'constant/polyMesh').symlink_to(refined/'constant/polyMesh', target_is_directory=True)
    configure_procs(case); shutil.copytree(case/'0.orig', case/'0')
    for sub in ['system/fvSchemes', 'system/fvSolution', 'constant/thermophysicalProperties', 'constant/turbulenceProperties']:
        assert (case/sub).read_bytes() == (source/sub).read_bytes()
    save(case/'source_audit.json', dict(source=str(source), mesh=str(refined), solverInvariant=True))
    run(case, 'decomposePar -force', 'decomposePar')
    for end in [3000, 4000, 5000]:
        p = case/'system/flowSettings'; s, n = re.subn(r'^endTime\s+[^;]+;', f'endTime {end};', p.read_text(), flags=re.M); assert n == 1; p.write_text(s)
        run(case, f'mpirun -np {NPROC} rhoSimpleFoam -parallel', f'rhoSimpleFoam_{end}')
        stats = statistics(case); save(case/'statistics.json', stats)
        if stats['meanStable']: break
    run(case, 'reconstructPar -latestTime', 'reconstructPar')
    for q in case.glob('processor[0-9]*'): shutil.rmtree(q)
    baseline = statistics(source)
    save(case/'result.json', dict(solver='OpenFOAM', mach=mach, deflection=int(tag[1:]) if tag[1] != 'm' else -int(tag[2:]), mesh=str(refined), source=str(source),
         resolution=list(RES), meanStable=stats['meanStable'], refined=stats, baseline=baseline,
         relativeDeltaPct={k: 100*(stats['metrics'][k]['mean']-baseline['metrics'][k]['mean'])/max(abs(baseline['metrics'][k]['mean']), 1e-12) for k in ['roll', 'yaw', 'axial', 'side']}))
    status(state='CASE_DONE', case=str(case), relativeDeltaPct=json.load(open(case/'result.json'))['relativeDeltaPct'])

if __name__ == '__main__':
    try:
        for tag, mach in JOBS: solve(tag, mach, mesh(tag))
        status(state='COMPLETE', jobs=JOBS, resolution=list(RES))
    except Exception as e:
        status(state='NEEDS_REVIEW', error=str(e)); raise
