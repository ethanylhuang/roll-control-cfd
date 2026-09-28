"""fill_coeff_row.py <case_dir> : write one converged steady case (fine mesh, 2nd order) into sheet tab 'v4 coeff sweep',
row matched by (Mach, deflection). Also usable with --init to (re)create the tab with the full Mach x deflection matrix."""
import json, os, subprocess, sys, time, math
SID = "1HBUH8UWuBCjaj4L-XtFVqeN6muDlGZhOQa-Z9IvfLCg"; TAB = "v4 coeff sweep SimScale"
MACHS = [0.3, 0.5, 0.6, 0.7, 0.8, 0.85, 0.9]; DEFLS = [-6, 0, 3, 6, 9, 10, 12, 15]
RHO, SREF, DREF, ZSHIFT = 1.18915, 0.0026248, 0.05781, 0.069   # rho_inf at 97690 Pa / 286.2 K; Sref, Dref from flowSettings; CofR 0.399 -> 0.330
env = dict(os.environ, GOOGLE_WORKSPACE_CLI_KEYRING_BACKEND="file")
def gws(*args, retries=5):
    for i in range(retries):
        out = subprocess.run(["gws", *args], capture_output=True, text=True, env=env)
        if out.returncode == 0: return out.stdout
        time.sleep(20)
    raise SystemExit("gws failed: " + out.stderr[-300:])
def vel(m): return 305.0 if abs(m - 0.9) < 1e-6 else round(m * 339.1, 1)
HEAD = [["goonmax tab CFD, matching SIMSCALE sweep, steady 2nd order, FINE per-deflection hex-dominant mesh (1.60M cells, mirror of the local snappy settings: body L5, fins+tab L6 + L6 tab box, 4 layers) for 3 to 15 deg and -6 deg, and the 0 deg row on the 0.92M coarse mesh (it is zero either way): Mach x tab deflection, tab clearance FILLED, open sides, CFD-branch CAD (= 2026-09-04 export). Completed 2026-09-07 03:41 (36 fine runs, 17:05-03:41, ~460 CPUh). The coarse-mesh pass was stopped after the 0/3/6 deg rows because the coarse mesh under-resolves small deflections (3 deg: 2-3.6x low)."],
        ["Settings: SimScale compressible steady (simscaleRhoSimpleFoam), k-omega SST, linearUpwindV momentum, inlet k/omega FIXED 13.98/93500 (not automatic), cell-limited least-squares gradients (SimScale default), ramp 50->V over 300 it, relax p0.3/rho0.05/eq0.7, pressure bounds 20-300 kPa, endTime 3000, mean of iterations 2500-3000; hex-dominant mesh: body L4-5 / fins+tab L5-6, 4 layers, no gap cutout (0.92M cells at every deflection). Freestream 97690 Pa, 286.2 K, rho 1.18915, V = Mach x 339.1 (305 at M0.9)."],
        ["Conventions: body axis = z (nose +z, flow along -z). Forces in body axes (N): Fx, Fy lateral, Fz axial. Moments about (0, 0, 0.330) m: Mroll about -z (flight direction, positive = tab roll sense), Mpitch about +y, Myaw about +x. Coefficients: q = 0.5 rho V^2, Sref = 0.0026248 m^2, Dref = 0.05781 m; CA = -Fz/(q Sref) (axial, positive aft), CY = Fy/(q Sref), CN = Fx/(q Sref), Cl = Mroll/(q Sref Dref), Cm = Mpitch/(q Sref Dref), Cn = Myaw/(q Sref Dref)."],
        ["Quality: Mroll std = scatter of the 250-iteration block means over the 1500-iteration averaging window (the steady solver sits in a fast iteration-to-iteration limit cycle, half-period ~12 iterations, whose mean is stable to ~1 %; rows written before 2026-09-06 18:00 show the raw iteration scatter instead), drift = change between the first and last quarter of the window; flags mroll_drift / mroll_noisy if either exceeds 3 %. Mpitch at zero angle of attack is a near-cancellation (sensitive to ~1 mm of axial station): report Cm as scatter-bounded. Rows grouped by Mach for deflection fits at fixed Mach. M0.9/M0.95 rows left empty: SimScale steady second order does not converge in the transonic range (see the transient run)."],
        ["Geometry: Onshape document roll-control, branch CFD = the 2026-09-04 export (the 2026-09-05 Main-branch export carried an unintended fin pocket; every result made with it was discarded on 2026-09-06). Mesh check (10 deg, fine 1.60M mirror mesh vs coarse 0.92M, same settings): Mroll coarse/fine = +0.8 % at M0.3 and +0.8 % at M0.5, Myaw +7 % / +1 %, side force +6 % / +1 %, but axial force Fz +16 % on the coarse mesh at both Machs -> CA from this sweep carries a ~15 % coarse-mesh over-prediction; Cl, Cn, CY do not. Coarse-mesh scatter is larger (std 7-10 % vs 2-4 %). Fine-mesh 10 deg rows are in the block below the matrix."],
        ["Mach", "V (m/s)", "Deflection (deg)", "q (Pa)", "Mroll (N.m)", "Mpitch (N.m)", "Myaw (N.m)", "Fx (N)", "Fy (N)", "Fz (N)", "CA", "CY", "CN", "Cl", "Cm", "Cn", "Mroll std", "Mroll drift", "flags", "case"]]
