'use client';
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Scatter, ComposedChart, Tooltip, XAxis, YAxis, Legend as RLegend } from 'recharts';
import { Info } from 'lucide-react';
import { Table, TableHeader, TableHead, TableBody, TableRow, TableCell } from '@/components/ui/table';
import { Panel } from '@/components/sweep-charts';
import { colors, extraPoints, fmt, points, raw, tick } from '@/lib/sweep';

export function HighMach() {
  const machs = [...raw.machs, 1.2];
  const at = (angle: number) => machs.map(m => {
    const p = points.find(x => x.solver === 'OpenFOAM' && x.angle === angle && x.mach === m);
    const s = points.find(x => x.solver === 'SimScale' && x.angle === angle && x.mach === m);
    const t = extraPoints.find(x => x.angle === angle && x.mach === m && x.method === 'transient');
    const st = extraPoints.find(x => x.angle === angle && x.mach === m && x.method === 'steady');
    return { mach: m, OpenFOAM: p?.roll ?? t?.roll, SimScale: s?.roll, steady: st?.roll };
  });
  const d15 = at(15), dm6 = at(-6);
  const rows = [...points.filter(p => p.method === 'transient'), ...extraPoints].sort((a, b) => a.angle - b.angle || a.mach - b.mach || a.method.localeCompare(b.method));
  return <>
    <div className="notice context-note"><Info size={18}/><span><strong>OpenFOAM only above M0.85.</strong> SimScale could not hold M1.2 (6 transient and 3 steady attempts, ~130 CPU h, all diverged). Nothing here is grid-checked. At M1.2 the ±0.6 m pressure-outlet sides reflect the nose shock onto the body ahead of the fins: roll (local to the tab) is usable, axial force is not.</span></div>
    <div className="two-grid">
      <Panel title="15° roll moment across Mach" subtitle="Sweep points, M0.90 transient and M1.2 transient · hollow = superseded steady mean">
        <div className="axis-caption">Mroll <span>(N·m)</span></div>
        <div className="chart"><ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 600, height: 300 }}><ComposedChart data={d15} margin={{ top: 14, right: 24, bottom: 24, left: 4 }}>
          <CartesianGrid vertical={false} stroke="#ededed" /><XAxis type="number" dataKey="mach" domain={[.25, 1.25]} ticks={machs} tickFormatter={v => v.toFixed(2)} axisLine={false} tickLine={false} label={{ value: 'Mach', position: 'bottom', offset: 6 }} />
          <YAxis tickFormatter={tick} width={62} axisLine={false} tickLine={false} /><Tooltip formatter={v => fmt(Number(v), 4)} labelFormatter={l => `M${Number(l).toFixed(2)}`} />
          <Line dataKey="OpenFOAM" stroke={colors.OpenFOAM} strokeWidth={2} connectNulls dot={{ r: 3.5 }} isAnimationActive={false} />
          <Line dataKey="SimScale" stroke={colors.SimScale} strokeWidth={2} connectNulls dot={{ r: 3.5 }} isAnimationActive={false} />
          <Scatter dataKey="steady" name="Steady (superseded)" fill="white" stroke={colors.OpenFOAM} isAnimationActive={false} />
          <RLegend verticalAlign="top" height={24} />
        </ComposedChart></ResponsiveContainer></div>
        <p className="fineprint">M0.90: transient 1.425 vs drifting steady 1.300. M1.2: transient 1.790 vs steady 1.931 (upper bound, +8 %). Roll grows ×1.26 from M0.90 to M1.2 while dynamic pressure grows ×1.78, so tab effectiveness drops supersonic.</p>
      </Panel>
      <Panel title="−6° roll moment across Mach" subtitle="Sweep points and the M0.90 transient">
        <div className="axis-caption">Mroll <span>(N·m)</span></div>
        <div className="chart"><ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 600, height: 300 }}><LineChart data={dm6.filter(r => r.mach < 1)} margin={{ top: 14, right: 24, bottom: 24, left: 4 }}>
          <CartesianGrid vertical={false} stroke="#ededed" /><XAxis type="number" dataKey="mach" domain={[.25, .95]} ticks={raw.machs} tickFormatter={v => v.toFixed(2)} axisLine={false} tickLine={false} label={{ value: 'Mach', position: 'bottom', offset: 6 }} />
          <YAxis tickFormatter={tick} width={62} axisLine={false} tickLine={false} /><Tooltip formatter={v => fmt(Number(v), 4)} labelFormatter={l => `M${Number(l).toFixed(2)}`} />
          <Line dataKey="OpenFOAM" stroke={colors.OpenFOAM} strokeWidth={2} connectNulls dot={{ r: 3.5 }} isAnimationActive={false} />
          <Line dataKey="SimScale" stroke={colors.SimScale} strokeWidth={2} connectNulls dot={{ r: 3.5 }} isAnimationActive={false} />
          <RLegend verticalAlign="top" height={24} />
        </LineChart></ResponsiveContainer></div>
        <p className="fineprint">−6° mirrors +6° within ~2 % on both solvers. The local ±6° rows sit 6–38 % above SimScale (largest at low Mach): the one unresolved solver disagreement.</p>
      </Panel>
    </div>
    <section className="panel"><div className="panel-head"><div><h2>Transient and supersonic runs</h2><p>OpenFOAM · moments at z = 0.330 m</p></div></div>
      <div className="source-table"><Table><TableHeader><TableRow>{['Case', 'Method', 'Status', 'Mroll · N·m', 'Myaw · N·m', 'Axial · N', 'Roll scatter', 'Averaging window'].map(h => <TableHead key={h}>{h}</TableHead>)}</TableRow></TableHeader><TableBody>{rows.map(p => <TableRow key={p.id}><TableCell>{p.angle}° / M{p.mach.toFixed(2)}</TableCell><TableCell>{p.method}</TableCell><TableCell>{p.role === 'primary' ? 'In sweep' : p.role === 'context' ? 'Superseded' : p.method === 'transient' ? 'Recommended' : 'Upper bound'}</TableCell><TableCell>{fmt(p.roll, 4)}</TableCell><TableCell>{fmt(p.yaw, 3)}</TableCell><TableCell>{fmt(p.axial, 1)}</TableCell><TableCell>{fmt(p.rawStdPct, 2)}%</TableCell><TableCell>{String(p.meanWindow)}</TableCell></TableRow>)}</TableBody></Table></div></section>
    <div className="two-grid">{raw.media.map(m => <section key={m.src} className="panel"><div className="panel-head"><div><h2>{m.title}</h2><p>OpenFOAM transient · 6-panel flow-field video</p></div></div><video className="flow-video" src={m.src} controls preload="metadata" playsInline /></section>)}</div>
  </>;
}
