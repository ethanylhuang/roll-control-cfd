'use client';
import { useState } from 'react';
import { CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis } from 'recharts';
import { ArrowDownToLine, Info } from 'lucide-react';
import { Table, TableHeader, TableHead, TableBody, TableRow, TableCell } from '@/components/ui/table';
import { Panel } from '@/components/sweep-charts';
import { colors, fmt, tick } from '@/lib/sweep';
import heuristic from '@/analysis/heuristic.json';

const est = { strip: '#b45309', vlm: '#16a34a', linear: '#8b5cf6' };
const g = heuristic.geometry;
const mm = (v: number) => fmt(v * 1000, 1);
const ratio = (v: number | null | undefined) => v == null ? '—' : `${fmt(v, 2)}×`;

function Legend({ items }: { items: [string, string, boolean?][] }) {
  return <div className="legend">{items.map(([label, color, dashed]) => <span key={label}><i className={dashed ? 'dashed' : ''} style={dashed ? { borderColor: color } : { background: color }} />{label}</span>)}</div>;
}

export function Heuristics() {
  const machs = heuristic.perMach.map(r => r.mach);
  const [mach, setMach] = useState(.6);
  const slopes = heuristic.perMach.map(r => ({ ...r, stripRatio: r.strip && r.cfdSlope ? r.strip / r.cfdSlope : null, vlmRatio: r.vlm && r.cfdSlope ? r.vlm / r.cfdSlope : null, linearRatio: r.linear && r.cfdSlope ? r.linear / r.cfdSlope : null }));
  const rows = heuristic.rows.filter(r => r.mach === mach);
  const active = heuristic.perMach.find(r => r.mach === mach)!;
  const line = [-6, 15].map(a => ({ angle: a, strip: active.strip == null ? undefined : active.strip * a, vlm: active.vlm == null ? undefined : active.vlm * a, linear: active.linear == null ? undefined : active.linear * a, calibrated: active.vlm == null ? undefined : heuristic.etaSubsonic * active.vlm * a }));
  return <>
    <div className="notice context-note"><Info size={18} /><span><strong>Hand methods vs CFD.</strong> Three textbook estimates of tab roll moment, built from the sealed-tab CAD the sweep meshed (Onshape CFD workspace, 11 Sep export), against OpenFOAM and SimScale. All are inviscid and linear in δ; the gap to CFD is mostly viscous loss on the 10 mm-thick tab and its 1 mm hinge gap.</span></div>
    <div className="summary-strip">
      <div><span>Tab</span><strong>{mm(g.tabSpan)} × {mm(g.tabChord)} <small>mm</small></strong><p>Span × chord · arm {mm(g.tabArm)} mm from the axis</p></div>
      <div><span>Flap fraction</span><strong>E = {fmt(g.chordFraction, 2)} <small>τ = {fmt(g.tau, 2)}</small></strong><p>Of the {mm(g.localChord)} mm local fin chord</p></div>
      <div><span>Subsonic calibration</span><strong>η = {fmt(heuristic.etaSubsonic, 2)}</strong><p>CFD / vortex lattice, mean of M0.30–0.60</p></div>
      <div><span>M1.2 calibration</span><strong>η = {fmt(heuristic.etaSupersonic, 2)}</strong><p>CFD 15° transient / Ackeret</p></div>
    </div>
    <div className="filters"><div className="filter-mach"><span className="control-label">Mach</span><fieldset className="mach-buttons" aria-label="Mach number">{machs.map(m => <button key={m} aria-pressed={mach === m} onClick={() => setMach(m)} className={mach === m ? 'selected' : ''}>{m.toFixed(2)}</button>)}</fieldset></div></div>
    <div className="two-grid">
      <Panel title="Roll control derivative across Mach" subtitle="dMroll/dδ · N·m per degree · CFD = OLS slope −6°…15° (M1.2: 15° point ÷ 15)">
        <div className="axis-caption">dMroll/dδ <span>(N·m/°)</span></div>
        <div className="chart"><ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 600, height: 300 }}><ComposedChart data={slopes} margin={{ top: 14, right: 24, bottom: 24, left: 4 }}>
          <CartesianGrid vertical={false} stroke="#ededed" /><XAxis type="number" dataKey="mach" domain={[.25, 1.25]} ticks={machs} tickFormatter={v => v.toFixed(2)} axisLine={false} tickLine={false} label={{ value: 'Mach', position: 'bottom', offset: 6 }} />
          <YAxis tickFormatter={tick} width={62} axisLine={false} tickLine={false} /><Tooltip formatter={v => fmt(Number(v), 4)} labelFormatter={l => `M${Number(l).toFixed(2)}`} />
          <Line dataKey="cfdSlope" name="OpenFOAM" stroke={colors.OpenFOAM} strokeWidth={2} dot={{ r: 3.5 }} isAnimationActive={false} />
          <Line dataKey="cfdSlopeSimScale" name="SimScale" stroke={colors.SimScale} strokeWidth={2} dot={{ r: 3.5 }} isAnimationActive={false} />
          <Line dataKey="strip" name="Strip theory" stroke={est.strip} strokeDasharray="5 4" strokeWidth={1.6} dot={{ r: 3 }} isAnimationActive={false} />
          <Line dataKey="vlm" name="Vortex lattice" stroke={est.vlm} strokeDasharray="5 4" strokeWidth={1.6} dot={{ r: 3 }} isAnimationActive={false} />
          <Scatter dataKey="linear" name="Ackeret" fill={est.linear} isAnimationActive={false} />
        </ComposedChart></ResponsiveContainer></div>
        <Legend items={[['OpenFOAM', colors.OpenFOAM], ['SimScale', colors.SimScale], ['Strip theory', est.strip, true], ['Vortex lattice', est.vlm, true], ['Ackeret (M1.2)', est.linear]]} />
      </Panel>
      <Panel title="Estimate ÷ CFD" subtitle="Ratio of the estimated derivative to the OpenFOAM derivative · 1.0 = exact">
        <div className="axis-caption">Ratio <span>(–)</span></div>
        <div className="chart"><ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 600, height: 300 }}><ComposedChart data={slopes} margin={{ top: 14, right: 24, bottom: 24, left: 4 }}>
          <CartesianGrid vertical={false} stroke="#ededed" /><XAxis type="number" dataKey="mach" domain={[.25, 1.25]} ticks={machs} tickFormatter={v => v.toFixed(2)} axisLine={false} tickLine={false} label={{ value: 'Mach', position: 'bottom', offset: 6 }} />
          <YAxis domain={[.5, 1.8]} ticks={[.6, .8, 1, 1.2, 1.4, 1.6]} width={44} axisLine={false} tickLine={false} /><Tooltip formatter={v => `${fmt(Number(v), 3)}×`} labelFormatter={l => `M${Number(l).toFixed(2)}`} /><ReferenceLine y={1} stroke="#737373" />
          <Line dataKey="stripRatio" name="Strip theory" stroke={est.strip} strokeWidth={2} dot={{ r: 3.5 }} isAnimationActive={false} />
          <Line dataKey="vlmRatio" name="Vortex lattice" stroke={est.vlm} strokeWidth={2} dot={{ r: 3.5 }} isAnimationActive={false} />
          <Scatter dataKey="linearRatio" name="Ackeret" fill={est.linear} isAnimationActive={false} />
        </ComposedChart></ResponsiveContainer></div>
        <Legend items={[['Strip theory', est.strip], ['Vortex lattice', est.vlm], ['Ackeret (M1.2)', est.linear]]} />
        <p className="fineprint">Strip theory runs 7–26 % high and the vortex lattice 11–19 % high; both close in toward M0.90, where CFD tab authority rises faster than Prandtl–Glauert predicts. At M1.2 linear theory is 57 % high: a 15° wedge at M1.2 has a detached bow shock, far outside small-disturbance theory.</p>
      </Panel>
    </div>
    <Panel title={`Roll moment vs deflection · M${mach.toFixed(2)}`} subtitle="CFD means (points) vs linear estimates (lines) · calibrated = η × vortex lattice">
      <div className="axis-caption">Mroll <span>(N·m)</span></div>
      <div className="chart"><ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 900, height: 300 }}><ComposedChart margin={{ top: 14, right: 24, bottom: 24, left: 4 }}>
        <CartesianGrid vertical={false} stroke="#ededed" /><XAxis type="number" dataKey="angle" domain={[-6, 15]} ticks={[-6, 0, 3, 6, 9, 12, 15]} axisLine={false} tickLine={false} label={{ value: 'Deflection δ (°)', position: 'bottom', offset: 6 }} allowDuplicatedCategory={false} />
        <YAxis tickFormatter={tick} width={62} axisLine={false} tickLine={false} /><Tooltip formatter={v => fmt(Number(v), 4)} labelFormatter={l => `${l}°`} /><ReferenceLine y={0} stroke="#d4d4d4" />
        <Line data={line} dataKey="strip" name="Strip theory" stroke={est.strip} strokeDasharray="5 4" dot={false} isAnimationActive={false} />
        <Line data={line} dataKey="vlm" name="Vortex lattice" stroke={est.vlm} strokeDasharray="5 4" dot={false} isAnimationActive={false} />
        <Line data={line} dataKey="calibrated" name="Calibrated VLM" stroke={est.vlm} strokeWidth={2} dot={false} isAnimationActive={false} />
        <Line data={line} dataKey="linear" name="Ackeret" stroke={est.linear} strokeDasharray="5 4" dot={false} isAnimationActive={false} />
        <Scatter data={rows} dataKey="openfoam" name="OpenFOAM" fill={colors.OpenFOAM} isAnimationActive={false} />
        <Scatter data={rows} dataKey="simscale" name="SimScale" fill={colors.SimScale} isAnimationActive={false} />
      </ComposedChart></ResponsiveContainer></div>
      <Legend items={mach > 1 ? [['OpenFOAM', colors.OpenFOAM], ['Ackeret', est.linear, true]] : [['OpenFOAM', colors.OpenFOAM], ['SimScale', colors.SimScale], ['Strip theory', est.strip, true], ['Vortex lattice', est.vlm, true], [`Calibrated VLM (η = ${fmt(heuristic.etaSubsonic, 2)})`, est.vlm]]} />
      <p className="fineprint">CFD is close to linear over −6°…15° below M0.90, so the linear estimates track its shape. At low Mach the CFD −6° moment is 2–3 % larger in magnitude than +6°, a small asymmetry no linear method shows.</p>
    </Panel>
    <section className="panel"><div className="panel-head"><div><h2>Control derivative by Mach</h2><p>N·m per degree · ratio = estimate ÷ OpenFOAM</p></div><div className="panel-actions"><a className="export-link" href="/data/heuristic.csv" download><ArrowDownToLine size={15} />Point table CSV</a></div></div>
      <div className="source-table"><Table><TableHeader><TableRow>{['Mach', 'q · kPa', 'OpenFOAM', 'SimScale', 'Strip', 'Strip ratio', 'VLM', 'VLM ratio', 'Ackeret', 'Ackeret ratio', 'Calibrated'].map(h => <TableHead key={h}>{h}</TableHead>)}</TableRow></TableHeader>
        <TableBody>{slopes.map(r => <TableRow key={r.mach} onClick={() => setMach(r.mach)} className="source-row"><TableCell>{r.mach.toFixed(2)}</TableCell><TableCell>{fmt(r.q / 1000, 1)}</TableCell><TableCell>{fmt(r.cfdSlope, 4)}</TableCell><TableCell>{fmt(r.cfdSlopeSimScale, 4)}</TableCell><TableCell>{fmt(r.strip, 4)}</TableCell><TableCell>{ratio(r.stripRatio)}</TableCell><TableCell>{fmt(r.vlm, 4)}</TableCell><TableCell>{ratio(r.vlmRatio)}</TableCell><TableCell>{fmt(r.linear, 4)}</TableCell><TableCell>{ratio(r.linearRatio)}</TableCell><TableCell>{fmt(r.vlm != null ? heuristic.etaSubsonic * r.vlm : r.linear != null ? heuristic.etaSupersonic * r.linear : null, 4)}</TableCell></TableRow>)}</TableBody></Table></div>
      <div className="panel-foot">Calibrated = η × VLM subsonic (η = {fmt(heuristic.etaSubsonic, 3)}), η × Ackeret at M1.2 (η = {fmt(heuristic.etaSupersonic, 3)}, matches its own point by construction). Click a row to plot that Mach.</div>
    </section>
    <section className="panel"><div className="panel-head"><div><h2>Point by point · M{mach.toFixed(2)}</h2><p>Mroll · N·m · ratio = estimate ÷ OpenFOAM (blank near 0°)</p></div></div>
      <div className="source-table"><Table><TableHeader><TableRow>{['δ', 'OpenFOAM', 'SimScale', 'Strip', 'Strip ratio', 'VLM', 'VLM ratio', 'Ackeret', 'Ackeret ratio'].map(h => <TableHead key={h}>{h}</TableHead>)}</TableRow></TableHeader>
        <TableBody>{rows.map(r => <TableRow key={r.angle}><TableCell>{r.angle}°{r.openfoamMethod === 'transient' ? ' · transient' : ''}</TableCell><TableCell>{fmt(r.openfoam, 4)}</TableCell><TableCell>{fmt(r.simscale, 4)}</TableCell><TableCell>{fmt(r.strip, 4)}</TableCell><TableCell>{ratio(r.stripRatio)}</TableCell><TableCell>{fmt(r.vlm, 4)}</TableCell><TableCell>{ratio(r.vlmRatio)}</TableCell><TableCell>{fmt(r.linear, 4)}</TableCell><TableCell>{ratio(r.linearRatio)}</TableCell></TableRow>)}</TableBody></Table></div>
    </section>
    <div className="method-grid">
      <section className="panel method"><div className="eyebrow">01 / GEOMETRY</div><h2>From the CFD-workspace CAD</h2><div className="math-block">fin: r {mm(g.rootRadius)}–{mm(g.tipRadius)} mm · span {mm(g.span)} mm<br />chord {mm(g.rootChord)} root → {mm(g.tipChord)} tip · LE sweep {fmt(g.leSweepDeg, 1)}°<br />thickness {mm(g.finThickness)} mm · A = 2s²/S = {fmt(g.aspect, 2)}<br />tab: r {mm(g.tabArm - g.tabSpan / 2)}–{mm(g.tabArm + g.tabSpan / 2)} mm · chord {mm(g.tabChord)} mm<br />S_tab = {fmt(g.tabArea * 1e6, 0)} mm² · local chord {mm(g.localChord)} mm</div><p>Measured by slicing the Part Studio STL export (Onshape {g.onshape}) that the sealed sweep meshed. The trailing edge is unswept at z = 25 mm; the tab hinge is at z = 52.5 mm.</p></section>
      <section className="panel method"><div className="eyebrow">02 / STRIP THEORY</div><h2>Fin lift slope × flap effectiveness</h2><div className="math-block">CNα = 2πA / (2 + √(4 + (βA / cos Γc)²))<br />θf = arccos(2E − 1), τ = 1 − (θf − sin θf)/π<br />ΔF = q · CNα · τ · δ · (b_tab · c_local)<br />Mroll = ΔF · r_tab</div><p>Barrowman/Diederich whole-fin slope (A = {fmt(g.aspect, 2)}) applied to the fin strip behind the tab, thin-airfoil τ = {fmt(g.tau, 3)} for E = {fmt(g.chordFraction, 3)}. No body carry-over: lift carried onto the round body has no roll arm.</p></section>
      <section className="panel method"><div className="eyebrow">03 / VORTEX LATTICE</div><h2>One fin, body as a wall</h2><div className="math-block">x′ = x / β (Göthert), same δ<br />Σ AIC · Γ = −V δ on tab panels<br />ΔF_i = ρ V Γ_i Δy_i<br />Mroll = Σ ΔF_i (r_root + y_i)</div><p>{g.panels} horseshoe panels with spanwise breaks at the tab edges and a chordwise break at the hinge, mirrored across the root plane. Converged to 0.3 % across three panel densities; the whole-fin lift slope matches Diederich within 2 %. Captures the spanwise spill of the narrow tab’s load onto the fixed fin, which strip theory ignores.</p></section>
      <section className="panel method"><div className="eyebrow">04 / SUPERSONIC</div><h2>Ackeret, and where it fails</h2><div className="math-block">Cp = ±2δ / √(M² − 1) on each tab face<br />Mroll = q · 4δ/β · S_tab · r_tab</div><p>In linear theory the tab’s side-edge pressure deficit spills onto the neighbouring fixed fin at the same arm, so the total is the 2-D value. At 15° and M1.2 the compression face is far past the ~4° shock-detachment angle, so this is an upper bound; the CFD comes in at η = {fmt(heuristic.etaSupersonic, 2)} of it.</p>
        <Table><TableHeader><TableRow>{['Mach', 'Ackeret · N·m/°', `× η = ${fmt(heuristic.etaSupersonic, 2)}`].map(h => <TableHead key={h}>{h}</TableHead>)}</TableRow></TableHeader><TableBody>{heuristic.extrapolation.map(r => <TableRow key={r.mach}><TableCell>{r.mach.toFixed(2)}</TableCell><TableCell>{fmt(r.linear, 4)}</TableCell><TableCell>{fmt(r.calibrated, 4)}</TableCell></TableRow>)}</TableBody></Table>
        <p className="fineprint">Extrapolation at the sweep’s sea-level density (ρ = 1.189 kg/m³). Real flight is at altitude: scale by ρ/1.189. Using one 15° point’s η at smaller δ or higher Mach is untested.</p></section>
    </div>
  </>;
}
