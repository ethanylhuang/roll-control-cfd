from pathlib import Path
import csv,json,re,gzip,zipfile
import numpy as np
out=Path(__file__).resolve().parent
root=out.parents[1]
z=zipfile.ZipFile('/private/tmp/claude-501/-Users-trasomi-dev-cfd/e77796e5-73f1-4b54-ac10-df1a9b566759/scratchpad/sol_T4/solution.zip')
def stats(a):
 return dict(n=len(a),mean=float(np.mean(a)),std=float(np.std(a)),min=float(np.min(a)),max=float(np.max(a)))
def read_csv(n):
 rows=[r for r in csv.DictReader(open(out/n)) if None not in r.values() and None not in r];return {k:np.array([float(r[k]) for r in rows]) for k in rows[0]}
m=read_csv('moment_plot.csv');f=read_csv('force_plot.csv');r=read_csv('residuals_plot.csv');t=m['Time (s)'];roll=-m['TOTAL_MOMENT_Z']
summary={'simscale_windows':[]}
for lo,hi in [(0.015,0.020),(0.020,0.025),(0.025,0.030),(0.029,0.030),(0.0225,0.030)]:
 w=(t>lo+1e-12)&(t<=hi+1e-12);d=dict(window_s=[lo,hi],roll=stats(roll[w]),pressure_roll=stats(-m['PRESSURE_MOMENT_Z'][w]),viscous_roll=stats(-m['VISCOUS_MOMENT_Z'][w]));d['slope_drift_pct']=float(100*np.polyfit(t[w],roll[w],1)[0]*(t[w][-1]-t[w][0])/abs(np.mean(roll[w])));summary['simscale_windows'].append(d)
print('SIMSCALE',json.dumps(summary['simscale_windows'],indent=2))
print('last',t[-1],roll[-1],'dt',stats(np.diff(t)))
rw=r['Time (s)']>0.025+1e-12;summary['simscale_residuals_last5ms']={k:stats(v[rw]) for k,v in r.items() if k!='Time (s)'};print('RESIDUALS',json.dumps(summary['simscale_residuals_last5ms'],indent=2))
summary['local_cases']={}
for name in ['M0.90_filled_fine_transient','M0.90_filled_fine_opensides','M0.90_simscale_v3mesh_local','M0.90_simscale_v3mesh_local_ssGrad','M0.90_simscale_v3mesh_local_ssBCs']:
 p=root/'runs_v4/d10'/name;data=np.loadtxt(p/'postProcessing/forces_all/0/moment.dat');tt=data[:,0]
 w=(tt>0.0075+1e-12) if name.endswith('transient') else (tt>=tt[-1]-500)
 d=dict(window=[float(tt[w][0]),float(tt[w][-1])],roll=stats(-data[w,3]),pressure_roll=stats(-data[w,6]),viscous_roll=stats(-data[w,9]));summary['local_cases'][name]=d
 print('LOCAL',name,json.dumps(d))
# Read actual exported internal fields and inlet rather than trusting setup labels.
def field(txt):
 if isinstance(txt,bytes):
  if re.search(rb'format\s+binary;',txt[:1000]):
   m=re.search(rb'internalField\s+nonuniform\s+List<scalar>\s+(\d+)\s*\(',txt);n=int(m.group(1));start=m.end();start+=int(txt[start:start+1]==b'\n');return np.frombuffer(txt[start:start+8*n],dtype='<f8').copy()
  txt=txt.decode()
 m=re.search(r'internalField\s+nonuniform\s+List<\w+>\s+(\d+)\s*\(',txt)
 if not m:
  m=re.search(r'internalField\s+uniform\s+([^;]+);',txt);return np.array([float(m.group(1))])
 end=txt.index('\n)',m.end());raw=txt[m.end():end];a=np.fromstring(raw.replace('(','').replace(')',''),sep=' ')
 return a
last=max((n.split('/')[0] for n in z.namelist() if re.match(r'^\d.*?/p.gz$',n)),key=float)
summary['simscale_fields']={}
for name in ['p','T','blendedIndicatorU']:
 txt=gzip.decompress(z.read(last+'/'+name+'.gz')).decode();a=field(txt);d=stats(a);d['percentiles']=np.percentile(a,[0,1,50,95,99,100]).tolist();summary['simscale_fields'][name]=d;print('SS FIELD',name,d)
 if name=='blendedIndicatorU':print('BLEND value counts',[(q,int(np.count_nonzero(np.isclose(a,q)))) for q in [0,1]])
 if name=='p':(out/'actual/final_pressure_boundary.txt').write_text(txt[txt.index('boundaryField'):])
txt=gzip.decompress(z.read(last+'/U.gz')).decode();idx=txt.index('    B5_TE5_B5_TE36\n');chunk=txt[idx:];depth=0;end=0
for j,c in enumerate(chunk):
 if c=='{':depth+=1
 elif c=='}':
  depth-=1
  if depth==0:end=j+1;break
(out/'actual/final_inlet_U').write_text(chunk[:end]);print('FINAL INLET',chunk[:end])
summary['local_fields']={}
for name in ['M0.90_filled_fine_transient','M0.90_filled_fine_opensides']:
 p=root/'runs_v4/d10'/name
 paths=list(p.glob('processor*/0.01/p')) if name.endswith('transient') else [p/'3000/p']
 a=np.concatenate([field(q.read_bytes()) for q in paths]);summary['local_fields'][name]=stats(a);print('LOCAL FIELD p',name,stats(a))
log=(root/'runs_v4/d10/M0.90_filled_fine_transient/log.rhoPimpleFoam.live').read_text();co=re.findall(r'Courant Number mean:\s*(\S+) max:\s*(\S+)',log)
if co:
 co=np.array(co,dtype=float);summary['local_courant_last625']={'meanCo':stats(co[-625:,0]),'maxCo':stats(co[-625:,1])};print('LOCAL COURANT',summary['local_courant_last625'])
(out/'summary.json').write_text(json.dumps(summary,indent=2))
