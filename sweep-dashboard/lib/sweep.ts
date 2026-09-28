import raw from '@/analysis/sweep.json';
export { raw };
export type Solver = 'OpenFOAM' | 'SimScale';
export type Metric = 'roll' | 'cl' | 'yaw' | 'cn' | 'pitch' | 'cm' | 'axial' | 'ca' | 'side' | 'cy' | 'normal' | 'cNormal';
export type Point = typeof raw.points[number];
export type Fit = typeof raw.fits[number];
export type GetFit = (s: Solver, m: number, k: Metric) => Fit | undefined;
export const solvers: Solver[] = ['OpenFOAM', 'SimScale'];
export const colors = { OpenFOAM: '#171717', SimScale: '#2563eb' };
export const palette = ['#94a3b8', '#0284c7', '#4f46e5', '#8b5cf6', '#b45309', '#dc2626', '#171717'];
export const metrics: Record<Metric, { label: string; symbol: string; unit: string }> = {
  roll: { label: 'Roll moment', symbol: 'Mroll', unit: 'N·m' },
  cl: { label: 'Roll coefficient', symbol: 'Cl', unit: '–' },
  yaw: { label: 'Yaw moment', symbol: 'Myaw', unit: 'N·m' },
  cn: { label: 'Yaw coefficient', symbol: 'Cn', unit: '–' },
  pitch: { label: 'Pitch moment', symbol: 'Mpitch', unit: 'N·m' },
  cm: { label: 'Pitch coefficient', symbol: 'Cm', unit: '–' },
  axial: { label: 'Axial force', symbol: 'FA', unit: 'N' },
  ca: { label: 'Axial coefficient', symbol: 'CA', unit: '–' },
  side: { label: 'Side force', symbol: 'Fy', unit: 'N' },
  cy: { label: 'Side-force coefficient', symbol: 'CY', unit: '–' },
  normal: { label: 'Normal force', symbol: 'Fx', unit: 'N' },
  cNormal: { label: 'Normal-force coefficient', symbol: 'CN', unit: '–' },
};
export const points = raw.points.filter(p => p.role === 'primary');
export const extraPoints = raw.points.filter(p => p.role !== 'primary');
export type Previous = typeof raw.previous[number];
export type GridCase = typeof raw.grid.cases[number];
const rollFits = raw.machs.map(m => [raw.fits.find(f => f.solver === 'OpenFOAM' && f.mach === m && f.metric === 'roll' && f.minAngle === -6 && f.maxAngle === 15 && !f.excludeFlagged), raw.fits.find(f => f.solver === 'SimScale' && f.mach === m && f.metric === 'roll' && f.minAngle === -6 && f.maxAngle === 15 && !f.excludeFlagged)] as const).filter(([a, b]) => a && b).map(([a, b]) => 100 * (b!.slope - a!.slope) / Math.abs(a!.slope));
export const stats = {
  of: points.filter(p => p.solver === 'OpenFOAM').length,
  ss: points.filter(p => p.solver === 'SimScale').length,
  pairs: new Set(raw.pairs.map(p => `${p.mach}|${p.angle}`)).size,
  slopeLo: Math.min(...rollFits), slopeHi: Math.max(...rollFits),
  prevPairs: new Set(raw.previous.map(p => `${p.solver}|${p.mach}|${p.angle}`)).size,
};
export const shortDate = (iso: string) => new Date(iso + (iso.length === 10 ? 'T12:00:00' : '')).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
export const fmt = (v: number | null | undefined, digits = 4) => v == null ? '—' : Math.abs(v) > 0 && Math.abs(v) < .0001 ? v.toExponential(2) : v.toLocaleString('en-US', { maximumFractionDigits: digits });
export const signed = (v: number, digits = 2) => `${v >= 0 ? '+' : '−'}${fmt(Math.abs(v), digits)}`;
export const tick = (v: number) => fmt(v, 3);
export const fitRange = [{ name: 'Full range · −6° to 15°', lo: -6, hi: 15 }, { name: 'Small positive · 0° to 10°', lo: 0, hi: 10 }, { name: 'Positive · 0° to 15°', lo: 0, hi: 15 }];
