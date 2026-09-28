'use client';
import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Table, TableHeader, TableHead, TableBody, TableRow, TableCell } from '@/components/ui/table';
import { colors, fmt, raw, signed } from '@/lib/sweep';

export function MeshStudy() {
  const report = raw.grid;
  const data = report.cases.map(c => ({ ...c, condition: `${c.solver === 'OpenFOAM' ? 'OF' : 'SS'} · ${c.angle}° / M${c.mach.toFixed(2)}` }));
  return <>
    <section className="panel method"><div className="panel-head"><div><h2>Grid check · sealed tab</h2><p>Same geometry, snappy levels and solver settings · background grid refined ~1.4× per direction (~2× cells)</p></div></div>
      <p><strong>{report.conclusion}</strong></p>
      <div style={{ height: 260, width: '100%' }}><ResponsiveContainer><BarChart data={data} margin={{ top: 12, right: 20, bottom: 12, left: 12 }}><CartesianGrid vertical={false} stroke="#ededed"/><XAxis dataKey="condition" tick={{ fontSize: 12 }}/><YAxis unit="%" tick={{ fontSize: 13 }} domain={[-50, 5]}/><Tooltip formatter={v => [`${Number(v).toFixed(2)}%`, 'Roll change']}/><ReferenceLine y={0} stroke="#737373"/><ReferenceLine y={-2} stroke="#16a34a" strokeDasharray="4 4"/><ReferenceLine y={2} stroke="#16a34a" strokeDasharray="4 4"/><Bar dataKey="rollDeltaPct" maxBarSize={70}>{data.map(c => <Cell key={c.condition} fill={c.pass ? colors[c.solver as 'OpenFOAM' | 'SimScale'] : '#dc2626'} />)}</Bar></BarChart></ResponsiveContainer></div>
      <p className="fineprint">Green lines: ±2 % pass band. Red bar: fails the band. {report.policy}</p>
      <div className="source-table"><Table><TableHeader><TableRow>{['Solver', 'Condition', 'Grid', 'Cells', 'Fine roll · N·m', 'Refined roll · N·m', 'Roll', 'Yaw', 'Axial', 'Side', 'Verdict'].map(h => <TableHead key={h}>{h}</TableHead>)}</TableRow></TableHeader><TableBody>{report.cases.map(c => <TableRow key={`${c.solver}-${c.angle}-${c.mach}`}><TableCell>{c.solver}</TableCell><TableCell>{c.angle}° / M{c.mach.toFixed(2)}</TableCell><TableCell>{c.grid}</TableCell><TableCell>{(c.baselineCells / 1e6).toFixed(2)} M → {(c.refinedCells / 1e6).toFixed(2)} M</TableCell><TableCell>{fmt(c.baselineRoll, 5)}</TableCell><TableCell>{fmt(c.refinedRoll, 5)}</TableCell><TableCell>{signed(c.rollDeltaPct)}%</TableCell><TableCell>{signed(c.yawDeltaPct, 1)}%</TableCell><TableCell>{signed(c.axialDeltaPct, 1)}%</TableCell><TableCell>{signed(c.sideDeltaPct, 1)}%</TableCell><TableCell>{c.pass ? 'Pass' : 'Fail'}</TableCell></TableRow>)}</TableBody></Table></div>
    </section>
    <div className="two-grid"><section className="panel method"><h2>Notes</h2>{report.notes.map(n => <p key={n}>{n}</p>)}</section>
      <section className="panel method"><h2>What this supersedes</h2><p>The 9–10 Sep study on the previous CAD failed (roll −28 to −37 % on refinement). That drop came from the finer mesh re-opening the tab's ~1 mm end clearances, which the sweep mesh had partly sealed. It was a geometry change, not discretization error.</p><p>The sealed CAD fills those clearances in the model itself, so refinement now only tests the discretization. The old study's evidence is archived with the previous sweep.</p><div className="download-row"><a href="/data/mesh-study.json" download>Download grid-check evidence</a><a href="/data/legacy-v4/mesh-study.json" download>Previous study (archived)</a></div></section></div>
  </>;
}
