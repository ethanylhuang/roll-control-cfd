# SimScale API sweep — design (2026-09-02, revised 09-04)

Run the v4 matrix (δ = 0, 3, 6, 9, 12, 15, −6°; M0.3–0.8) on SimScale via its
REST API, in parallel with the local OpenFOAM v4 sweep, inheriting the
settings the user tuned in their **roll-control** project.

## Ground rules (from the user)

- All work happens in an API-made **copy**: "roll-control API sweep (copy)",
  project `4625983764381654020`. The original (`5692073260772831163`) is
  never written to.
- Drive everything through APIs (Onshape + SimScale); the browser is a last
  resort, approved only for the two things the API cannot do.
- API key in `~/.config/simscale/credentials.env` (0600), never in the repo.
- The local OpenFOAM sweep belongs to another agent — this pipeline must not
  touch `runs_v4/`, `run_sweep.py`, or any local solver process.

## What the API can and cannot do (verified against the live API)

| Need | Status |
|---|---|
| project copy, geometry import, table import, mesh op, simulation, run, results | full API |
| **flow volume extraction (CAD mode)** | **no endpoint** — the only UI step |
| **delete geometry / mesh / simulation / run** | **no endpoint** (only subruns, reports, materials, folders) |
| schema versions | `POST` must carry the reference object's `version` (`internal:65` mesh, `internal:628` sim); the public versions reject `FULL_SNAPPY_HEX_MESH` and the copied spec |
| STL geometry | imports as a **sheet body**; COMPRESSIBLE refuses it ("faces which are not part of a volume"). `optimizeForLBMSolver` is the faceted path and is for the LBM solver only |
| mesh start | needs `simulationId` for physics-based meshing, so the **simulation must exist before the mesh** (a bare start returns HTTP 500) |

## Architecture

Geometry per deflection:

1. `simscale_onshape.export_parasolid` sets `#deflection` through the same
   feature API the STL exporter uses, exports the Part Studio as **Parasolid**
   (solids, not facets), then **re-reads `#deflection`** — a concurrent writer
   (the local sweep exporting its own geometry) cannot silently hand us the
   wrong angle. ~4 Onshape requests per deflection.
2. Import into the copy as `dXX rocket (delta=N, API)`. All seven import
   identically: **90 faces, 4 regions** — that uniformity is what makes the
   swap below legitimate.
3. **Flow volume extraction in the Workbench** (the one UI step), saved as
   `dXX flow region`. The sweep finds it by name; until then the deflection is
   reported as `waiting_for_extraction` and the rest of the matrix proceeds.

Mesh and simulation per deflection — the user's geometry-swap insight:
because every geometry comes from one feature tree with only `#deflection`
changed and is extracted the same way, **face IDs are identical**, so the
reference mesh operation ("Mesh 31") and simulation ("Compressible") are
cloned **verbatim** and only `geometryId` changes. No face classification, no
re-assignment. `check_face_template` verifies the reference's wall faces all
exist on the new geometry and refuses the case if they do not — the swap is
checked, not assumed.

Runs: one inlet velocity table per Mach (`T,Ux,Uy,Uz`, −50 → −V over 300
iterations, clamped), PUT onto the spec, run created and started, up to
`max_concurrent_runs` in flight, polled every `poll_seconds`.

Results: FORCE/MOMENT plot CSVs are converted to OpenFOAM function-object
`.dat` files under `postProcessing/<name>/0/`, and `coefficient.dat` is
computed with the v4 reference values (lift +x, drag −z, pitch +y, Dref,
Sref = πD²/4). `report.py` then builds the table unchanged — convergence
gate, Cd band, Cd continuity across δ, SNR flags all apply.

Monitors: the reference monitor (CofR 0,0,0.33) is kept as `forces_ref033`;
`forces_all` adds the v4 CG (0,0,z_cg). Hinge monitors need the tab faces,
which cannot be identified through the API on an extracted geometry —
`tab_entities` / `tab_selection_set` in the config enable them; empty means
the hinge columns stay blank rather than wrong.

## Deviations from the local v4 protocol (report header states them)

endTime 3000 with the mean over the **final 500 iterations**; SimScale
residual controls 1e-5 can stop a run early (`stopped_on_residuals@N`, still
averaged over its final 500); first-order bounded upwind convection; 19.85 °C
walls; the reference relaxation set (ρ 0.1). **Do not compare these numbers
against the local v4 table** — same rule as v1–v3 vs v4.

## Cost control

