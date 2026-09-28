"""Extend only drifting reference cases, after the serial refinement queue ends."""
import json
import re
import shutil
import time
import local_study as study


def status(**values):
    study.save(study.HERE/'baseline_extension_status.json', dict(updated=time.time(), **values))
    print(json.dumps(values), flush=True)


study.status = status


def extend(tag):
    source = study.ROOT/f'runs_v4/{tag}/M0.30_filled_fine_opensides'
    before = study.statistics(source)
    if before['meanStable']:
        return
    case = study.HERE/f'local/{tag}/M0.30_baseline_extension'
    if (case/'result.json').exists():
        return
    if case.exists():
        raise RuntimeError(f'Incomplete extension requires inspection: {case}')
    if shutil.disk_usage(study.ROOT).free < 5*1024**3:
        raise RuntimeError('Insufficient free disk for reference extension')
    case.mkdir(parents=True)
    for sub in ['system', 'constant', '0.orig', '2000']:
        shutil.copytree(source/sub, case/sub, ignore=shutil.ignore_patterns('polyMesh'))
    (case/'constant/polyMesh').symlink_to((source/'constant/polyMesh').resolve(), target_is_directory=True)
    study.configure_procs(case)
    study.save(case/'source_audit.json', dict(source=str(source), restart=2000,
        mesh=str((source/'constant/polyMesh').resolve()), before=before,
        invariant='Original mesh, geometry, physics and numerics; continuation in an isolated copy'))
    study.run(case, 'decomposePar -latestTime -force', 'decomposePar')
    for end in [3000, 4000, 5000]:
        p = case/'system/flowSettings'
        value, count = re.subn(r'^endTime\s+[^;]+;', f'endTime {end};', p.read_text(), flags=re.M)
        assert count == 1
        p.write_text(value)
        study.run(case, f'mpirun -np {study.NPROC} rhoSimpleFoam -parallel', f'rhoSimpleFoam_{end}')
        stats = study.statistics(case)
        study.save(case/'statistics.json', stats)
        if stats['meanStable']:
            break
    study.run(case, 'reconstructPar -latestTime', 'reconstructPar')
    for p in case.glob('processor[0-9]*'):
        shutil.rmtree(p)
    study.save(case/'result.json', dict(source=str(source), before=before, extended=stats,
        status='READY_FOR_REVIEW' if stats['meanStable'] else 'ITERATIVE_UNCERTAINTY_REQUIRES_REVIEW'))


if __name__ == '__main__':
    try:
        status(state='WAITING_FOR_REFINED_QUEUE')
        deadline = time.monotonic()+36*3600
        while time.monotonic() < deadline:
            current = json.loads((study.HERE/'local_status.json').read_text())
            if current['state'] == 'NEEDS_REVIEW':
                raise RuntimeError('Refinement queue needs review; no additional job started')
            if current['state'] == 'FIRST_STAGE_COMPLETE':
                break
            time.sleep(300)
        else:
            raise RuntimeError('Reference extension wait expired')
        for tag in ['d03', 'd15']:
            extend(tag)
        status(state='BASELINE_EXTENSIONS_COMPLETE')
    except Exception as error:
        status(state='NEEDS_REVIEW', error=str(error))
        raise
