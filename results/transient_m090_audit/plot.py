from pathlib import Path
import os,sys,csv,json
os.environ['MPLCONFIGDIR']='/private/tmp/cfd-audit-mplconfig'
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=Path(__file__).resolve().parent;s=json.load(open(p/'summary.json'));r=list(csv.DictReader(open(p/'moment_plot.csv')))
t=np.array([float(x['Time (s)'])*1000 for x in r]);m=-np.array([float(x['TOTAL_MOMENT_Z']) for x in r])
plt.rcParams.update({'font.size':11,'axes.spines.top':False,'axes.spines.right':False})
fig,axes=plt.subplots(1,2,figsize=(11.8,4.5),gridspec_kw={'width_ratios':[1.3,1]},layout='constrained')
for ax in axes:
 ax.plot(t,m,color='#22649a',lw=1.5,label='SimScale T4 transient')
 ax.axhline(.8123937488,color='#207548',lw=1.4,label='Local transient mean: 0.8124')
 ax.axhline(.8238094234,color='#bc6423',ls='--',lw=1.3,label='Local steady mean: 0.8238')
 ax.grid(alpha=.18);ax.set_xlabel('SimScale physical time (ms)')
axes[0].axvspan(0,7,color='#8b94a1',alpha=.12);axes[0].text(3.5,.41,'Inlet ramp',ha='center',color='#555555',fontsize=10,rotation=90)
axes[0].set_xlim(0,30);axes[0].set_ylim(-.015,.885);axes[0].set_ylabel('Roll moment = -total Mz (N m)');axes[0].set_title('Startup and subsequent response',loc='left')
axes[0].legend(loc='lower right',fontsize=9,framealpha=.95)
axes[1].set_xlim(15,30);axes[1].set_ylim(.58,.85);axes[1].axvspan(25,30,color='#22649a',alpha=.06);axes[1].hlines(.6244914027,25,30,color='#22649a',lw=1.4,ls=':')
axes[1].text(23,.679,'Final 5 ms mean: 0.6245 N m\n23.1% below local transient',ha='center',fontsize=10,color='#184f7d');axes[1].set_title('Later response remains around 0.62',loc='left')
fig.suptitle('Mach 0.9, 10° roll control: fine-mesh comparison',fontsize=15)
fig.savefig(p/'roll_comparison.png',dpi=180)