`estimate` runs before every mesh and run; `max_core_hours` (400) refuses work
that would exceed it; spend is tracked per object in the state file. A pilot
(d06/M0.6) must land within `pilot.tolerance_pct` of the user's own SimScale
result (Mroll 0.1055 N·m) before the rest of the matrix starts.

## Files

`scripts/simscale_api.py` (stdlib REST client, retries, pagination, request
counter), `simscale_onshape.py` (Parasolid export + verify), `simscale_sweep.py`
(orchestrator, resumable via `runs_simscale/simscale_state.json`),
`simscale_config.json`, `test_simscale_sweep.py` (offline suite, zero API
calls — ramp table, CSV→dat, coefficients, moment signs, spec cloning, hinge
projection).

## Status 2026-09-03

- Copy made; all 7 rocket geometries staged and deflection-verified.
- Offline suite passes; computed Cd 0.9117 matches the local v4 d06/M0.6 0.912.
- A validation run (d10/M0.6) on the user's already-extracted 10deg flow
  region is in flight, exercising every downstream step.
- Blocked on: the Chrome bridge (hook timeout) for extraction and cleanup.

## Revision 2026-09-04 (user's updated project, new Mach ladder)

- The user cleaned and re-tuned the original project: one geometry "10D"
  (extracted Flow region, 85 faces), "Mesh 33" (21x21x112, 924,707 cells),
  simulation `Compressible` internal:629 — second-order convection
  (`GAUSS_LINEARUPWINDV_GRAD_U_`), relaxation p 0.15 / U 0.5, adiabatic walls,
  inlet T 286.2 K, p 97,690 Pa, pressure limits 50–200 kPa, **constant inlet**
  (no table), monitor CofR (0,0,399 mm).
- New copy **"roll-control API sweep v2 (copy)" = `1269879333705405039`**; the
  09-02 copy and the probe project are renamed OBSOLETE (no API delete).
- Mach ladder: 0.3 (Prandtl–Glauert anchor), 0.5, 0.7, 0.8, 0.85, 0.9
  (predicted max), 0.95 (margin). V = M·a(T_ref) with a = 339.1 m/s from the
  reference inlet temperature, rounded to integers: 102, 170, 237, 271, 288,
  305, 322 m/s — M0.9 matches the user's own 10D_M0.9 run exactly.
- `inlet_mode: constant`: inlet and initial velocity both (0,0,−V), verified
  from the server read-back before every run — the reference's own approach,
  and immune to the project-copy table loss.
- Freestream (T, p, ρ, a) is read from the reference spec at prepare time; ρ
  feeds the coefficient maths.
- Moments for the sheet are about **(0,0,0.330) m** (`cg_point`), the
  convention the sheet "Aero roll control CFD data" already uses for its
  SimScale rows; the user's 399 mm monitor is kept in result.json as
  `forces_ref`. Roll is CofR-independent, yaw shifts ≈ Fy·Δz.
- Geometry: the CAD changed after the 09-03 exports (workspace modified
  09-04 04:05Z), so all seven rockets were re-exported (22 Onshape requests)
  and imported into the new copy. CAD-mode extraction (browser, Mac mini
  Chrome) edits each rocket geometry in place; the sweep recognises the
  result by its single "Flow region" and the reference face names.
- Results flow to the sheet after every finished run (`simscale_sheet.py`
  upserts C/E/G by (deflection, Mach); OpenFOAM columns are never touched).

## Revision 2026-09-04 (later): how the meshes actually get made

- `FULL_SNAPPY_HEX_MESH` operations cannot be started through the public API
  (`/start` and `/check` return HTTP 500 for API-made and Workbench-made ops
  alike; `/estimate` works), and a new op cannot reference the reference op's
  geometry-primitive UUIDs. So each deflection's simulation + mesh are made in
  the Workbench with the user's own recipe — duplicate `Compressible`, rename
  to `sweep dXX`, switch its geometry to the extracted `dXX rocket`, Generate
  — and the driver takes over from there.
- The Workbench geometry swap is lossy ("Partial mapping": 75 → 71 rocket
  wall faces, 70 → 66 / 69 → 65 in the refinements). `simscale_repair.py`
  puts the reference lists back; the driver runs it automatically every poll
  for any pending `sweep dXX`, so the only ordering constraint is to wait a
  minute between the swap and Generate.
- Adoption: the driver polls for `sweep dXX`, attaches its finished
  hex-dominant mesh (the Workbench does not write `meshId` into the spec until
  the simulation is opened), adds the sweep's `forces_all` monitor at the
  sheet's CofR, and starts the Mach ladder. Runs recorded with only the user's
  monitor (CofR 399 mm) are converted by an exact moment transfer
  `M + (r_src − r_dst) × F` (`transfer_moments`, unit-tested).
