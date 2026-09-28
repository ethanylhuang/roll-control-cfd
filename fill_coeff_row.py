"""fill_coeff_row.py <case_dir> : write one converged steady case (fine mesh, 2nd order) into sheet tab 'v4 coeff sweep',
row matched by (Mach, deflection). Also usable with --init to (re)create the tab with the full Mach x deflection matrix."""
import json, os, subprocess, sys, time, math
SID = "1HBUH8UWuBCjaj4L-XtFVqeN6muDlGZhOQa-Z9IvfLCg"; TAB = "v4 coeff sweep"
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
HEAD = [["goonmax tab CFD, exhaustive local OpenFOAM sweep: Mach x tab deflection, tab clearance FILLED (sealed by the mesh), open sides, geometry = Onshape document roll-control, branch CFD (identical to the 2026-09-04 export; the 2026-09-05 Main-branch export with the fin pocket was discarded). 10 deg series 2026-09-05, other deflections started 2026-09-06 12:45."],
        ["Settings (most accurate validated set): steady rhoSimpleFoam v2606, k-omega SST, linearUpwindV momentum, Gauss linear gradients (cell-limited for U/k/omega), ramp 50->V over 300 it, relax p0.3/rho0.05/eq0.7, pressure bounds 20-300 kPa, endTime 2000, mean of iterations 1500-2000; fine snappy mesh per deflection (body L5, fins/tab L6, 4 layers, ~1.5 M cells). Freestream 97690 Pa, 286.2 K, rho 1.18915, V = Mach x 339.1 (305 at M0.9)."],
        ["Conventions: body axis = z (nose +z, flow along -z). Forces in body axes (N): Fx, Fy lateral, Fz axial. Moments about (0, 0, 0.330) m: Mroll about -z (flight direction, positive = tab roll sense), Mpitch about +y, Myaw about +x. Coefficients: q = 0.5 rho V^2, Sref = 0.0026248 m^2, Dref = 0.05781 m; CA = -Fz/(q Sref) (axial, positive aft), CY = Fy/(q Sref), CN = Fx/(q Sref), Cl = Mroll/(q Sref Dref), Cm = Mpitch/(q Sref Dref), Cn = Myaw/(q Sref Dref)."],
        ["Quality: std = scatter of Mroll over the averaging window, drift = linear drift over the window; flags list mroll_drift / mroll_noisy if either exceeds 3 % / 5 %. Mpitch at zero angle of attack is a near-cancellation (sensitive to ~1 mm of axial station): report Cm as scatter-bounded. Rows grouped by Mach for deflection fits at fixed Mach. M0.95 excluded: steady second order does not converge there."],
        [],
        ["Mach", "V (m/s)", "Deflection (deg)", "q (Pa)", "Mroll (N.m)", "Mpitch (N.m)", "Myaw (N.m)", "Fx (N)", "Fy (N)", "Fz (N)", "CA", "CY", "CN", "Cl", "Cm", "Cn", "Mroll std", "Mroll drift", "flags", "case"]]
FIRST_DATA_ROW = len(HEAD) + 1
def row_index(mach, defl):
    return FIRST_DATA_ROW + MACHS.index(mach) * len(DEFLS) + DEFLS.index(defl)
def coeff_row(case):
    r = json.load(open(os.path.join(case, "result.json"))); m = r["moments_Nm"]; f = r["forces_N"]; c = r.get("convergence") or {}
    mach = float(r["mach"]); defl = float(r["deflection"]); V = vel(mach); q = 0.5 * RHO * V * V
    myaw = m["Myaw"] - ZSHIFT * f["Fy"]; mpitch = m["Mpitch"] + ZSHIFT * f["Fx"]
    vals = [mach, V, defl, round(q, 1), round(m["Mroll"], 4), round(mpitch, 4), round(myaw, 4), round(f["Fx"], 3), round(f["Fy"], 3), round(f["Fz"], 2),
            round(-f["Fz"] / (q * SREF), 5), round(f["Fy"] / (q * SREF), 5), round(f["Fx"] / (q * SREF), 5),
            round(m["Mroll"] / (q * SREF * DREF), 5), round(mpitch / (q * SREF * DREF), 5), round(myaw / (q * SREF * DREF), 5),
            (f"{c.get('std_rel_pct', 0):.1f}%" if c else ""), (f"{c.get('drift_pct', 0):.2f}%" if c else ""), ", ".join(c.get("flags", [])) if c else "", os.path.basename(case.rstrip("/"))]
    return mach, defl, vals
if "--header" in sys.argv:
    gws("sheets", "spreadsheets", "values", "update", "--params", json.dumps({"spreadsheetId": SID, "range": f"'{TAB}'!A1", "valueInputOption": "USER_ENTERED"}), "--json", json.dumps({"values": HEAD})); print("header rewritten")
if "--clear" in sys.argv:   # --clear M,defl : blank the data cells (D:T) of one matrix row
    m, d = [float(x) for x in sys.argv[sys.argv.index("--clear") + 1].split(",")]; rr = row_index(m, d)
    gws("sheets", "spreadsheets", "values", "update", "--params", json.dumps({"spreadsheetId": SID, "range": f"'{TAB}'!D{rr}:T{rr}", "valueInputOption": "USER_ENTERED"}), "--json", json.dumps({"values": [[""] * 17]})); print(f"cleared row {rr}")
if "--init" in sys.argv:
    meta = gws("sheets", "spreadsheets", "get", "--params", json.dumps({"spreadsheetId": SID, "fields": "sheets.properties"})); titles = [s["properties"]["title"] for s in json.loads(meta[meta.find("{"):])["sheets"]]
    if TAB not in titles: gws("sheets", "spreadsheets", "batchUpdate", "--params", json.dumps({"spreadsheetId": SID}), "--json", json.dumps({"requests": [{"addSheet": {"properties": {"title": TAB}}}]})); print("tab created")
    matrix = [[mach, vel(mach), defl] + [""] * 17 for mach in MACHS for defl in DEFLS]
    gws("sheets", "spreadsheets", "values", "update", "--params", json.dumps({"spreadsheetId": SID, "range": f"'{TAB}'!A1", "valueInputOption": "USER_ENTERED"}), "--json", json.dumps({"values": HEAD + matrix})); print(f"matrix written: {len(matrix)} rows from row {FIRST_DATA_ROW}")
for case in [a for a in sys.argv[1:] if os.path.isdir(a) or a.endswith(".json")]:
    mach, defl, vals = coeff_row(case)
    if mach not in MACHS or defl not in DEFLS: print("skip (not in matrix):", case, mach, defl); continue
    rr = row_index(mach, defl)
    gws("sheets", "spreadsheets", "values", "update", "--params", json.dumps({"spreadsheetId": SID, "range": f"'{TAB}'!A{rr}:T{rr}", "valueInputOption": "USER_ENTERED"}), "--json", json.dumps({"values": [vals]}))
    print(f"row {rr}: M{mach} d{defl:g} Mroll {vals[4]} Cl {vals[13]} CA {vals[10]} CY {vals[11]} CN {vals[12]} Cm {vals[14]} Cn {vals[15]} {vals[18]}")
