'use client';
import { useState } from 'react';
import Link from 'next/link';
import { ArrowDownToLine, ArrowUpRight, Info, SlidersHorizontal } from 'lucide-react';
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select';
import { Table, TableHeader, TableHead, TableBody, TableRow, TableCell } from '@/components/ui/table';
import { Panel, ResponseChart, FamilyChart, SlopeChart, ParityChart } from '@/components/sweep-charts';
import { DataMethod } from '@/components/data-method';
import { MeshStudy } from '@/components/mesh-study';
import { PreviousSweep } from '@/components/previous-sweep';
import { HighMach } from '@/components/high-mach';
import { colors, fitRange, fmt, metrics, raw, shortDate, signed, solvers, stats, type Fit, type Metric, type Solver } from '@/lib/sweep';

function FitCard({ solver, fit, metric }: { solver: Solver; fit?: Fit; metric: Metric }) {
  return <div className="fit-card"><div className="fit-label"><i style={{ background: colors[solver] }} />{solver}<span>OLS</span></div>{fit ? <>
    <div className="equation">{metrics[metric].symbol} = <b>{fmt(fit.slope, 6)}</b>δ {signed(fit.intercept, 6)}</div>
    <p className="fineprint">{solver === 'OpenFOAM' ? 'Fine mesh grid-checked (roll within 1.5 %)' : 'Fine mesh · SimScale grid check partial'}</p>
    <div className="fit-values"><div><span>Slope / degree</span><strong>{fmt(fit.slope, 6)}</strong></div><div><span>Slope / radian</span><strong>{fmt(fit.slopePerRad, 6)}</strong></div><div><span>R²</span><strong>{fmt(fit.r2, 5)}</strong></div><div><span>Points</span><strong>{fit.n}</strong></div></div>
    <p className="fineprint">RMSE {fmt(fit.rmse, 6)} · slope SE {fmt(fit.slopeSE, 6)} /deg</p>
    {fit.r2 != null && fit.r2 < .95 && <p className="weak-fit">Weak linear model · R² below 0.95</p>}
  </> : <p className="no-fit">{solver === 'SimScale' ? 'No eligible SimScale fit.' : 'Fewer than three eligible points.'}</p>}</div>;
}

