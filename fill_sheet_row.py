"""fill_sheet_row.py <case_dir>: write the OpenFOAM roll/yaw of a finished runs_v4/d10 case into sheet tab v2
(row matched by deflection 10 and Mach; appended if missing). Myaw shifted to CofR (0,0,0.330): Myaw - 0.069*Fy."""
import json, os, subprocess, sys
SID = "1HBUH8UWuBCjaj4L-XtFVqeN6muDlGZhOQa-Z9IvfLCg"; TAB = "v2"
env = dict(os.environ, GOOGLE_WORKSPACE_CLI_KEYRING_BACKEND="file")
def gws(*args):
    out = subprocess.run(["gws", *args], capture_output=True, text=True, env=env)
    if out.returncode: raise SystemExit(f"gws failed: {out.stderr[-600:]}")
    txt = out.stdout; i = txt.find("{"); return json.loads(txt[i:]) if i >= 0 else {}
case = sys.argv[1].rstrip("/"); r = json.load(open(os.path.join(case, "result.json")))
mach = float(r["mach"]); defl = float(r["deflection"]); mroll = r["moments_Nm"]["Mroll"]; myaw = r["moments_Nm"]["Myaw"] - 0.069 * r["forces_N"]["Fy"]
conv = r.get("convergence", {}); flags = conv.get("flags") or []
setup = f"OpenFOAM local 1.5M cells (levels 5/6/6), {r['mesh_name']}, {r.get('n_avg_samples')}-iter mean, endTime {os.path.basename(case)}"
setup = f"OpenFOAM local {r['mesh_name']} (levels 5/6/6, 1.5M cells); ramp300, relax {r['relax_overrides']}, p {int(r['pMin']/1000)}-{int(r['pMax']/1000)} kPa, open sides, tab FILLED; drift {conv.get('drift_pct', 0):.2f}% std {conv.get('std_rel_pct', 0):.2f}%" + (f"; FLAGS {flags}" if flags else "") + ("; FIRST-ORDER UPWIND momentum (biased low; 2nd-order steady limit-cycles at this Mach)" if r.get("div_u") == "upwind" else "")
vals = gws("sheets", "+read", "--spreadsheet", SID, "--range", f"{TAB}!A1:H60").get("values", [])
row = None
for i, v in enumerate(vals, start=1):
    try:
        if abs(float(v[0]) - defl) < 1e-6 and abs(float(v[1]) - mach) < 1e-6 and "MESH STUDY" not in (v[7] if len(v) > 7 else ""): row = i; break
    except (ValueError, IndexError): pass
def update(rng, values):
    gws("sheets", "spreadsheets", "values", "update", "--params", json.dumps({"spreadsheetId": SID, "range": rng, "valueInputOption": "USER_ENTERED"}), "--json", json.dumps({"values": values}))
if row:
    old = vals[row - 1]; h = old[7] if len(old) > 7 else ""
    update(f"{TAB}!D{row}", [[f"{mroll:.4f}"]]); update(f"{TAB}!F{row}", [[f"{myaw:.4f}"]])
    newh = (h[:h.index("OpenFOAM local")].rstrip("; ") + "; " + setup) if "OpenFOAM local" in h else ((h + "; " if h else "") + setup)
    update(f"{TAB}!H{row}", [[newh]])
    print(f"updated row {row}: M{mach} Mroll {mroll:.4f} Myaw(0.330) {myaw:.4f}")
else:
    V = round(mach * 339.1)
    gws("sheets", "spreadsheets", "values", "append", "--params", json.dumps({"spreadsheetId": SID, "range": f"{TAB}!A1:H", "valueInputOption": "USER_ENTERED", "insertDataOption": "INSERT_ROWS"}), "--json", json.dumps({"values": [[f"{defl:g}", f"{mach:g}", str(V), f"{mroll:.4f}", "", f"{myaw:.4f}", "", setup]]}))
    print(f"appended row: M{mach} Mroll {mroll:.4f} Myaw(0.330) {myaw:.4f}")
