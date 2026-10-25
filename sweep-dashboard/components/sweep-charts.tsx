'use client';
import type { ReactNode } from 'react';
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { ArrowDownToLine } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { colors, estimate, estimatedMethods, estMethods, fmt, metrics, palette, points, raw, solvers, tick, type EstMethod, type GetFit, type Metric, type Solver } from '@/lib/sweep';

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
export function EstSwatch({ method }: { method: EstMethod }) {
  const m = estMethods[method];
  return <span><i className={m.dashed ? 'dashed' : ''} style={m.dashed ? { borderTop: `2px dashed ${m.color}` } : { background: m.color }} />{m.label}</span>;
}
export function Legend({ fits = false, flags = true, estimates = [] }: { fits?: boolean; flags?: boolean; estimates?: EstMethod[] }) {
  return <div className="legend">{solvers.map(s => <span key={s}><i style={{ background: colors[s] }} />{s}</span>)}{fits && <span><i className="dashed" />Linear fit</span>}{estimates.map(e => <EstSwatch key={e} method={e} />)}{flags && <span className="muted"><b className="hollow" />Source flagged</span>}</div>;
}
function ChartTip({ active, payload, label, xLabel = 'Deflection', xUnit = '°' }: { active?: boolean; payload?: readonly { color?: string; name?: string | number; value?: unknown }[]; label?: string | number; xLabel?: string; xUnit?: string }) {
  if (!active || !payload?.length) return null;
  return <div className="chart-tip"><strong>{xLabel} {label}{xUnit}</strong>{payload.map((p, i) => <div key={i}><span style={{ color: p.color }}>{p.name}</span><b>{typeof p.value === 'number' ? fmt(p.value, 6) : String(p.value)}</b></div>)}</div>;
}
export function ResponseChart({ metric, mach, getFit, withFits = false }: { metric: Metric; mach: number; getFit: GetFit; withFits?: boolean }) {
  const meta = metrics[metric];
  const ests = estimatedMethods(metric, mach);
  const rows = raw.angles.map(angle => {
    const row: Record<string, number | boolean | undefined> = { angle };
    solvers.forEach(s => {
      const point = points.find(p => p.solver === s && p.mach === mach && p.angle === angle);
      row[s] = point?.[metric]; row[`${s}Flag`] = !!point?.flags.length;
      const fit = getFit(s, mach, metric);
      if (fit && angle >= Math.min(...fit.angles) && angle <= Math.max(...fit.angles)) row[`${s}Fit`] = fit.slope * angle + fit.intercept;
    });
    ests.forEach(e => { row[e] = estimate(e, metric, mach)! * angle; });
    return row;
  });
  return <><div className="axis-caption">{meta.symbol} <span>{meta.unit === '–' ? '(dimensionless)' : `(${meta.unit})`}</span></div><div className={`chart ${withFits ? 'hero-chart' : ''}`}><ResponsiveContainer width="100%" height="100%" initialDimension={{width:600,height:300}}><LineChart data={rows} margin={{ top: 14, right: 24, bottom: 24, left: 4 }} accessibilityLayer>
    <CartesianGrid vertical={false} stroke="#ededed" /><XAxis type="number" dataKey="angle" domain={[-6, 15]} ticks={[-6, 0, 3, 6, 9, 12, 15]} tickLine={false} axisLine={{ stroke: '#e5e5e5' }} tickMargin={10} label={{ value: 'Deflection δ (°)', position: 'bottom', offset: 6 }} />
    <YAxis tickFormatter={tick} axisLine={false} tickLine={false} width={62} domain={['auto', 'auto']} /><Tooltip content={<ChartTip />} /><ReferenceLine y={0} stroke="#d4d4d4" />
    {solvers.map(s => <Line key={s} name={s} dataKey={s} stroke={colors[s]} strokeWidth={2} connectNulls isAnimationActive={false} dot={(props: { cx?: number; cy?: number; payload?: Record<string, unknown>; index?: number }) => typeof props.payload?.[s] !== 'number' ? <g key={`${s}-${props.index}`} /> : <circle key={`${s}-${props.index}`} cx={props.cx} cy={props.cy} r={3.5} fill={props.payload?.[`${s}Flag`] ? 'white' : colors[s]} stroke={colors[s]} strokeWidth={1.7} />} activeDot={{ r: 6 }} />)}
    {withFits && solvers.map(s => <Line key={`${s}fit`} name={`${s} fit`} dataKey={`${s}Fit`} stroke={colors[s]} strokeDasharray="5 5" strokeWidth={1.3} opacity={.5} connectNulls dot={false} isAnimationActive={false} />)}
    {ests.map(e => <Line key={e} name={estMethods[e].label} dataKey={e} stroke={estMethods[e].color} strokeDasharray={estMethods[e].dashed ? '6 4' : undefined} strokeWidth={estMethods[e].dashed ? 1.6 : 2} dot={false} isAnimationActive={false} />)}
  </LineChart></ResponsiveContainer></div><Legend fits={withFits} estimates={ests} /></>;
}
export function FamilyChart({ metric, solver }: { metric: Metric; solver: Solver }) {
  const est: EstMethod | undefined = estimatedMethods(metric).includes('calibrated') ? 'calibrated' : estimatedMethods(metric).includes('vlm') ? 'vlm' : undefined;
  const family = raw.angles.map(angle => Object.fromEntries([['angle', angle], ...raw.machs.flatMap(m => [[`M${m}`, points.find(p => p.solver === solver && p.angle === angle && p.mach === m)?.[metric]], [`E${m}`, est && estimate(est, metric, m)! * angle]])]));
  return <><div className="axis-caption">{metrics[metric].symbol} ({metrics[metric].unit})</div><div className="chart family-chart"><ResponsiveContainer width="100%" height="100%" initialDimension={{width:600,height:300}}><LineChart data={family} margin={{ top: 10, right: 28, left: 4, bottom: 24 }} accessibilityLayer><CartesianGrid vertical={false} stroke="#ededed"/><XAxis type="number" dataKey="angle" domain={[-6,15]} ticks={[-6,0,3,6,9,12,15]} axisLine={false} tickLine={false} label={{ value: 'Deflection δ (°)', position:'bottom', offset:6 }}/><YAxis tickFormatter={tick} width={62} axisLine={false} tickLine={false}/><ReferenceLine y={0} stroke="#d4d4d4"/><Tooltip content={<ChartTip/>}/>{raw.machs.filter(m => solver === 'OpenFOAM' || m < .9).map((m,i) => <Line key={m} dataKey={`M${m}`} name={`M${m.toFixed(2)}`} stroke={palette[i]} strokeWidth={2} connectNulls dot={{ r:3 }} isAnimationActive={false}/>)}{est && raw.machs.filter(m => solver === 'OpenFOAM' || m < .9).map((m,i) => <Line key={`E${m}`} dataKey={`E${m}`} name={`M${m.toFixed(2)} ${estMethods[est].label}`} stroke={palette[i]} strokeDasharray="6 4" strokeWidth={1.2} opacity={.8} dot={false} isAnimationActive={false}/>)}</LineChart></ResponsiveContainer></div><div className="legend">{raw.machs.filter(m => solver === 'OpenFOAM' || m < .9).map((m,i) => <span key={m}><i style={{ background:palette[i] }}/>M{m.toFixed(2)}</span>)}{est && <span className="muted"><i className="dashed" />{estMethods[est].label} (same colour)</span>}</div></>;
}
export function SlopeChart({ metric, getFit }: { metric: Metric; getFit: GetFit }) {
  const ests = estimatedMethods(metric).filter(e => e !== 'linear');
  const rows = raw.machs.map(m => ({ mach: m, OpenFOAM: getFit('OpenFOAM', m, metric)?.slope, SimScale: getFit('SimScale', m, metric)?.slope, ...Object.fromEntries(ests.map(e => [e, estimate(e, metric, m)])) }));
  return <><div className="chart"><ResponsiveContainer width="100%" height="100%" initialDimension={{width:600,height:300}}><LineChart data={rows} margin={{top:20,right:24,left:10,bottom:25}} accessibilityLayer><CartesianGrid vertical={false} stroke="#ededed"/><XAxis type="number" dataKey="mach" domain={[.3,.9]} ticks={raw.machs} axisLine={false} tickLine={false} tickFormatter={v => v.toFixed(2)} label={{value:'Mach',position:'bottom',offset:6}}/><YAxis tickFormatter={tick} width={70} axisLine={false} tickLine={false}/><Tooltip content={<ChartTip xLabel="Mach" xUnit=""/>}/>{solvers.map(s => <Line key={s} dataKey={s} name={s} stroke={colors[s]} strokeWidth={2} dot={{r:4}} isAnimationActive={false}/>)}{ests.map(e => <Line key={e} dataKey={e} name={estMethods[e].label} stroke={estMethods[e].color} strokeDasharray={estMethods[e].dashed ? '6 4' : undefined} strokeWidth={estMethods[e].dashed ? 1.6 : 2} dot={{r:2.5}} isAnimationActive={false}/>)}</LineChart></ResponsiveContainer></div><Legend flags={false} estimates={ests}/></>;
}
