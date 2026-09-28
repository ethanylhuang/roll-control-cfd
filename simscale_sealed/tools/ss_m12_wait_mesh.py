"""poll the M1.2 project's mesh op until it ends (prints one line per status change; exits 0 on FINISHED, 1 otherwise)"""
import os, sys, json, time
sys.path.insert(0, os.path.expanduser("~/.claude/skills/cfd-sweep/scripts")); from simscale_api import SimScale
api = SimScale(); J = json.load(open("/Users/trasomi/dev/cfd/simscale_sealed/m12_project.json")); P = J["new_project"]; op_id = J["mesh_op"]; last = None; t0 = time.time()
while time.time() - t0 < 4 * 3600:
    op = api.mesh_op(P, op_id); s = op.get("status")
    if s != last: print(time.strftime("%H:%M:%S"), "mesh op", op_id[:8], s, "meshId", op.get("meshId"), flush=True); last = s
    if s == "FINISHED":
        J["mesh_id"] = op["meshId"]; json.dump(J, open("/Users/trasomi/dev/cfd/simscale_sealed/m12_project.json", "w"), indent=1)
        try: m = api.mesh(P, op["meshId"]); print("mesh:", json.dumps({k: m.get(k) for k in ("name", "meshId", "cellCount", "status")})[:300], flush=True)
        except Exception as e: print("mesh info failed", e)
        sys.exit(0)
    if s in ("FAILED", "CANCELED", "ERROR"): sys.exit(1)
    time.sleep(120)
print("timeout"); sys.exit(2)
