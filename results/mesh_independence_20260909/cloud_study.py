"""One bounded cloud solve after an already-submitted refined mesh succeeds."""
import copy
import csv
import io
import json
import sys
import time
from pathlib import Path
import numpy as np

sys.path.insert(0, '/Users/trasomi/.claude/skills/cfd-sweep/scripts')
from simscale_api import SimScale, check_entries

HERE = Path(__file__).resolve().parent
PID = '1269879333705405039'
API = SimScale()


def save(path, data):
    temp = path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(data, indent=2, allow_nan=False)+'\n')
    temp.replace(path)


def get(path):
    return API.request('GET', path, retries=2, timeout=30)


def post(path, body=None):
    return API.request('POST', path, body=body, retries=0, timeout=45)


def collect(sid, rid, folder):
    folder.mkdir(exist_ok=True, parents=True)
    items = API.run_results(PID, sid, rid)
    arrays = {}
    for category in ['MOMENT_PLOT', 'FORCE_PLOT', 'RESIDUALS_PLOT']:
        candidates = [i for i in items if i.get('category') == category]
        if len(candidates) != 1:
            raise RuntimeError(f'Expected one {category}, found {len(candidates)}; review monitor selection')
        raw = API.download(candidates[0]['download']['url']).decode('utf-8', 'replace').replace('\x00', '')
        (folder/f'{category}.csv').write_text(raw)
        rows = list(csv.reader(io.StringIO(raw)))
        headers = [h.strip() for h in rows[0]]
        values = []
        for row in rows[1:]:
            if len(row) != len(headers):
                continue
            try:
                values.append([float(v) for v in row])
            except ValueError:
                continue
        arrays[category] = (headers, np.asarray(values))
    mh, m = arrays['MOMENT_PLOT']; fh, f = arrays['FORCE_PLOT']
    assert len(m) >= 1000 and len(f) >= 1000
    m = m[-1000:]; f = f[-1000:]
    assert np.allclose(m[:, 0], f[:, 0]) and np.isfinite(m).all() and np.isfinite(f).all()
    series = {'roll': -m[:, mh.index('TOTAL_MOMENT_Z')],
              'yaw': m[:, mh.index('TOTAL_MOMENT_X')]-.069*f[:, fh.index('TOTAL_FORCE_Y')],
              'axial': -f[:, fh.index('TOTAL_FORCE_Z')],
              'side': f[:, fh.index('TOTAL_FORCE_Y')],
              'normal': f[:, fh.index('TOTAL_FORCE_X')]}
    metrics = {}
    for name, a in series.items():
        mean = float(a.mean()); den = max(abs(mean), 1e-12); blocks = a.reshape(4, 250).mean(axis=1)
        metrics[name] = dict(mean=mean, rawStd=float(a.std()), blockMeans=blocks.tolist(),
                             blockStdPct=float(100*blocks.std()/den),
                             driftPct=float(100*abs(blocks[-1]-blocks[0])/den))
    stable = all(metrics[k]['blockStdPct'] <= .5 and metrics[k]['driftPct'] <= .5 for k in ['roll', 'yaw', 'axial'])
    return dict(metrics=metrics, window=m[[0,-1],0].tolist(), samples=1000, meanStable=stable)


def main(tag):
    folder = HERE/f'cloud/{tag}'; folder.mkdir(parents=True, exist_ok=True)
    def state(**kw):
        save(folder/'status.json', dict(updated=time.time(), **kw)); print(json.dumps(kw), flush=True)
    try:
        # A named reservation is mandatory. This worker never expands its cap or retries a run.
        budget = json.loads((HERE/'budget.json').read_text())
        assert any(i.get('kind') == 'solver' and i.get('tag') == tag and i['maxCPUh'] == 40 for i in budget['items'])
        baseline = json.loads((HERE/f'ss_{tag}_base_simulation.json').read_text())
        prepared = json.loads((HERE/f'ss_{tag}_refined_mesh.json').read_text())
        sid = json.loads((HERE/f'ss_{tag}_copy.json').read_text())['simulationId']
        opid = prepared['meshOperationId']
        if (folder/'run.json').exists():
            raise RuntimeError('Existing run found: inspect it before resuming; no duplicate submitted')
        deadline = time.monotonic()+3*3600
        while time.monotonic() < deadline:
            op = get(f'/projects/{PID}/meshoperations/{opid}'); save(folder/'mesh_status.json', op)
            if op['status'] == 'FINISHED':
                break
            if op['status'] in ['FAILED', 'CANCELED']:
                raise RuntimeError('Mesh failed; solver not started')
            state(stage='WAITING_FOR_MESH', meshStatus=op['status'])
            time.sleep(300)
        else:
            raise RuntimeError('Mesh wait expired; solver not started')
        assert op['model'] == prepared['model'] and op['geometryId'] == baseline['geometryId']
        events = get(f'/projects/{PID}/meshoperations/{opid}/eventlog'); save(folder/'mesh_eventlog.json', events)
        if 'MSG_GOOD_MESH_QUALITY' not in json.dumps(events):
            raise RuntimeError('Mesh quality needs manual review before solving')
        mesh = get(f'/projects/{PID}/meshes/{op["meshId"]}'); save(folder/'mesh.json', mesh)
        current = API.simulation(PID, sid)
        current['model'] = copy.deepcopy(baseline['model'])
        current['meshId'] = op['meshId']
        control = current['model']['simulationControl']
        control['numProcessors'] = 32
        control['maxRunTime'] = {'value':4500, 'unit':'s'}
        # Preserve the baseline's 3000-iteration target and every physics/numerics field.
        assert control['endTime']['value'] == 3000
        API.update_simulation(PID, current)
        saved = API.simulation(PID, sid)
        assert saved['model'] == current['model'] and saved['meshId'] == op['meshId']
        save(folder/'saved_spec.json', saved)
        check = post(f'/projects/{PID}/simulations/{sid}/check'); save(folder/'check.json', check)
        errors, warnings = check_entries(check)
        if errors or warnings:
            raise RuntimeError('Simulation check needs review; solver not started')
        run = post(f'/projects/{PID}/simulations/{sid}/runs', {'name':f'MI {tag} refined same physics 32 cores'})
        save(folder/'run.json', run)
        rid = run['runId']
        snapshot = API.run_spec(PID, sid, rid); save(folder/'run_spec.json', snapshot)
        assert snapshot['model'] == saved['model'] and snapshot['meshId'] == op['meshId']
        post(f'/projects/{PID}/simulations/{sid}/runs/{rid}/start')
        state(stage='SOLVING', runId=rid)
        deadline = time.monotonic()+4*3600
        while time.monotonic() < deadline:
            run = API.run(PID, sid, rid); save(folder/'run_status.json', run)
            if run['status'] in ['FINISHED', 'FAILED', 'CANCELED']:
                break
            time.sleep(300)
        else:
            raise RuntimeError('Run monitoring wait expired; check existing run, do not submit another')
        if run['status'] != 'FINISHED':
            raise RuntimeError(f'Run ended {run["status"]}; inspect partial results')
        stats = collect(sid, rid, folder/'raw')
        save(folder/'statistics.json', stats)
        state(stage='READY_FOR_REVIEW', meanStable=stats['meanStable'], runId=rid,
              cpuHours=(run.get('computeResource') or {}).get('value'))
    except Exception as error:
        state(stage='NEEDS_REVIEW', error=str(error))
        raise


if __name__ == '__main__':
    main(sys.argv[1])
