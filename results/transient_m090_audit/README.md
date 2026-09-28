# Mach 0.9 transient discrepancy audit

Checked 2026-09-07. Latest transient: **T4_fine30**, simulation `d17a4d46-7512-43fc-9234-fccd9acf69c8`, run `f14922f9-cc74-457c-b16d-0deea960985d` in project `1269879333705405039`. API status is CANCELED, but the force/moment histories and exported fields reach 0.030 s (7,500 steps). Use the available 30 ms record; do not describe it as a certified converged result.

[SimScale moment plot](https://www.simscale.com/workbench/?pid=1269879333705405039&rru=a4ce9cd2-f9cf-4c44-8449-8ae1cd98acd3&ci=fee8ed61-19e3-4efb-acff-c6e9dcfbe1b0&ct=PLOT&mt=SIMULATION_RESULT)

## Measured comparison

All roll moments are **-total Mz**, in N m, about (0,0,0.399 m), integrated over the complete body. These are moments, not normalized coefficients. Each average below is from that run's late history, not from equivalent initial conditions.

| Case | Averaging window | Mean roll | Standard deviation | Range |
|---|---|---:|---:|---:|
| SimScale T4 fine-v3 transient | 25.004–30.000 ms, 1250 points | 0.6244914 | 0.0121122 | 0.6046232–0.6408598 |
| Local fine transient | 7.504–10.000 ms, 625 points | 0.8123937 | 0.0015932 | 0.8095618–0.8150603 |
| Local fine steady | iterations 2500–3000, 501 points | 0.8238094 | 0.0078904 | 0.8030615–0.8421391 |

T4 is 23.13% below the local transient. Its final instantaneous value is 0.6076794. Its successive 5 ms means are 0.632063 (15–20 ms), 0.629436 (20–25 ms), and 0.624491 (25–30 ms). It has reached a much lower, mildly oscillating response; a long-time statistical mean and time-step independence remain unproven. There is no observed late recovery toward 0.81 within this record.

The pressure contribution is 0.625238 for T4 and 0.813453 for the local transient. The viscous contributions are -0.000747 and -0.001060. Thus essentially all of the discrepancy is a pressure-loading difference. This does not rule out indirect effects of wall treatment on the pressure field.

## Actual setup differences

The exported OpenFOAM dictionaries in `actual/` take precedence over UI labels and the saved JSON when they differ.

| Item | SimScale T4 | Local fine transient |
|---|---|---|
| Inlet | 50 to 305 m/s over 0–7 ms; constant thereafter | Constant 305 m/s |
| Initial field | Uniform U=(0,0,-50), p=97690 Pa, T=286.2 K | Full steady solution at iteration 3000 |
| Mesh | Fine-v3, 1,603,588 cells | Local fine, 1,500,457 cells |
| Solver | simscaleRhoPimpleFoam; exported fields identify v2406 | rhoPimpleFoam v2606, verified in log |
| Time scheme and step | Euler, fixed 4 microseconds | Euler, fixed 4 microseconds |
| Correctors | PIMPLE 2 outer × 2 pressure; 1 nonorthogonal | Same counts |
| Pressure gradient | cellLimited leastSquares 1 | Gauss linear, unlimited |
| Velocity/k/omega gradients | cellLimited leastSquares 1 | cellLimited Gauss linear 1 |
| Momentum convection | bounded Gauss localBlended upwind linearUpwindV grad(U) | Gauss linearUpwindV grad(U) |
| Transonic pressure algorithm | on | off |
| Intermediate p/rho relaxation | 0.7 / 1.0 | 0.3 / 0.05 |
| Final linear relative tolerances | Actual exported files: zero | zero |
| Pressure bounds | 10–500 kPa | 5–500 kPa |
| Side velocity | inletOutlet, zero return velocity | pressureInletOutletVelocity |
| Side/outlet temperature | zeroGradient | inletOutlet, return 286.2 K |
| Wall nut | nutUSpaldingWallFunction | nutkWallFunction |
| Omega wall blending | explicitly stepwise | default omegaWallFunction |

Correct inlet speed is verified in BOTH the exported CSV and the final U boundary: (0,0,-305). This latest discrepancy is not the previous 322 m/s inlet-table error. Air properties, nominal p/T, k=13.98, omega=93500, k-omega SST model, and force origin match.

The final exported blendedIndicatorU field is uniform zero. The presence of localBlended in fvSchemes alone is not evidence that first-order fallback caused the mismatch; this audit does not attribute the discrepancy to fallback without verifying the indicator's implementation and meaning.

## Strongest available diagnostic evidence

Existing local runs already apply the local solver to the exported SimScale fine-v3 mesh. Their last-501-iteration measurements are:

| Local steady diagnostic on the SAME SimScale mesh | Mean roll | Standard deviation |
|---|---:|---:|
| Local gradients and local BCs | 0.867008 | 0.062150 |
| Change only to SimScale's cellLimited leastSquares gradients for all fields | 0.720066 | 0.383278 |
| Change only to the tested SimScale BC/wall-function set | 0.848658 | 0.044410 |

The gradient-only change reduces that diagnostic's mean by about 17% and increases its fluctuations by about 6.2 times. These steady diagnostics are not all converged and do not isolate the exact 23% T4 offset. They do provide direct evidence that gradient treatment strongly affects this case. Merely using SimScale's mesh with the local numerics did not reproduce a 0.62 mean.

Gradient limiting modifies the reconstruction at cell faces; matching the label linearUpwindV does not match the method if grad(U), grad(p), and pressure coupling differ. See [OpenCFD's cell-limited gradient description](https://doc.openfoam.com/2306/tools/processing/numerics/schemes/gradient/rtm/cellLimited/).

## Time resolution and startup

The local transient is a restart from the steady result, so its 1.4% agreement with steady is a useful consistency check on that setup, not an independent cold-start or validation result.

T4 begins with the inlet 7 ms ramp and the body force develops slowly; substantial roll appears only around 12–16 ms. Only a few later oscillations fit in its available 30 ms history. A longer averaging interval is needed to establish the statistical mean, but the observed oscillation amplitude is much smaller than the 0.188 N m discrepancy.

During the final windows, the maximum Courant number is approximately 11.1 for T4 and 6.66 locally, despite the same nominal time step. Both schemes are implicit, so Co>1 alone does not prove an invalid calculation; neither result has demonstrated time-step independence here. [SimScale recommends sensitivity studies when selecting Courant limits](https://www.simscale.com/knowledge-base/time-step-transient-cfd-simulation/).

T4's final internal pressure range is 21.7–135.0 kPa; the local transient snapshot is 29.7–172.3 kPa. These are different meshes and snapshots, so maxima are not an accuracy ranking. T4's final pressure bounds are not active at these extrema. They support that the pressure field differs, rather than indicating a force-report sign or coefficient error.

## What would isolate the remaining cause

Use one mesh and a common developed initial field, then compare (1) the gradient settings, (2) the transonic pressure algorithm, and (3) side/wall conditions one change at a time. Repeat the settled transient at 2 microseconds and with additional outer correctors to check sensitivity to the temporal and inner-iteration resolution. Match generated dictionaries, including final solver settings, not only SimScale's saved JSON. No new simulations were launched by this audit.

## Data and reproduction

`run_spec.json` and `run_status.json` were read from SimScale on 2026-09-07. The three plot CSVs were downloaded afresh. `actual/` was extracted from the existing T4 solution archive at `/private/tmp/claude-501/-Users-trasomi-dev-cfd/e77796e5-73f1-4b54-ac10-df1a9b566759/scratchpad/sol_T4/solution.zip`; its inlet-table ID matches the immutable T4 run spec. The final incomplete residual CSV row has two missing columns and is excluded from residual/Courant statistics. The complete force and moment records are retained.

Local data come from `runs_v4/d10/M0.90_filled_fine_transient`, `M0.90_filled_fine_opensides`, and the `M0.90_simscale_v3mesh_local*` diagnostic cases. `analyze.py` generates `summary.json` and `analysis_output.txt`; `plot.py` creates `roll_comparison.png` using matplotlib.
