"""Attach mesh-study evidence without promoting unverified refined values."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STUDY = ROOT.parent/'results/mesh_independence_20260909'


def load(path):
    return json.loads(path.read_text()) if path.exists() else {}


def annotate(points):
    cases = []
    for path in sorted(STUDY.glob('local/*/*_r10over7/result.json')):
        result = load(path)
        baseline = result['baseline']
        extension = path.parent.parent/(path.parent.name.replace('_r10over7','_baseline_extension'))/'result.json'
        if extension.exists():
            baseline = load(extension)['extended']
        refined = result['refined']
        bm, rm = baseline['metrics'], refined['metrics']
        mesh = load(Path(result['mesh'])/'mesh_report.json')
        cases.append(dict(angle=result['deflection'], mach=result['mach'], solver='OpenFOAM',
            baselineRoll=bm['roll']['mean'], refinedRoll=rm['roll']['mean'],
            rollDeltaPct=100*(rm['roll']['mean']/bm['roll']['mean']-1),
            yawDeltaPct=100*(rm['yaw']['mean']/bm['yaw']['mean']-1),
            axialDeltaPct=100*(rm['axial']['mean']/bm['axial']['mean']-1),
            baselineStable=baseline['meanStable'], refinedStable=refined['meanStable'],
            rollDriftPct=rm['roll']['driftPct'], yawDriftPct=rm['yaw']['driftPct'],
            cells=mesh['cells'], tabLayerCoverage=mesh['layer_coverage']['rocket_tab'],
            window=refined['window'], qualified=False))
    for point in points:
        point.update(qualified=False, verificationStatus='UNVERIFIED',
                     verificationNote='Mesh independence is not established for this condition.',
                     revisionSource='', revisionSha256='')
        matches = [c for c in cases if (c['solver'],c['mach'],c['angle']) ==
                   (point['solver'],point['mach'],point['angle'])]
        if matches:
            point['verificationStatus'] = 'MESH_SENSITIVE'
            point['verificationNote'] = 'Refinement changes roll by %.2f%%; refined values remain diagnostic.' % matches[0]['rollDeltaPct']
        if point['solver'] == 'OpenFOAM' and point['mach'] == .3 and point['angle'] in [3,15]:
            path = STUDY/f'local/d{int(point["angle"]):02d}/M0.30_baseline_extension/result.json'
            extension = load(path)
            if extension and extension['extended']['meanStable']:
                stats = extension['extended']; m = stats['metrics']; q=point['q']
                for key in ['roll','yaw','pitch','axial','side','normal']:
                    point[key] = m[key]['mean']
                for coeff, quantity in [('cl','roll'),('cn','yaw'),('cm','pitch')]:
                    point[coeff] = point[quantity]/(q*.0026248*.05781)
                for coeff,quantity in [('ca','axial'),('cy','side'),('cNormal','normal')]:
                    point[coeff] = point[quantity]/(q*.0026248)
                point.update(rawStdPct=100*m['roll']['rawStd']/abs(m['roll']['mean']),
                    blockStdPct=m['roll']['blockStdPct'],driftPct=m['roll']['driftPct'],meanWindow=stats['samples'],
                    revisionSource=str(path),revisionSha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    note=point['note']+' Updated from the same-mesh extension: iterations 2001–3000; roll/yaw/axial mean-stability screen passed. Source flags remain archived.')
    cloud=[]
    for tag,label in [('d03','Original 3° cloud attempt'),('d15','15° / M0.85'),('d03_corrected','Corrected 3° / M0.30'),('d15_energy_diagnostic','15° energy-relaxation startup test')]:
        folder=STUDY/'cloud'/tag; status=load(folder/'status.json'); run=load(folder/'run_status.json')
        cloud.append(dict(label=label,status=status.get('stage','NOT_STARTED'),runId=run.get('runId',''),
            progress=run.get('progress'),error=status.get('error',''),
            excluded=tag=='d03',cpuHours=(run.get('computeResource') or {}).get('value')))
    report=dict(updated=datetime.now(timezone.utc).isoformat(),qualifiedPoints=0,
        conclusion='Original sweep fails the mesh-sensitivity screen. No replacement mesh is qualified yet.',
        cases=cases,cloud=cloud,thirdGrid=load(STUDY/'third_grid_status.json'),
        thirdGridResult=load(STUDY/'local/d15/M0.30_r40/result.json'),
        surfaceAudit=load(STUDY/'surface_audit/summary.json'),
        policy='Historical fits describe provisional CFD means. No global scale factor, invented replacement values, GCI, or physical-accuracy bound is applied.')
    (ROOT/'public/data/legacy-v4/mesh-study.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    revisions=[dict(id=p['id'],source=p['revisionSource'],sha256=p['revisionSha256'],originalSource=p['source'],originalSha256=p['sha256']) for p in points if p['revisionSource']]
    (ROOT/'public/data/legacy-v4/revision-manifest.json').write_text(json.dumps(revisions,indent=2)+'\n')
    return report
