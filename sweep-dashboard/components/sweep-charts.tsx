'use client';
import type { ReactNode } from 'react';
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from 'recharts';
import { ArrowDownToLine } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { colors, fmt, metrics, palette, points, raw, signed, solvers, tick, type GetFit, type Metric, type Solver } from '@/lib/sweep';

function ExportChart({ title }: { title: string }) {
  return <Button variant="ghost" size="icon" aria-label={`Download ${title} as SVG`} title="Download chart as SVG" onClick={e => {
    const panel = e.currentTarget.closest('.panel');
    const svg = panel?.querySelector('svg.recharts-surface');
    if (!svg) return;
    const clone = svg.cloneNode(true) as SVGElement;
    clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
    clone.setAttribute('style', 'font-family:Arial,sans-serif;font-size:14px;background:white');
    const name = document.createElementNS('http://www.w3.org/2000/svg', 'title'); name.textContent = title; clone.insertBefore(name, clone.firstChild);
    const width = svg.getBoundingClientRect().width, height = svg.getBoundingClientRect().height;
    const outer = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    outer.setAttribute('xmlns', 'http://www.w3.org/2000/svg'); outer.setAttribute('width', String(width)); outer.setAttribute('height', String(height+130));
    outer.setAttribute('viewBox', `0 0 ${width} ${height+130}`); outer.setAttribute('style', 'background:white;font-family:Arial,sans-serif;font-size:12px');
    const addText = (text: string, x: number, y: number, color = '#525252', size = '12') => {
      const t = document.createElementNS('http://www.w3.org/2000/svg','text'); t.setAttribute('x',String(x)); t.setAttribute('y',String(y)); t.setAttribute('fill',color); t.setAttribute('font-size',size); t.textContent=text; outer.appendChild(t);
    };
    addText(title,24,25,'#171717','16');
    addText(panel?.querySelector('.panel-head p')?.textContent ?? '',24,45);
    addText(panel?.querySelector('.axis-caption')?.textContent ?? '',24,64);
    clone.setAttribute('y','72'); outer.appendChild(clone);
    let legendX=24;
    panel?.querySelectorAll('.legend span').forEach(item=>{
      const swatch=item.querySelector('i'); const color=swatch ? getComputedStyle(swatch).backgroundColor : '#737373';
      const label=item.textContent??''; addText(label,legendX,height+99,color==='rgba(0, 0, 0, 0)'?'#737373':color); legendX+=label.length*7+24;
    });
    addText('Sealed-tab CFD sweep · 11–14 Sep 2026 · means include source flags · moments at z = 0.330 m',24,height+120,'#737373','10');
    const url = URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(outer)], { type: 'image/svg+xml' }));
    const link = document.createElement('a'); link.href = url; link.download = `${title.toLowerCase().replace(/[^a-z0-9]+/g, '-')}.svg`; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }}><ArrowDownToLine size={16} /></Button>;
}
export function Panel({ title, subtitle, children, action, className = '' }: { title: string; subtitle?: string; children: ReactNode; action?: ReactNode; className?: string }) {
  return <section className={`panel ${className}`}><div className="panel-head"><div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div><div className="panel-actions">{action}<ExportChart title={title} /></div></div>{children}</section>;
}
export function Legend({ fits = false, flags = true }: { fits?: boolean; flags?: boolean }) {
  return <div className="legend">{solvers.map(s => <span key={s}><i style={{ background: colors[s] }} />{s}</span>)}{fits && <span><i className="dashed" />Linear fit</span>}{flags && <span className="muted"><b className="hollow" />Source flagged</span>}</div>;
}
function ChartTip({ active, payload, label, xLabel = 'Deflection', xUnit = '°' }: { active?: boolean; payload?: readonly { color?: string; name?: string | number; value?: unknown }[]; label?: string | number; xLabel?: string; xUnit?: string }) {
  if (!active || !payload?.length) return null;
  return <div className="chart-tip"><strong>{xLabel} {label}{xUnit}</strong>{payload.map((p, i) => <div key={i}><span style={{ color: p.color }}>{p.name}</span><b>{typeof p.value === 'number' ? fmt(p.value, 6) : String(p.value)}</b></div>)}</div>;
}
export function ResponseChart({ metric, mach, getFit, withFits = false }: { metric: Metric; mach: number; getFit: GetFit; withFits?: boolean }) {
  const meta = metrics[metric];
  const rows = raw.angles.map(angle => {
    const row: Record<string, number | boolean | undefined> = { angle };
    solvers.forEach(s => {
      const point = points.find(p => p.solver === s && p.mach === mach && p.angle === angle);
      row[s] = point?.[metric]; row[`${s}Flag`] = !!point?.flags.length;
      const fit = getFit(s, mach, metric);
      if (fit && angle >= Math.min(...fit.angles) && angle <= Math.max(...fit.angles)) row[`${s}Fit`] = fit.slope * angle + fit.intercept;
    }); return row;
  });
  return <><div className="axis-caption">{meta.symbol} <span>{meta.unit === '–' ? '(dimensionless)' : `(${meta.unit})`}</span></div><div className={`chart ${withFits ? 'hero-chart' : ''}`}><ResponsiveContainer width="100%" height="100%" initialDimension={{width:600,height:300}}><LineChart data={rows} margin={{ top: 14, right: 24, bottom: 24, left: 4 }} accessibilityLayer>
    <CartesianGrid vertical={false} stroke="#ededed" /><XAxis type="number" dataKey="angle" domain={[-6, 15]} ticks={[-6, 0, 3, 6, 9, 12, 15]} tickLine={false} axisLine={{ stroke: '#e5e5e5' }} tickMargin={10} label={{ value: 'Deflection δ (°)', position: 'bottom', offset: 6 }} />
    <YAxis tickFormatter={tick} axisLine={false} tickLine={false} width={62} domain={['auto', 'auto']} /><Tooltip content={<ChartTip />} /><ReferenceLine y={0} stroke="#d4d4d4" />
    {solvers.map(s => <Line key={s} name={s} dataKey={s} stroke={colors[s]} strokeWidth={2} connectNulls isAnimationActive={false} dot={(props: { cx?: number; cy?: number; payload?: Record<string, unknown>; index?: number }) => typeof props.payload?.[s] !== 'number' ? <g key={`${s}-${props.index}`} /> : <circle key={`${s}-${props.index}`} cx={props.cx} cy={props.cy} r={3.5} fill={props.payload?.[`${s}Flag`] ? 'white' : colors[s]} stroke={colors[s]} strokeWidth={1.7} />} activeDot={{ r: 6 }} />)}
    {withFits && solvers.map(s => <Line key={`${s}fit`} name={`${s} fit`} dataKey={`${s}Fit`} stroke={colors[s]} strokeDasharray="5 5" strokeWidth={1.3} opacity={.5} connectNulls dot={false} isAnimationActive={false} />)}
  </LineChart></ResponsiveContainer></div><Legend fits={withFits} /></>;
}
export function FamilyChart({ metric, solver }: { metric: Metric; solver: Solver }) {
  const family = raw.angles.map(angle => Object.fromEntries([['angle', angle], ...raw.machs.map(m => [`M${m}`, points.find(p => p.solver === solver && p.angle === angle && p.mach === m)?.[metric]])]));
  return <><div className="axis-caption">{metrics[metric].symbol} ({metrics[metric].unit})</div><div className="chart family-chart"><ResponsiveContainer width="100%" height="100%" initialDimension={{width:600,height:300}}><LineChart data={family} margin={{ top: 10, right: 28, left: 4, bottom: 24 }} accessibilityLayer><CartesianGrid vertical={false} stroke="#ededed"/><XAxis type="number" dataKey="angle" domain={[-6,15]} ticks={[-6,0,3,6,9,12,15]} axisLine={false} tickLine={false} label={{ value: 'Deflection δ (°)', position:'bottom', offset:6 }}/><YAxis tickFormatter={tick} width={62} axisLine={false} tickLine={false}/><ReferenceLine y={0} stroke="#d4d4d4"/><Tooltip content={<ChartTip/>}/>{raw.machs.filter(m => solver === 'OpenFOAM' || m < .9).map((m,i) => <Line key={m} dataKey={`M${m}`} name={`M${m.toFixed(2)}`} stroke={palette[i]} strokeWidth={2} connectNulls dot={{ r:3 }} isAnimationActive={false}/>)}</LineChart></ResponsiveContainer></div><div className="legend">{raw.machs.filter(m => solver === 'OpenFOAM' || m < .9).map((m,i) => <span key={m}><i style={{ background:palette[i] }}/>M{m.toFixed(2)}</span>)}</div></>;
}
export function SlopeChart({ metric, getFit }: { metric: Metric; getFit: GetFit }) {
  const rows = raw.machs.map(m => ({ mach: m, OpenFOAM: getFit('OpenFOAM', m, metric)?.slope, SimScale: getFit('SimScale', m, metric)?.slope }));
  return <><div className="chart"><ResponsiveContainer width="100%" height="100%" initialDimension={{width:600,height:300}}><LineChart data={rows} margin={{top:20,right:24,left:10,bottom:25}} accessibilityLayer><CartesianGrid vertical={false} stroke="#ededed"/><XAxis type="number" dataKey="mach" domain={[.3,.9]} ticks={raw.machs} axisLine={false} tickLine={false} tickFormatter={v => v.toFixed(2)} label={{value:'Mach',position:'bottom',offset:6}}/><YAxis tickFormatter={tick} width={70} axisLine={false} tickLine={false}/><Tooltip content={<ChartTip xLabel="Mach" xUnit=""/>}/>{solvers.map(s => <Line key={s} dataKey={s} name={s} stroke={colors[s]} strokeWidth={2} dot={{r:4}} isAnimationActive={false}/>)}</LineChart></ResponsiveContainer></div><Legend flags={false}/></>;
}
export function ParityChart({ metric, quality }: { metric: Metric; quality: boolean }) {
  const pairs = raw.pairs.filter(p => p.metric === metric && (!quality || !p.flagged));
  const bounds = pairs.flatMap(p => [p.openfoam, p.simscale]);
  const low = Math.min(0, ...bounds), high = Math.max(0, ...bounds), pad = (high-low)*.07 || 1;
  return <><div className="chart"><ResponsiveContainer width="100%" height="100%" initialDimension={{width:600,height:300}}><ScatterChart margin={{top:20,right:25,left:22,bottom:28}} accessibilityLayer><CartesianGrid stroke="#ededed"/><XAxis type="number" dataKey="openfoam" domain={[low-pad,high+pad]} tickFormatter={tick} axisLine={false} tickLine={false} label={{value:'OpenFOAM',position:'bottom',offset:6}}/><YAxis type="number" dataKey="simscale" domain={[low-pad,high+pad]} tickFormatter={tick} width={65} axisLine={false} tickLine={false} label={{value:'SimScale',angle:-90,position:'insideLeft',offset:-8}}/><ZAxis range={[42,42]}/><ReferenceLine segment={[{x:low-pad,y:low-pad},{x:high+pad,y:high+pad}]} stroke="#a3a3a3" strokeDasharray="5 5"/><Tooltip content={({active,payload}) => { const p=payload?.[0]?.payload; return active && p ? <div className="chart-tip"><strong>M{p.mach.toFixed(2)} · {p.angle}°</strong><div>OpenFOAM <b>{fmt(p.openfoam,6)}</b></div><div>SimScale <b>{fmt(p.simscale,6)}</b></div><div>Δ <b>{signed(p.delta,6)}</b></div>{p.flagged && <small>Source convergence flag</small>}</div> : null; }}/><Scatter data={pairs} fill={colors.SimScale} fillOpacity={.72} isAnimationActive={false}/></ScatterChart></ResponsiveContainer></div><div className="legend"><span><i style={{background:colors.SimScale}}/>{pairs.length} paired conditions</span><span><i className="dashed"/>Equal prediction</span></div></>;
}
