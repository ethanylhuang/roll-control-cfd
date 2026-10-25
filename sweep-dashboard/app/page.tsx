'use client';
import { useState } from 'react';
import Link from 'next/link';
import { ArrowDownToLine, Info, SlidersHorizontal } from 'lucide-react';
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select';
import { Panel, ResponseChart, FamilyChart, SlopeChart, EstSwatch } from '@/components/sweep-charts';
import { colors, estimate, estimatedMethods, estMethods, fitRange, fmt, heuristic, metrics, raw, shortDate, signed, solvers, stats, type Fit, type Metric, type Solver } from '@/lib/sweep';

function FitCard({ solver, fit, metric }: { solver: Solver; fit?: Fit; metric: Metric }) {
  return <div className="fit-card"><div className="fit-label"><i style={{ background: colors[solver] }} />{solver}<span>OLS</span></div>{fit ? <>
    <div className="equation">{metrics[metric].symbol} = <b>{fmt(fit.slope, 6)}</b>δ {signed(fit.intercept, 6)}</div>
    <p className="fineprint">{solver === 'OpenFOAM' ? 'Fine mesh grid-checked (roll within 1.5 %)' : 'Fine mesh · SimScale grid check partial'}</p>
    <div className="fit-values"><div><span>Slope / degree</span><strong>{fmt(fit.slope, 6)}</strong></div><div><span>Slope / radian</span><strong>{fmt(fit.slopePerRad, 6)}</strong></div><div><span>R²</span><strong>{fmt(fit.r2, 5)}</strong></div><div><span>Points</span><strong>{fit.n}</strong></div></div>
    <p className="fineprint">RMSE {fmt(fit.rmse, 6)} · slope SE {fmt(fit.slopeSE, 6)} /deg</p>
    {fit.r2 != null && fit.r2 < .95 && <p className="weak-fit">Weak linear model · R² below 0.95</p>}
  </> : <p className="no-fit">{solver === 'SimScale' ? 'No eligible SimScale fit.' : 'Fewer than three eligible points.'}</p>}</div>;
}

function EstimateCard({ metric, mach, fit }: { metric: Metric; mach: number; fit?: Fit }) {
  const ests = estimatedMethods(metric, mach);
  if (!ests.length) return <div className="fit-card"><div className="fit-label">Hand estimates</div><p className="no-fit">No estimate for {metrics[metric].label.toLowerCase()}: only roll, side force and yaw are estimated.</p></div>;
  return <div className="fit-card"><div className="fit-label">Hand estimates<span>per degree</span></div>
    <div className="fit-values">{ests.map(e => { const v = estimate(e, metric, mach)!; return <div key={e}><span>{estMethods[e].label}</span><strong>{fmt(v, 6)}</strong><small className="fineprint" style={{ display: 'block' }}>{fit && Math.abs(fit.slope) > 1e-9 ? `${fmt(v / fit.slope, 2)}× OpenFOAM` : ''}</small></div>; })}</div>
    <p className="fineprint">Inviscid, linear in δ, geometry from the CFD-workspace CAD. {metric === 'side' || metric === 'cy' || metric === 'yaw' || metric === 'cn' ? 'Fin load only: lift the tab induces on the body is not estimated, so CFD should be higher.' : `Calibrated = ${fmt(heuristic.etaSubsonic, 3)} × vortex lattice (CFD / VLM, mean of M0.30–0.60).`}</p></div>;
}

