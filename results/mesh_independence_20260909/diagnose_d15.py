"""Bounded startup diagnostic; not a production sweep result."""
import copy
import json
import time
from cloud_study import API,PID,HERE,save,check_entries

FOLDER=HERE/'cloud/d15_energy_diagnostic'


def main():
    FOLDER.mkdir(parents=True,exist_ok=True)
    def state(**kw):
        save(FOLDER/'status.json',dict(updated=time.time(),**kw));print(json.dumps(kw),flush=True)
    try:
        assert any(i.get('tag')=='d15_energy_diagnostic' and i['maxCPUh']==8 for i in json.loads((HERE/'budget.json').read_text())['items'])
        assert not (FOLDER/'run.json').exists(), 'Existing diagnostic; do not duplicate'
        base=json.loads((HERE/'cloud/d15/baseline/run_spec.json').read_text())
        sid=json.loads((HERE/'ss_d15_copy.json').read_text())['simulationId']
        spec=API.simulation(PID,sid);spec['model']=copy.deepcopy(base['model'])
        spec['meshId']=json.loads((HERE/'cloud/d15/mesh_status.json').read_text())['meshId']
        spec['model']['numerics']['relaxationFactor']['enthalpyEquation']=.2
        spec['model']['simulationControl'].update(numProcessors=32,maxRunTime={'value':900,'unit':'s'},endTime={'value':100,'unit':'s'})
        spec['model']['simulationControl']['writeControl']={'type':'TIME_STEP','writeInterval':100}
        API.update_simulation(PID,spec);saved=API.simulation(PID,sid)
        assert saved['model']==spec['model'] and saved['meshId']==spec['meshId']
        assert saved['model']['boundaryConditions']==base['model']['boundaryConditions']
        save(FOLDER/'saved_spec.json',saved)
        check=API.check_simulation(PID,sid);save(FOLDER/'check.json',check);assert not any(check_entries(check))
        run=API.create_run(PID,sid,'MI d15 startup diagnostic h relaxation 0.2 — 100 iterations')
        save(FOLDER/'run.json',run);rid=run['runId'];snap=API.run_spec(PID,sid,rid);save(FOLDER/'run_spec.json',snap)
        assert snap['model']==saved['model'] and snap['meshId']==saved['meshId']
        API.start_run(PID,sid,rid)
        deadline=time.monotonic()+3*3600
        while time.monotonic()<deadline:
            run=API.run(PID,sid,rid);save(FOLDER/'run_status.json',run);state(stage=run['status'],runId=rid,qualified=False)
            if run['status'] in ['FINISHED','FAILED','CANCELED']:break
            time.sleep(300)
        else:raise RuntimeError('Monitor deadline reached; inspect existing run')
        save(FOLDER/'eventlog.json',API.request('GET',f'/projects/{PID}/simulations/{sid}/runs/{rid}/eventlog',retries=1,timeout=30))
        state(stage='READY_FOR_REVIEW',outcome=run['status'],runId=rid,qualified=False,note='Startup test only; does not establish convergence at M0.85')
    except Exception as error:
        state(stage='NEEDS_REVIEW',error=str(error));raise


if __name__=='__main__':main()
