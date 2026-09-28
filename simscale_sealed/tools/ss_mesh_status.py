import os, sys, json
sys.path.insert(0, os.path.expanduser("~/.claude/skills/cfd-sweep/scripts"))
from simscale_api import SimScale
api = SimScale(); COPY = "1269879333705405039"; SP = os.path.dirname(os.path.abspath(__file__))
for l in open(f"{SP}/sweep_mesh_ops_{sys.argv[1]}.txt").read().splitlines():
    tag, op = l.split(); full = api.mesh_op(COPY, op); print(tag, op[:8], full.get("status"), (full.get("meshId") or "")[:8], end=" | ")
print()
