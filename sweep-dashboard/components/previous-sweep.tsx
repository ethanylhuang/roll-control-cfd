'use client';
import { useState } from 'react';
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Info } from 'lucide-react';
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select';
import { Table, TableHeader, TableHead, TableBody, TableRow, TableCell } from '@/components/ui/table';
import { Panel } from '@/components/sweep-charts';
import { colors, fmt, metrics, raw, signed, solvers, tick, type Metric, type Solver } from '@/lib/sweep';

export function PreviousSweep({ mach, metric }: { mach: number; metric: Metric }) {
  const [solver, setSolver] = useState<Solver>('OpenFOAM');
  const meta = metrics[metric];
  const rows = raw.previous.filter(p => p.metric === metric);
  const chart = raw.angles.map(angle => {
    const row: Record<string, number | undefined> = { angle };
    solvers.forEach(s => {
      const p = rows.find(r => r.solver === s && r.mach === mach && r.angle === angle);
      row[`${s} sealed`] = p?.sealed; row[`${s} previous`] = p?.previous;
    });
    return row;
  });
  const active = rows.filter(r => r.solver === solver && r.mach === mach);
  const angles = [-6, 0, 3, 6, 9, 10, 12, 15];
  return <>
    <div className="notice context-note"><Info size={18}/><span><strong>What changed between the sweeps.</strong> The previous sweep (4 Sep CAD) had a 6 mm tab with ~1 mm spanwise end clearances that the mesh sealed only partly. The sealed CAD (11 Sep) widens the tab to 8 mm, fills the slot, and keeps only the 1 mm chordwise gap so the tab can swing. The solver settings and meshing levels are unchanged, so higher roll authority is expected.</span></div>
    <Panel title={`${meta.label}: sealed vs previous`} subtitle={`Mach ${mach.toFixed(2)} · solid = sealed tab, dashed = previous sweep`}>
      <div className="axis-caption">{meta.symbol} <span>{meta.unit === '–' ? '(dimensionless)' : `(${meta.unit})`}</span></div>
      <div className="chart hero-chart"><ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 600, height: 300 }}><LineChart data={chart} margin={{ top: 14, right: 24, bottom: 24, left: 4 }} accessibilityLayer>
        <CartesianGrid vertical={false} stroke="#ededed" /><XAxis type="number" dataKey="angle" domain={[-6, 15]} ticks={[-6, 0, 3, 6, 9, 12, 15]} tickLine={false} axisLine={{ stroke: '#e5e5e5' }} tickMargin={10} label={{ value: 'Deflection δ (°)', position: 'bottom', offset: 6 }} />
        <YAxis tickFormatter={tick} axisLine={false} tickLine={false} width={62} /><ReferenceLine y={0} stroke="#d4d4d4" />
        <Tooltip formatter={v => fmt(Number(v), 6)} labelFormatter={l => `Deflection ${l}°`} />
        {solvers.flatMap(s => [
          <Line key={`${s}s`} name={`${s} · sealed`} dataKey={`${s} sealed`} stroke={colors[s]} strokeWidth={2} connectNulls dot={{ r: 3.5, fill: colors[s] }} isAnimationActive={false} />,
          <Line key={`${s}p`} name={`${s} · previous`} dataKey={`${s} previous`} stroke={colors[s]} strokeDasharray="5 4" strokeWidth={1.5} opacity={.55} connectNulls dot={{ r: 3, fill: 'white' }} isAnimationActive={false} />])}
      </LineChart></ResponsiveContainer></div>
      <div className="legend">{solvers.map(s => <span key={s}><i style={{ background: colors[s] }} />{s} sealed</span>)}<span><i className="dashed" />Previous sweep</span></div>
      {mach === .9 && <p className="fineprint">At M0.90 the sealed 15° and −6° points are transient restarts; the previous sweep's M0.90 points are steady extensions. SimScale has no M0.90 sweep in either set.</p>}
    </Panel>
    <section className="panel"><div className="panel-head"><div><h2>Change from the previous sweep</h2><p>{meta.symbol} · Δ% = 100 (sealed / previous − 1) · positive = larger magnitude</p></div><div className="panel-actions"><NativeSelect aria-label="Solver" value={solver} onChange={e => setSolver(e.target.value as Solver)}>{solvers.map(s => <NativeSelectOption key={s}>{s}</NativeSelectOption>)}</NativeSelect></div></div>
      <div className="heatmap-scroll"><table className="heatmap"><thead><tr><th>Deflection</th>{raw.machs.map(m => <th key={m}>M{m.toFixed(2)}</th>)}</tr></thead><tbody>{angles.map(a => <tr key={a}><th>{a}°</th>{raw.machs.map(m => { const p = rows.find(r => r.solver === solver && r.mach === m && r.angle === a); const v = p?.percent; return <td key={m}><span className="heat-cell" title={p ? `sealed ${fmt(p.sealed, 6)} · previous ${fmt(p.previous, 6)} ${meta.unit}` : 'No point in one of the sweeps'} style={{ background: v == null ? '#fafafa' : `rgba(${v < 0 ? '37,99,235' : '217,119,6'},${Math.min(.5, .045 + Math.abs(v) / 80)})` }}>{v == null ? '—' : `${signed(v, 1)}%`}</span></td>; })}</tr>)}</tbody></table></div>
      <div className="panel-foot">Orange = sealed larger in magnitude. Relative changes are hidden where the previous value is below 1 % of the largest magnitude at that Mach (0° rows are near zero in both sweeps).</div></section>
    <section className="panel"><div className="panel-head"><div><h2>{solver} values at M{mach.toFixed(2)}</h2><p>{meta.label} · {meta.unit}</p></div></div><Table><TableHeader><TableRow>{['Deflection', 'Sealed', 'Previous', 'Δ absolute', 'Δ relative'].map(h => <TableHead key={h}>{h}</TableHead>)}</TableRow></TableHeader><TableBody>{active.map(p => <TableRow key={p.angle}><TableCell>{p.angle}°{p.sealedMethod === 'transient' ? ' (transient)' : ''}</TableCell><TableCell>{fmt(p.sealed, 6)}</TableCell><TableCell>{fmt(p.previous, 6)}</TableCell><TableCell>{signed(p.delta, 6)}</TableCell><TableCell>{p.percent == null ? '—' : `${signed(p.percent)}%`}</TableCell></TableRow>)}</TableBody></Table>{!active.length && <p className="empty">No {solver} points at this Mach in both sweeps.</p>}
      <div className="download-row"><a href="/data/previous-sweep.csv" download>Download sealed-vs-previous table</a><a href="/data/legacy-v4/normalized.csv" download>Download previous sweep data</a></div></section>
  </>;
}
