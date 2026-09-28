"""One further local grid at the stable 15-degree low-Mach condition."""
import hashlib
import json
import re
import shutil
import time
from pathlib import Path
import local_study as study

HERE = study.HERE
ROOT = study.ROOT


def state(**kw):
    study.save(HERE/'third_grid_status.json', dict(updated=time.time(), **kw))
    print(json.dumps(kw), flush=True)


def main():
    study.status = state
    mesh = HERE/'local/d15/mesh_r40'
    case = HERE/'local/d15/M0.30_r40'
    if (case/'result.json').exists():
        state(state='READY_FOR_REVIEW', result=str(case/'result.json'))
        return
    repairing = mesh.exists() and (mesh/'quality_repair.json').exists()
    if case.exists() or (mesh.exists() and not repairing):
        raise RuntimeError('Partial third-grid work exists; inspect it before resuming')
    if shutil.disk_usage(ROOT).free < 18*1024**3:
        raise RuntimeError('Third grid requires at least 18 GiB free')
    source = HERE/'local/d15/mesh_r10over7'
    if repairing:
        marker=json.loads((mesh/'quality_repair.json').read_text())
        assert not marker['attempted'], 'Quality repair already attempted; inspect before any further work'
        marker['attempted']=True; study.save(mesh/'quality_repair.json',marker)
        for p in mesh.glob('log.*'): p.rename(p.with_name(p.name+'.initial'))
        for p in mesh.glob('processor[0-9]*'): shutil.rmtree(p)
        path=mesh/'system/snappyHexMeshDict'
        text,n=re.subn(r'(maxBoundarySkewness\s+)20;',r'\g<1>4;',path.read_text())
        assert n==1; path.write_text(text)
    else:
        mesh.mkdir(parents=True)
        shutil.copytree(source/'system', mesh/'system')
        shutil.copytree(source/'constant', mesh/'constant', ignore=shutil.ignore_patterns('polyMesh','extendedFeatureEdgeMesh'))
        path = mesh/'system/blockMeshDict'
        text = path.read_text()
        assert text.count('(30 30 160)') == 1
        path.write_text(text.replace('(30 30 160)', '(40 40 214)'))
    for p in (mesh/'constant/triSurface').glob('*.stl'):
        assert p.read_bytes() == (source/'constant/triSurface'/p.name).read_bytes()
    study.configure_procs(mesh)
    for command, label in [('surfaceFeatureExtract','surfaceFeatureExtract'),('blockMesh','blockMesh'),
                           ('decomposePar -force','decomposePar'),('mpirun -np 6 snappyHexMesh -parallel -overwrite','snappyHexMesh'),
                           ('mpirun -np 6 checkMesh -parallel','checkMesh')]:
        study.run(mesh, command, label)
    check = (mesh/'log.checkMesh').read_text()
    assert 'Mesh OK.' in check, 'checkMesh rejected the grid; see log.checkMesh'
    cells = int(re.search(r'cells:\s+(\d+)', check).group(1))
    assert cells <= 6_000_000, 'Final mesh exceeds local memory guard'
    study.run(mesh, 'reconstructParMesh -constant', 'reconstructParMesh')
    study.run(mesh, 'renumberMesh -overwrite -constant', 'renumberMesh')
    for p in mesh.glob('processor[0-9]*'): shutil.rmtree(p)
    study.save(mesh/'mesh_report.json', dict(ok=True,cells=cells,baseResolution=[40,40,214],
               layer_coverage=study.rs.parse_layer_coverage((mesh/'log.snappyHexMesh').read_text())))
    previous = HERE/'local/d15/M0.30_r10over7'
    case.mkdir()
    for name in ['system','constant','0.orig']:
        shutil.copytree(previous/name,case/name,ignore=shutil.ignore_patterns('polyMesh'))
    (case/'constant/polyMesh').symlink_to(mesh/'constant/polyMesh', target_is_directory=True)
    shutil.copytree(case/'0.orig',case/'0')
    for name in ['system/fvSchemes','system/fvSolution','constant/thermophysicalProperties','constant/turbulenceProperties','0/U','0/p']:
        assert (case/name).read_bytes() == (previous/name).read_bytes()
    study.run(case,'decomposePar -force','decomposePar')
    for end in [3000,4000,5000,6000]:
        path=case/'system/flowSettings'
        text,n=re.subn(r'^endTime\s+[^;]+;',f'endTime {end};',path.read_text(),flags=re.M)
        assert n==1; path.write_text(text)
        study.run(case,'mpirun -np 6 rhoSimpleFoam -parallel',f'rhoSimpleFoam_{end}')
        stats=study.statistics(case); study.save(case/'statistics.json',stats)
        if stats['meanStable']: break
    study.run(case,'reconstructPar -latestTime','reconstructPar')
    for p in case.glob('processor[0-9]*'): shutil.rmtree(p)
    old=study.statistics(previous)
    changes={k:100*(stats['metrics'][k]['mean']/old['metrics'][k]['mean']-1) for k in ['roll','yaw','axial','side']}
    study.save(case/'result.json',dict(solver='OpenFOAM',mach=.3,deflection=15,mesh=str(mesh),
        previous=old,refined=stats,relativeDeltaPct=changes,qualified=False,
        note='Third grid at one condition. Review geometry capture, y+, convergence and spatial trend before qualifying any data.'))
    state(state='READY_FOR_REVIEW',meanStable=stats['meanStable'],relativeDeltaPct=changes)


if __name__=='__main__':
    try: main()
    except Exception as error:
        state(state='NEEDS_REVIEW',error=str(error))
        raise