FINE_MACHS = [0.3, 0.5, 0.6, 0.7, 0.8, 0.85]
FINE_HEAD_ROW = len(HEAD) + 1 + len(MACHS) * len(DEFLS) + 1     # one blank row after the matrix
FINE_HEAD = ["Fine-mesh check rows: 10 deg on the SimScale fine v3 local-mirror mesh (1.60M cells: body L5, fins/tab L6 + L6 tab box, 4 layers), identical solver settings, same CAD; not part of the fit matrix"]
FIRST_DATA_ROW = len(HEAD) + 1
def row_index(mach, defl, fine=False):
    if fine: return FINE_HEAD_ROW + 1 + FINE_MACHS.index(mach)
    return FIRST_DATA_ROW + MACHS.index(mach) * len(DEFLS) + DEFLS.index(defl)
def is_fine(case):
    return case.endswith(".json") and str(json.load(open(case)).get("mesh_name", "")).startswith("SimScale fine")
def coeff_row(case):
    r = json.load(open(case if case.endswith(".json") else os.path.join(case, "result.json"))); m = r["moments_Nm"]; f = r["forces_N"]; c = r.get("convergence") or {}
    mach = float(r["mach"]); defl = float(r["deflection"]); V = vel(mach); q = 0.5 * RHO * V * V
    myaw = m["Myaw"] - ZSHIFT * f["Fy"]; mpitch = m["Mpitch"] + ZSHIFT * f["Fx"]
    vals = [mach, V, defl, round(q, 1), round(m["Mroll"], 4), round(mpitch, 4), round(myaw, 4), round(f["Fx"], 3), round(f["Fy"], 3), round(f["Fz"], 2),
            round(-f["Fz"] / (q * SREF), 5), round(f["Fy"] / (q * SREF), 5), round(f["Fx"] / (q * SREF), 5),
            round(m["Mroll"] / (q * SREF * DREF), 5), round(mpitch / (q * SREF * DREF), 5), round(myaw / (q * SREF * DREF), 5),
            (f"{c.get('block_std_pct', c.get('std_rel_pct', 0)):.1f}%" if c else ""), (f"{c.get('drift_pct', 0):.2f}%" if c else ""), ", ".join(c.get("flags", [])) if c else "", ((r.get("run", "")[:8] + (" fine 1.60M" if ("fine" in str(r.get("mesh_name", "")).lower()) else " coarse 0.92M")) if case.endswith(".json") else os.path.basename(case.rstrip("/")))]
    return mach, defl, vals
if "--init" in sys.argv:
    meta = gws("sheets", "spreadsheets", "get", "--params", json.dumps({"spreadsheetId": SID, "fields": "sheets.properties"})); titles = [s["properties"]["title"] for s in json.loads(meta[meta.find("{"):])["sheets"]]
    if TAB not in titles: gws("sheets", "spreadsheets", "batchUpdate", "--params", json.dumps({"spreadsheetId": SID}), "--json", json.dumps({"requests": [{"addSheet": {"properties": {"title": TAB}}}]})); print("tab created")
    matrix = [[mach, vel(mach), defl] + [""] * 17 for mach in MACHS for defl in DEFLS]
    gws("sheets", "spreadsheets", "values", "update", "--params", json.dumps({"spreadsheetId": SID, "range": f"'{TAB}'!A1", "valueInputOption": "USER_ENTERED"}), "--json", json.dumps({"values": HEAD + matrix})); print(f"matrix written: {len(matrix)} rows from row {FIRST_DATA_ROW}")
if "--init" in sys.argv or "--header" in sys.argv:
    gws("sheets", "spreadsheets", "values", "update", "--params", json.dumps({"spreadsheetId": SID, "range": f"'{TAB}'!A1", "valueInputOption": "USER_ENTERED"}), "--json", json.dumps({"values": HEAD}))
    fine_rows = [FINE_HEAD] + [[10 if False else m, vel(m), 10] + [""] * 17 for m in FINE_MACHS]
    gws("sheets", "spreadsheets", "values", "update", "--params", json.dumps({"spreadsheetId": SID, "range": f"'{TAB}'!A{FINE_HEAD_ROW}", "valueInputOption": "USER_ENTERED"}), "--json", json.dumps({"values": fine_rows})); print(f"header + fine block written (fine block header row {FINE_HEAD_ROW})")
if "--clear" in sys.argv:   # --clear M,defl : blank the data cells (D:T) of one matrix row
    m, d = [float(x) for x in sys.argv[sys.argv.index("--clear") + 1].split(",")]; rr = row_index(m, d)
    gws("sheets", "spreadsheets", "values", "update", "--params", json.dumps({"spreadsheetId": SID, "range": f"'{TAB}'!D{rr}:T{rr}", "valueInputOption": "USER_ENTERED"}), "--json", json.dumps({"values": [[""] * 17]})); print(f"cleared row {rr}")
for case in [a for a in sys.argv[1:] if a.endswith(".json") or os.path.isdir(a)]:
    mach, defl, vals = coeff_row(case)
    fine = is_fine(case) and "--matrix" not in sys.argv
    if fine and (mach not in FINE_MACHS or defl != 10): print("skip (fine, not in fine block):", case, mach, defl); continue
    if not fine and (mach not in MACHS or defl not in DEFLS): print("skip (not in matrix):", case, mach, defl); continue
    rr = row_index(mach, defl, fine)
    gws("sheets", "spreadsheets", "values", "update", "--params", json.dumps({"spreadsheetId": SID, "range": f"'{TAB}'!A{rr}:T{rr}", "valueInputOption": "USER_ENTERED"}), "--json", json.dumps({"values": [vals]}))
    print(f"row {rr}: M{mach} d{defl:g} Mroll {vals[4]} Cl {vals[13]} CA {vals[10]} CY {vals[11]} CN {vals[12]} Cm {vals[14]} Cn {vals[15]} {vals[18]}")
