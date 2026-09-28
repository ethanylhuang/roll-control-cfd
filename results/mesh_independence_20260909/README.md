# Adaptive mesh study — 9 September 2026

Purpose: assess discretization sensitivity of the existing steady fine-mesh sweep with the fewest useful extra cases. This is numerical verification; it does not establish agreement with real flight.

Initial local queue: (3°, M0.30), (15°, M0.85), (3°, M0.85), (15°, M0.30). Reuse two meshes at two Mach numbers. Each case retains its own original geometry, domain, physical model, boundary conditions and numerical schemes. Refine the background grid from 21×21×112 to 30×30×160 (spacing reduced to 0.7), holding refinement regions/levels and relative prism-layer settings fixed. Run serially on six local processes. Start at 3000 iterations, extend only if required, stop for review after 6000.

Initial SimScale targets: 3°/M0.30 and 15°/M0.85, using native copies of each fine recipe, with 25×25×118 changed to 36×36×169. Rounded axis ratios differ slightly; retain actual ratios in analysis. Preserve all existing CAD, boxes, layers and physics within SimScale. The two platforms' original recipes are not identical. Cross-platform agreement must not be mistaken for mesh independence.

Compare roll moment and Cl, yaw moment about z=0.330 m, side/normal force and axial force. Use the same final 1000-iteration window convention; retain four block means of 250 iterations. Initial mean-stability screen: roll, yaw and axial block standard deviation and first-to-last block drift each ≤0.5% of the mean. This is a screening rule, not a confidence interval. Use absolute tolerances for quantities near zero. Local 3° and 15° low-Mach references fail the yaw drift screen; isolated continuations are queued after the refinement cases.

Provisional spatial targets: ≤2% change in roll/Cl and axial force; ≤3% in yaw and side force, with iterative uncertainty smaller than the spatial tolerance. A two-mesh comparison screens sensitivity only. Add a third systematically refined grid at the most sensitive condition to establish an observed trend before estimating discretization uncertainty. Do not force Richardson extrapolation/GCI onto nonmonotonic or nonasymptotic results.

Follow-up selection must examine negative deflection, interior sweep anomalies and the local M0.90 endpoint. The four positive corners alone cannot certify those conditions. Add only cases justified by the first comparisons. Small roll changes do not excuse poor yaw convergence, inadequate wall layers, pressure clipping, conservation errors or unresolved near-wall behavior. Inspect layer coverage and wall y+ alongside force convergence.

Status files are authoritative: `local_status.json`, `baseline_extension_status.json`, and `budget.json`. Native SimScale/API specifications are saved beside this file. No cloud solver may start before its mesh succeeds and settings/quality checks pass. Reserve each cloud computation before starting, include prior work in the existing 500 CPUh ledger, and release reservations only against verified final costs.

User jobs: `com.trasomi.cfd-mesh-study` runs the local queue; `com.trasomi.cfd-mesh-baseline-extensions` waits for its completion before extending drifting references. These jobs save results to disk; they do not send notifications or certify convergence automatically.

Method reference: [NASA spatial convergence guidance](https://www.grc.nasa.gov/www/wind/valid/tutorial/spatconv.html).

## First cloud launch

3° mesh operation `ed040f6c-c63e-4d14-bb8e-f4cda8f818d7` completed with 3,232,874 cells, mesh `e579fe99-4af5-4d78-8c62-6cf08124a4e1`. Reported good mesh quality; actual cost 3.40528 CPUh. Native recipe was identical to the source before changing background resolution and runtime cap. Public legacy mesh check returns HTTP 500; native Generate completed successfully.

3°/M0.30 solver run `fab10443-3d6a-4a7d-9e46-a71140941ffb` submitted, 32 preferred cores, 3000 iterations, 4500-second/40-CPUh cap. Immutable run model and mesh ID matched the saved specification; simulation preflight returned no warnings/errors. Background job `com.trasomi.cfd-mesh-cloud-d03` monitors every five minutes and saves force histories/statistics at completion. It does not retry or expand its cost cap. It writes `cloud/d03/status.json`; submission is not convergence.

Baseline cloud histories were downloaded and the common-window parser validated against both source runs. At 15°/M0.85, roll block standard deviation is 0.0285%, but yaw is 0.5214% (marginally above the 0.5% screen). Do not interpret the entire result as unstable or automatically spend another run solely for that marginal threshold exceedance. Evaluate its iterative contribution against the observed mesh difference.

## Second cloud launch

15°/M0.85 isolated simulation `cf1a99b8-f3f2-4b61-850c-753fda2c43e5` uses native copied mesh operation `5ffc88ed-fee3-4756-a6ef-70ceed3af8b5`. Complete model equality with its source was verified before refinement; only `boundingBoxResolution` and `maxMeshingRunTime` differ afterward. Resolution 36×36×169, 32 preferred cores, 900-second/8-CPUh mesh cap. Native Generate was verified QUEUED. Public API start returns HTTP 500 for this legacy native recipe.

Background job `com.trasomi.cfd-mesh-cloud-d15` waits for successful mesh quality checks, then submits one exact-physics 3000-iteration solver run at 32 preferred cores with a 4500-second/40-CPUh cap. Status: `cloud/d15/status.json`. The two new mesh/solver reservations fit inside the prior 500-CPUh ceiling; current conservative remaining allocation is 4.79034 CPUh before releasing unused portions at completion. Do not start additional cloud work without reconciling actual costs first.

A failed API-only copy attempt left never-run operation `51865169-739c-4f72-a3b0-040f070bc1d8`, labeled `UNUSED API draft - missing native regions - DO NOT RUN`. It is not assigned to the study solver and must not be used for mesh comparisons.

Chrome workbench tabs were closed after submission. The local and cloud jobs continue independently, but first-stage completion still requires review and adaptive follow-up; no whole-sweep mesh-independence conclusion has been established.

## Outcome review — 10 September

All four local refined cases and both local reference extensions finished. Local roll changes are approximately -28.35%, -34.54%, -31.28%, and -37.34% at d03/M0.30, d03/M0.85, d15/M0.30, d15/M0.85, respectively (extended low-Mach references used). Only d15/M0.30 passes the complete configured mean-stability screen. These do not establish mesh independence.

Cloud d03 finished, but its inlet table differs from the immutable baseline run: the worker copied the current editable simulation. Earlier statements about matched inlet settings were therefore incorrect. Quarantine this comparison until the actual inlet contents and other immutable-run differences are resolved. Cloud d15 failed near startup with thermodynamic temperature-inversion iteration limit. No additional solve was launched during this status review. The completed launchctl jobs were unloaded because they relaunched and overwrote status; saved final results remain intact. See immutable_run_audit.json.