export default function Dashboard() {
  const [tab, setTab] = useState('Overview');
  const [mach, setMach] = useState(.6);
  const [metric, setMetric] = useState<Metric>('roll');
  const [range, setRange] = useState(0);
  const [quality, setQuality] = useState(false);
  const [familySolver, setFamilySolver] = useState<Solver>('OpenFOAM');
  const getFit = (s: Solver, m: number, k: Metric) => raw.fits.find(f => f.solver === s && f.mach === m && f.metric === k && f.minAngle === fitRange[range].lo && f.maxAngle === fitRange[range].hi && f.excludeFlagged === quality);
  const of = getFit('OpenFOAM', mach, metric), ss = getFit('SimScale', mach, metric);
  const slopeDelta = of && ss && Math.abs(of.slope) > 1e-12 ? 100*(ss.slope - of.slope)/Math.abs(of.slope) : null;
  const pairs = raw.pairs.filter(p => p.metric === metric);
  const activePairs = pairs.filter(p => p.mach === mach);
  const matched = of?.angles.filter(a => ss?.angles.includes(a)) ?? [];
  return <div className="app-shell">
    <header className="topbar"><Link className="brand" href="/" aria-label="CFD sweep dashboard"><span className="brand-mark" />CFD<span className="slash">/</span><span className="project-name">Roll control</span></Link><div className="topbar-right"><span className="snapshot"><i />Sealed tab · updated {shortDate(raw.reviewed)}</span><a href="/data/normalized.csv" download className="export-link"><ArrowDownToLine size={15} />Export data</a></div></header>
    <div className="nav-wrap"><nav aria-label="Dashboard sections">{['Overview', 'Solver comparison', 'Sealed vs previous', 'Transonic & M1.2', 'Mesh study', 'Data & method'].map(t => <button key={t} onClick={() => setTab(t)} aria-current={tab === t ? 'page' : undefined} className={tab === t ? 'active' : ''}>{t}</button>)}</nav><span className="nav-context">v5 sealed-tab sweep · 11–14 Sep 2026</span></div>
    <main>
      <div className="page-heading"><div><div className="eyebrow">AERODYNAMIC ANALYSIS</div><h1>Deflection sweep</h1><p>Control authority and yaw coupling, across two solvers.</p></div><span className="status-label">Steady RANS · transient M0.90 rows</span></div>
      <div className="notice"><Info size={18}/><span><strong>Sealed tab CAD: grid check passed locally.</strong> Refining the OpenFOAM mesh changes roll by ≤1.5 % at 3°/M0.30, 10°/M0.60 and 15°/M0.85. SimScale passes at 15°/M0.85 but not at 3°/M0.30 (−45 %, unexplained). M0.90 and M1.2 are not grid-checked. <button className="source-button" onClick={() => setTab('Mesh study')}>View mesh evidence</button></span></div>
      {tab === 'Mesh study' && <MeshStudy/>}
      {tab === 'Transonic & M1.2' && <HighMach/>}
      {tab !== 'Mesh study' && tab !== 'Transonic & M1.2' && <><div className="summary-strip"><div><span>OpenFOAM</span><strong>{stats.of} <small>fine-mesh points</small></strong><p>M0.30–0.90 · 8 deflections · + M1.2 at 15°</p></div><div><span>SimScale</span><strong>{stats.ss} <small>fine-mesh points</small></strong><p>M0.30–0.85 · 8 deflections</p></div><div><span>Matched conditions</span><strong>{stats.pairs} <small>pairs</small></strong><p>Same Mach and deflection</p></div><div><span>Roll-slope difference</span><strong>{signed(stats.slopeLo, 1)}% <small>to</small> {signed(stats.slopeHi, 1)}%</strong><p>SimScale vs OpenFOAM · full-range fit</p></div></div>
      <div className="filters"><div className="filter-mach"><span className="control-label">Mach</span><fieldset className="mach-buttons" aria-label="Mach number">{raw.machs.map(m => <button key={m} aria-pressed={mach === m} onClick={() => setMach(m)} className={mach === m ? 'selected' : ''}>{m.toFixed(2)}{m === .9 && <sup>*</sup>}</button>)}</fieldset></div><label><span className="control-label">Quantity</span><NativeSelect aria-label="Quantity" value={metric} onChange={e => setMetric(e.target.value as Metric)}>{Object.entries(metrics).map(([k,v]) => <NativeSelectOption key={k} value={k}>{v.label} · {v.symbol}</NativeSelectOption>)}</NativeSelect></label><label><span className="control-label">Fit interval</span><NativeSelect aria-label="Fit interval" value={range} onChange={e => setRange(+e.target.value)}>{fitRange.map((r,i) => <NativeSelectOption key={i} value={i}>{r.name}</NativeSelectOption>)}</NativeSelect></label></div>
      {mach === .9 && <div className="notice"><Info size={17} /><span><strong>OpenFOAM only at M0.90.</strong> SimScale's sealed sweep stops at M0.85. The 15° and −6° points are transient restarts (their steady means drifted); the others are steady. See Transonic & M1.2.</span></div>}
      </>}
      {tab === 'Overview' && <>
        <div className="hero-grid"><Panel title={`${metrics[metric].label} vs deflection`} subtitle={`Mach ${mach.toFixed(2)} · reported means and linear fits`}><ResponseChart metric={metric} mach={mach} getFit={getFit} withFits /><div className="panel-foot">Solid lines join sampled means. Dashed lines are fits over the selected interval.</div></Panel>
          <aside className="fit-panel"><div className="fit-heading"><SlidersHorizontal size={16} /><h2>Linear response</h2><span>y = aδ + b</span></div>{solvers.map(s => <FitCard key={s} solver={s} fit={getFit(s, mach, metric)} metric={metric} />)}<div className="slope-delta"><span>Difference in fitted slope</span><strong>{slopeDelta == null ? 'Unavailable' : `${signed(slopeDelta)}%`}</strong></div><p className="fineprint fit-note">{matched.length ? `${matched.length} shared angles: ${matched.map(a => `${a}°`).join(', ')}.` : mach === .9 ? 'OpenFOAM-only fits use its available angles.' : 'Too few shared eligible points for a paired fit.'} Free intercept; equal weight per condition. Units: {metrics[metric].unit === '–' ? 'coefficient' : metrics[metric].unit} per degree.</p></aside>
        </div>
        <div className="analysis-controls"><label><input type="checkbox" checked={quality} onChange={e => setQuality(e.target.checked)} />Omit source-flagged conditions from fits</label><span>Removes a flagged angle from both solvers. Plot points remain visible.</span></div>
        <div className="two-grid"><Panel title="Roll coefficient" subtitle="Cl · normalized control authority"><ResponseChart metric="cl" mach={mach} getFit={getFit} /><div className="formula-foot">Cl = Mroll / (½ρV² Sref Dref)</div></Panel><Panel title="Yaw coefficient" subtitle="Cn · signed yaw coupling / adverse-yaw assessment"><ResponseChart metric="cn" mach={mach} getFit={getFit} /><div className="formula-foot">Cn = Myaw / (½ρV² Sref Dref)</div></Panel></div>
        <Panel title="Response across Mach" subtitle={`${metrics[metric].label} · source means, including flagged points`} action={<NativeSelect aria-label="Solver for Mach overlay" value={familySolver} onChange={e => setFamilySolver(e.target.value as Solver)}>{solvers.map(s => <NativeSelectOption key={s}>{s}</NativeSelectOption>)}</NativeSelect>}><FamilyChart metric={metric} solver={familySolver}/></Panel>
      </>}
      {tab === 'Solver comparison' && <>
        <div className="analysis-controls comparison-controls"><label><input type="checkbox" checked={quality} onChange={e => setQuality(e.target.checked)}/>Omit source-flagged pairs from fits and parity plot</label><span>Heatmap retains all {stats.pairs} paired means.</span></div>
        <div className="two-grid"><Panel title="Control derivative across Mach" subtitle={`${metrics[metric].symbol} slope · ${metrics[metric].unit === '–' ? 'coefficient' : metrics[metric].unit} / degree`}><SlopeChart metric={metric} getFit={getFit}/><div className="panel-foot">M0.90 has OpenFOAM only and a different angle set. Other fits use shared angles.</div></Panel>
        <Panel title="Solver parity" subtitle={`${metrics[metric].symbol} · all matched Machs`}><ParityChart metric={metric} quality={quality}/><div className="panel-foot">Agreement between solvers does not establish accuracy against reality.</div></Panel></div>
        <section className="panel"><div className="panel-head"><div><h2>Where the solvers differ</h2><p>{metrics[metric].symbol} · Δ% = 100 (SimScale / OpenFOAM − 1) · positive = SimScale larger in magnitude</p></div><span className="muted heat-key">Lower <i/> Higher</span></div><div className="heatmap-scroll"><table className="heatmap"><thead><tr><th>Deflection</th>{raw.machs.map(m => <th key={m}>M{m.toFixed(2)}</th>)}</tr></thead><tbody>{[-6,0,3,6,9,10,12,15].map(a => <tr key={a}><th>{a}°</th>{raw.machs.map(m => { const p=pairs.find(p=>p.mach===m&&p.angle===a); const v=p?.percent; return <td key={m}><button disabled={!p} title={p ? `Δ ${fmt(p.delta,6)} ${metrics[metric].unit}${p.flagged?' · Source flagged':''}`:'No matching SimScale result'} onClick={()=>{setMach(m);setTab('Overview');}} style={{background:v == null ? '#fafafa' : `rgba(${v<0?'37,99,235':'217,119,6'},${Math.min(.5,.045+Math.abs(v)/80)})`}}>{v == null?'—':`${signed(v,1)}%`}{p?.flagged&&<sup>†</sup>}</button></td>; })}</tr>)}</tbody></table></div><div className="panel-foot">† At least one source is flagged. Relative differences are hidden below 1% of the maximum OpenFOAM magnitude at that Mach. Click a cell to inspect its Mach.</div></section>
        <section className="panel"><div className="panel-head"><div><h2>Paired values at M{mach.toFixed(2)}</h2><p>{metrics[metric].label} · {metrics[metric].unit}</p></div></div><Table><TableHeader><TableRow>{['Deflection','OpenFOAM','SimScale','Δ absolute','Δ relative'].map(h=><TableHead key={h}>{h}</TableHead>)}</TableRow></TableHeader><TableBody>{activePairs.map(p=><TableRow key={p.angle}><TableCell>{p.angle}°{p.flagged?' †':''}</TableCell><TableCell>{fmt(p.openfoam,6)}</TableCell><TableCell>{fmt(p.simscale,6)}</TableCell><TableCell>{signed(p.delta,6)}</TableCell><TableCell>{p.percent==null?'—':`${signed(p.percent)}%`}</TableCell></TableRow>)}</TableBody></Table>{!activePairs.length&&<p className="empty">No matching SimScale sweep data at this Mach.</p>}</section>
      </>}
      {tab === 'Sealed vs previous' && <PreviousSweep mach={mach} metric={metric}/>}
      {tab === 'Data & method' && <DataMethod mach={mach}/>}
      <footer><span>{stats.of + stats.ss} fine-mesh conditions · {stats.pairs} direct comparisons · moments at z = 0.330 m</span><button onClick={()=>{setTab('Data & method');window.scrollTo({top:0,behavior:'smooth'});}}>Method & provenance <ArrowUpRight size={14}/></button></footer>
    </main>
  </div>;
}
