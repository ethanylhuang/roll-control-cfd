"""One idempotent correction from the immutable baseline run, with a fixed budget."""
import copy
import json
import time
from pathlib import Path
from cloud_study import API, PID, HERE, save, collect, check_entries

FOLDER = HERE / 'cloud/d03_corrected'
CAP = 36


def main():
    FOLDER.mkdir(parents=True, exist_ok=True)
    def state(**kw):
        save(FOLDER/'status.json', dict(updated=time.time(), **kw))
        print(json.dumps(kw), flush=True)
    try:
        budget = json.loads((HERE/'budget.json').read_text())
        assert any(i.get('tag') == 'd03_corrected' and i['maxCPUh'] == CAP for i in budget['items'])
        baseline = json.loads((HERE/'cloud/d03/baseline/run_spec.json').read_text())
        sid = json.loads((HERE/'ss_d03_copy.json').read_text())['simulationId']
        mesh = json.loads((HERE/'cloud/d03/mesh_status.json').read_text())
        assert mesh['status'] == 'FINISHED'
        if not (FOLDER/'run.json').exists():
            spec = API.simulation(PID, sid)
            spec['model'] = copy.deepcopy(baseline['model'])
            spec['meshId'] = mesh['meshId']
            spec['model']['simulationControl']['numProcessors'] = 32
            spec['model']['simulationControl']['maxRunTime'] = {'value': CAP*3600/32, 'unit': 's'}
            API.update_simulation(PID, spec)
            saved = API.simulation(PID, sid)
            assert saved['model'] == spec['model'] and saved['meshId'] == mesh['meshId']
            assert saved['model']['boundaryConditions'] == baseline['model']['boundaryConditions']
            save(FOLDER/'saved_spec.json', saved)
            check = API.check_simulation(PID, sid)
            save(FOLDER/'check.json', check)
            assert not any(check_entries(check)), 'Preflight requires review'
            run = API.create_run(PID, sid, 'MI d03 M0.30 CORRECTED immutable baseline inlet')
            save(FOLDER/'run.json', run)
            snapshot = API.run_spec(PID, sid, run['runId'])
            save(FOLDER/'run_spec.json', snapshot)
            assert snapshot['model'] == saved['model'] and snapshot['meshId'] == saved['meshId']
            # Persist intent before Start: any uncertain start requires manual review, never duplication.
            save(FOLDER/'start_intent.json', {'runId': run['runId']})
            API.start_run(PID, sid, run['runId'])
        else:
            run = json.loads((FOLDER/'run.json').read_text())
        rid = run['runId']
        deadline = time.monotonic()+4*3600
        while time.monotonic() < deadline:
            current = API.run(PID, sid, rid)
            save(FOLDER/'run_status.json', current)
            state(stage=current['status'], runId=rid, progress=current.get('progress'))
            if current['status'] in ['FINISHED', 'FAILED', 'CANCELED']:
                break
            if current['status'] == 'CREATED':
                raise RuntimeError('Created run was not confirmed started; inspect before resuming')
            time.sleep(300)
        else:
            raise RuntimeError('Monitoring deadline reached; inspect existing run')
        events = API.request('GET', f'/projects/{PID}/simulations/{sid}/runs/{rid}/eventlog', retries=1, timeout=30)
        save(FOLDER/'eventlog.json', events)
        if current['status'] != 'FINISHED':
            raise RuntimeError('Corrected run ended '+current['status'])
        stats = collect(sid, rid, FOLDER/'raw')
        save(FOLDER/'statistics.json', stats)
        base = json.loads((HERE/'cloud/d03/baseline/statistics.json').read_text())
        changes = {k: 100*(stats['metrics'][k]['mean']/base['metrics'][k]['mean']-1)
                   for k in ['roll', 'yaw', 'axial', 'side']}
        save(FOLDER/'comparison.json', dict(baseline=base, refined=stats, relativeDeltaPct=changes,
             qualified=False, note='Two-grid screen; audit defeatured faces and iterative uncertainty before use'))
        state(stage='READY_FOR_REVIEW', meanStable=stats['meanStable'], relativeDeltaPct=changes,
              runId=rid, cpuHours=current['computeResource']['value'])
    except Exception as error:
        state(stage='NEEDS_REVIEW', error=str(error))
        raise


if __name__ == '__main__':
    main()
