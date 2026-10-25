# CFD sweep dashboard

Local interactive analysis of the **sealed-tab (v5) sweep** (CAD 11 Sep 2026, runs 11–14 Sep). OpenFOAM: 56 points (M0.30–0.90 × 8 deflections; 15° and −6° at M0.90 are transient restarts) plus a 15° / M1.2 case; SimScale: 48 points (M0.30–0.85 × 8 deflections); 48 paired conditions.

Tabs: Overview · Solver comparison · Sealed vs previous (point-by-point vs the 4 Sep gap sweep) · Transonic & M1.2 (transients, M1.2, videos) · Hand estimates (strip theory, vortex lattice and Ackeret vs CFD) · Mesh study (sealed grid check, both solvers) · Data & method.

The production server runs on the Mac mini (`trasomi@100.83.170.110`, checkout `~/dev/rocket/cfd`) as the `com.trasomi.cfd-dashboard` LaunchAgent (`wrangler dev` on `dist/`, 127.0.0.1:3000). After changes: `python3 scripts/analyze.py && python3 scripts/heuristics.py && npm run build && launchctl kickstart -k gui/$(id -u)/com.trasomi.cfd-dashboard`.

## Analysis

`python3 scripts/analyze.py` snapshots the sources into `analysis/raw` on first run (SHA-256 in `analysis/manifest.json`; delete it to re-snapshot) and writes `public/data/{sweep.json, normalized.csv, fits.csv, comparison.csv, previous-sweep.csv, mesh-study.json, manifest.json}`. It does not touch simulations or the spreadsheet.

Sources: `runs_v4/*/M*_sealedcad_fine_opensides`, `runs_v4/{d15,dm06}/M0.90_sealedcad_fine_transient`, `runs_v4/d15/M1.20_sealedcad_fine_{transient,restart}`, `simscale_sealed/results/ss_sweep_*_fine_sealed.json`, grid check `results/mesh_independence_sealed_20260911` + SimScale `*_refined_sealed_h0.2.json`.

Percent differences use the ratio form 100 (a/b − 1), so a larger magnitude reads positive at negative deflections too. Moments are transformed from z = 0.399 m to z = 0.330 m, as before.

Videos in `public/media` are faststart copies of `results/anim/*.mp4` (the wrangler server ignores Range requests, so the index must be at the front).

`python3 scripts/heuristics.py` (needs numpy) reads `analysis/sweep.json` and writes `analysis/heuristic.json` and `public/data/heuristic.csv`: hand-method roll-moment estimates from the sealed-tab CAD geometry (measured from `../models_v4/d00`, the CFD-workspace export), compared against the sweep. Geometry constants and method notes are in the script's docstring.

## Previous sweep (archived)

The 4 Sep gap-sweep dashboard data is frozen in `analysis/legacy/` and `public/data/legacy-v4/`; its scripts are in `scripts/legacy/` (outputs repointed there). A full pre-change backup is `../results/sweep-dashboard_backup_2026-09-22.tgz`.

## Validation

Production build, TypeScript and focused lint checks. Independent OLS algebra checked every saved fit; reference transformations, coefficient round trips, matched angle sets, exclusions, and missing-data handling checked against raw snapshots. Chrome validation covers metric and fit selection, insufficient-point states, M0.90 coverage, comparisons, provenance, exports and responsive layout.

No Git commands were used. The dashboard is served locally; hosted Sites publication requires Git source upload, which is excluded by the user's workspace instructions.

## Tailscale access

Private route: http://trasos-mini-2.tail663a4e.ts.net:3000/

Tailscale Serve forwards TCP port 3000 to 127.0.0.1:3000, so both the hostname and http://100.83.170.110:3000/ work. The laptop must be connected to the same tailnet and allowed by its access policy. Keep the Mac awake and the dashboard server running. Disable only this route with `tailscale serve --tcp=3000 off`.

The server is the LaunchAgent `~/Library/LaunchAgents/com.trasomi.cfd-dashboard.plist` (RunAtLoad + KeepAlive), so it comes back after a reboot or login; the Tailscale Serve route also persists. Inspect with `launchctl print gui/$(id -u)/com.trasomi.cfd-dashboard`; if it shows `runs = 0` after loading, start it with `launchctl kickstart gui/$(id -u)/com.trasomi.cfd-dashboard`. Remove it with `launchctl bootout gui/$(id -u)/com.trasomi.cfd-dashboard` and delete the plist. Logs are in `.runtime/`.