export default function Dashboard() {
  const [mach, setMach] = useState(.6);
  const [metric, setMetric] = useState<Metric>('roll');
  const [range, setRange] = useState(0);
  const [quality, setQuality] = useState(false);
  const [familySolver, setFamilySolver] = useState<Solver>('OpenFOAM');
  const getFit = (s: Solver, m: number, k: Metric) => raw.fits.find(f => f.solver === s && f.mach === m && f.metric === k && f.minAngle === fitRange[range].lo && f.maxAngle === fitRange[range].hi && f.excludeFlagged === quality);
  const of = getFit('OpenFOAM', mach, metric), ss = getFit('SimScale', mach, metric);
  const slopeDelta = of && ss && Math.abs(of.slope) > 1e-12 ? 100*(ss.slope - of.slope)/Math.abs(of.slope) : null;
  const matched = of?.angles.filter(a => ss?.angles.includes(a)) ?? [];
  const g = heuristic.geometry;
  return <div className="app-shell">
    <header className="topbar"><Link className="brand" href="/" aria-label="CFD sweep dashboard"><span className="brand-mark" />CFD<span className="slash">/</span><span className="project-name">Roll control</span></Link><div className="topbar-right"><span className="snapshot"><i />Sealed tab · updated {shortDate(raw.reviewed)}</span><a href="/data/normalized.csv" download className="export-link"><ArrowDownToLine size={15} />Export data</a></div></header>
    <div className="nav-wrap"><nav aria-label="Dashboard sections"><button aria-current="page" className="active">Overview</button></nav><span className="nav-context">v5 sealed-tab sweep · 11–14 Sep 2026</span></div>
    <main>
      <div className="page-heading"><div><div className="eyebrow">AERODYNAMIC ANALYSIS</div><h1>Deflection sweep</h1><p>Control authority and yaw coupling, across two solvers and hand estimates.</p></div><span className="status-label">Steady RANS · transient M0.90 rows</span></div>
      <div className="notice"><Info size={18}/><span><strong>Sealed tab CAD: grid check passed locally.</strong> Refining the OpenFOAM mesh changes roll by ≤1.5 % at 3°/M0.30, 10°/M0.60 and 15°/M0.85. SimScale passes at 15°/M0.85 but not at 3°/M0.30 (−45 %, unexplained). M0.90 is not grid-checked.</span></div>
      <>
        <div className="summary-strip"><div><span>OpenFOAM</span><strong>{stats.of} <small>fine-mesh points</small></strong><p>M0.30–0.90 · 8 deflections</p></div><div><span>SimScale</span><strong>{stats.ss} <small>fine-mesh points</small></strong><p>M0.30–0.85 · 8 deflections</p></div><div><span>Roll-slope difference</span><strong>{signed(stats.slopeLo, 1)}% <small>to</small> {signed(stats.slopeHi, 1)}%</strong><p>SimScale vs OpenFOAM · full-range fit</p></div><div><span>Hand estimate calibration</span><strong>η = {fmt(heuristic.etaSubsonic, 2)}</strong><p>CFD roll / vortex lattice · M0.30–0.60</p></div></div>
        <div className="filters"><div className="filter-mach"><span className="control-label">Mach</span><fieldset className="mach-buttons" aria-label="Mach number">{raw.machs.map(m => <button key={m} aria-pressed={mach === m} onClick={() => setMach(m)} className={mach === m ? 'selected' : ''}>{m.toFixed(2)}{m === .9 && <sup>*</sup>}</button>)}</fieldset></div><label><span className="control-label">Quantity</span><NativeSelect aria-label="Quantity" value={metric} onChange={e => setMetric(e.target.value as Metric)}>{Object.entries(metrics).map(([k,v]) => <NativeSelectOption key={k} value={k}>{v.label} · {v.symbol}</NativeSelectOption>)}</NativeSelect></label><label><span className="control-label">Fit interval</span><NativeSelect aria-label="Fit interval" value={range} onChange={e => setRange(+e.target.value)}>{fitRange.map((r,i) => <NativeSelectOption key={i} value={i}>{r.name}</NativeSelectOption>)}</NativeSelect></label></div>
        {mach === .9 && <div className="notice"><Info size={17} /><span><strong>OpenFOAM only at M0.90.</strong> SimScale’s sealed sweep stops at M0.85. The 15° and −6° points are transient restarts (their steady means drifted); the others are steady.</span></div>}
        <div className="hero-grid"><Panel title={`${metrics[metric].label} vs deflection`} subtitle={`Mach ${mach.toFixed(2)} · CFD means, linear fits and hand estimates`}><ResponseChart metric={metric} mach={mach} getFit={getFit} withFits /><div className="panel-foot">Solid black/blue lines join CFD means; faint dashed lines are fits over the selected interval; coloured lines are hand estimates.</div></Panel>
          <aside className="fit-panel"><div className="fit-heading"><SlidersHorizontal size={16} /><h2>Linear response</h2><span>y = aδ + b</span></div>{solvers.map(s => <FitCard key={s} solver={s} fit={getFit(s, mach, metric)} metric={metric} />)}<div className="slope-delta"><span>Difference in fitted slope</span><strong>{slopeDelta == null ? 'Unavailable' : `${signed(slopeDelta)}%`}</strong></div><EstimateCard metric={metric} mach={mach} fit={of} /><p className="fineprint fit-note">{matched.length ? `${matched.length} shared angles: ${matched.map(a => `${a}°`).join(', ')}.` : mach === .9 ? 'OpenFOAM-only fits use its available angles.' : 'Too few shared eligible points for a paired fit.'} Free intercept; equal weight per condition. Units: {metrics[metric].unit === '–' ? 'coefficient' : metrics[metric].unit} per degree.</p></aside>
        </div>
        <div className="analysis-controls"><label><input type="checkbox" checked={quality} onChange={e => setQuality(e.target.checked)} />Omit source-flagged conditions from fits</label><span>Removes a flagged angle from both solvers. Plot points remain visible.</span></div>
        <div className="two-grid"><Panel title="Roll coefficient" subtitle="Cl · normalized control authority"><ResponseChart metric="cl" mach={mach} getFit={getFit} /><div className="formula-foot">Cl = Mroll / (½ρV² Sref Dref)</div></Panel><Panel title="Yaw coefficient" subtitle="Cn · signed yaw coupling / adverse-yaw assessment"><ResponseChart metric="cn" mach={mach} getFit={getFit} /><div className="formula-foot">Cn = Myaw / (½ρV² Sref Dref)</div></Panel></div>
        <div className="two-grid"><Panel title="Control derivative across Mach" subtitle={`${metrics[metric].symbol} slope · ${metrics[metric].unit === '–' ? 'coefficient' : metrics[metric].unit} / degree · CFD fits vs hand estimates`}><SlopeChart metric={metric} getFit={getFit}/><div className="panel-foot">M0.90 has OpenFOAM only.</div></Panel>
          <Panel title="Response across Mach" subtitle={`${metrics[metric].label} · source means (solid) and hand estimate (dashed, same colour)`} action={<NativeSelect aria-label="Solver for Mach overlay" value={familySolver} onChange={e => setFamilySolver(e.target.value as Solver)}>{solvers.map(s => <NativeSelectOption key={s}>{s}</NativeSelectOption>)}</NativeSelect>}><FamilyChart metric={metric} solver={familySolver}/></Panel></div>
        <section className="panel method"><div className="panel-head"><div><h2>Hand estimates</h2><p>Tab {fmt(g.tabSpan * 1000, 1)} × {fmt(g.tabChord * 1000, 1)} mm at {fmt(g.tabArm * 1000, 1)} mm from the axis · fin A = {fmt(g.aspect, 2)} · E = {fmt(g.chordFraction, 2)}, τ = {fmt(g.tau, 2)} · CAD: Onshape CFD workspace, 11 Sep export</p></div></div>
          <div className="legend" style={{ justifyContent: 'flex-start', padding: '0 24px 8px' }}>{(['strip', 'vlm', 'calibrated'] as const).map(e => <EstSwatch key={e} method={e} />)}</div>
          <div className="math-block" style={{ margin: '0 24px 18px' }}>Strip: Mroll = q · CNα(fin) · τ · δ · b_tab c_local · r_tab, CNα = 2πA / (2 + √(4 + (βA / cos Γc)²))<br />Vortex lattice: one fin, body as a wall, Prandtl–Glauert (Göthert), {g.panels} panels; gives roll, side force and yaw about z = 0.330 m<br />Calibrated: {fmt(heuristic.etaSubsonic, 3)} × vortex lattice</div></section>
      </>
      <footer><span>{stats.of + stats.ss} fine-mesh conditions · moments at z = 0.330 m · hand estimates from scripts/heuristics.py</span></footer>
    </main>
  </div>;
}