- Inlet policy `per_mach`: constant (0,0,−V) below M0.8, start-up table
  −50 → −V over 1000 iterations at and above (the user's `ramp1000` fix).
- Results: d10 at 0.3–0.95 reproduces the user's own new-geometry run to four
  digits (M0.9: Mroll −0.1024 both), but its sign is opposite to the old
  geometry's rows in the sheet and to d06 on the same CAD (+0.079 at M0.7):
  the user's `10D` export appears to be deflected the other way. Flagged.

## Outcome 2026-09-04 07:45 — sweep complete

56/56 runs finished, no *branch* flags (Cd band / continuity), but every case above M0.3 carries `mroll_noisy`: the updated numerics limit-cycle (see below). 381.7 CPUh on runs (+≈14 CPUh for
seven Workbench meshes). Results: `results/simscale_v2/sweep_table.{csv,md}`
(49 rows: δ = −6…15°), per-case `runs_simscale_v2/dXX/MY.YY/result.json`,
and the Google Sheet "Aero roll control CFD data" (SimScale columns, 56 rows).

Roll moment about (0,0,0.33) m, N·m:

| δ | M0.3 | M0.5 | M0.7 | M0.8 | M0.85 | M0.9 | M0.95 |
|---|---|---|---|---|---|---|---|
| −6 | −0.025 | −0.065 | −0.095 | −0.091 | −0.094 | −0.098 | −0.107 |
| 0 | 0.000 | −0.003 | −0.008 | −0.007 | −0.011 | −0.011 | −0.012 |
| 3 | 0.010 | 0.024 | 0.034 | 0.035 | 0.035 | 0.038 | 0.040 |
| 6 | 0.024 | 0.053 | 0.079 | 0.079 | 0.081 | 0.088 | 0.084 |
| 9 | 0.034 | 0.079 | 0.113 | 0.100 | 0.113 | 0.112 | 0.127 |
| 12 | 0.046 | 0.113 | 0.151 | 0.142 | 0.142 | 0.130 | 0.135 |
| 15 | 0.054 | 0.124 | 0.178 | 0.168 | 0.178 | 0.169 | 0.168 |

Observations: authority grows with Mach up to ~M0.7 and plateaus through
the transonic range (Cd falls 0.95 → 0.69 from M0.7 to M0.95 for every δ);
near-linear in δ to 9°, sub-linear beyond (15° ≈ 2.1× 6°); a small negative
standing moment at 0° (−0.003…−0.012); −6° gives 15–20 % more roll than +6°
above M0.5 (single-tab asymmetry).

The user's "10D" geometry reproduces the −6° row at every Mach (e.g. M0.8:
−0.0916 vs −0.0914): the previous scripted export had left `#deflection` at
−6°, and the manual 10D export inherited it. `#deflection` was reset to 0°
after the sweep; `simscale_onshape.py --reset` does this going forward.

### Convergence caveat (2026-09-04, post-sweep audit)

All runs reached endTime 3000, but with the 09-04 numerics (second-order
linearUpwindV, relaxation p 0.15 / U 0.5, potential-flow init) the steady
solver does not settle above M0.3. The roll moment oscillates with a fixed
iteration period (≈8 it at M0.5, 28 at M0.7, 33–38 at M0.8–0.95) at
80–130 % of its mean; Ux/Uz/h residuals stall at ~1e-2 (k ~1e-3, ω ~5e-6),
flat over the last 500 iterations. M0.3 is clean (std ≤ 11 %). The user's
earlier setup (first-order bounded upwind, p 0.3 / U 0.7) converged to
0.02 % scatter at M0.6 on the same geometry family.

Reported values are 500-iteration cycle averages. Window-to-window
reproducibility (max deviation of the three preceding 500-it windows from the
reported one): median 6.6 %; ≤ 15 % for δ ≥ 6°; but 26–50 % for δ = 3° and
−6° at M ≥ 0.8, where the cycle amplitude is comparable to the small mean.
`report.py` flags every such row `mroll_noisy`/`mroll_drift`; the Google
Sheet rows carry no flag (caveat column offered to the user). Cause not yet
isolated: candidates are the 50 kPa lower pressure clamp (suction peaks at
M ≥ 0.7 fall below it for Cp < −1.4…−0.9) and the second-order scheme.
Proposed diagnostics: one M0.9 case with the lower bound at 10 kPa, one with
the old first-order scheme (~6.5 CPUh each).
