#!/usr/bin/env python3
"""Axial force (drag, +ve = aft) by region from foamToVTK -legacy -ascii wall patches (p, wallShearStress)."""
import sys, numpy as np
P_INF = 97690.0

def read_vtk(path):
    tok = open(path).read().split()
    i = tok.index('POINTS'); n = int(tok[i + 1]); pts = np.array(tok[i + 3:i + 3 + 3 * n], float).reshape(-1, 3)
    i = tok.index('POLYGONS'); nf = int(tok[i + 1]); j = i + 3; faces = []
    for _ in range(nf):
        k = int(tok[j]); faces.append([int(x) for x in tok[j + 1:j + 1 + k]]); j += k + 1
    data = {}
    i = tok.index('CELL_DATA'); j = i + 2
    while j < len(tok):
        if tok[j] == 'FIELD':
            nfld = int(tok[j + 2]); j += 3
            for _ in range(nfld):
                name, nc, nt = tok[j], int(tok[j + 1]), int(tok[j + 2]); j += 4
                data[name] = np.array(tok[j:j + nc * nt], float).reshape(nt, nc); j += nc * nt
            break
        j += 1
    S = np.zeros((nf, 3)); C = np.zeros((nf, 3))
    for f, idx in enumerate(faces):
        v = pts[idx]; C[f] = v.mean(0)
        S[f] = 0.5 * np.cross(v, np.roll(v, -1, 0)).sum(0)
    return C, S, data

case = sys.argv[1]
GEOM = sys.argv[2] if len(sys.argv) > 2 else 'new'
rows = {}
tot_p = tot_v = 0.0
for patch in ('rocket_body', 'rocket_fins', 'rocket_tab', 'rocket_slot'):
    C, S, d = read_vtk(f'{case}/VTK/{patch}/{patch}_2000.vtk')
    Fp = (d['p'][:, 0] - P_INF)[:, None] * S             # Sf points out of the fluid -> force on the wall
    Fv = -d['wallShearStress'] * np.linalg.norm(S, axis=1)[:, None]
    r = np.hypot(C[:, 0], C[:, 1]); z = C[:, 2]
    if patch == 'rocket_body' and GEOM == 'new':
        reg = np.full(len(C), 'body tube', dtype=object)
        reg[(z < 0.0205) & (np.abs(S[:, 2]) > 0.9 * np.linalg.norm(S, axis=1))] = 'base'
        reg[(z > 0.0205) & (z < 0.1405) & (r > 0.02905)] = 'fin can sleeve (body part)'
        reg[(z > 0.748) & (z < 0.796) & (r > 0.02902) & (C[:, 1] < 0) & (np.abs(C[:, 0]) < 0.022)] = 'camera shroud'
        reg[z > 1.2251] = 'nose'
    elif patch == 'rocket_body' and GEOM == 'bt':   # current CAD + Part Studio boattail (z -0.040..0.020, open aft end)
        reg = np.full(len(C), 'body tube', dtype=object)
        reg[z < 0.0205] = 'base (+ boattail, incl. cavity)'
        reg[(z > 0.0205) & (z < 0.1405) & (r > 0.02905)] = 'fin can sleeve (body part)'
        reg[(z > 0.748) & (z < 0.796) & (r > 0.02902) & (C[:, 1] < 0) & (np.abs(C[:, 0]) < 0.022)] = 'camera shroud'
        reg[z > 1.2251] = 'nose'
    elif patch == 'rocket_body':          # v4 CFD-branch geometry: boattail z -0.055..0, base disc at z=-0.055 (r 20 mm)
        reg = np.full(len(C), 'body tube', dtype=object)
        reg[(z < -0.0545) & (np.abs(S[:, 2]) > 0.9 * np.linalg.norm(S, axis=1))] = 'base'
        reg[(z >= -0.0545) & (z < 0.0005)] = 'boattail (old only)'
        reg[(z > 0.0005) & (z < 0.1405) & (r > 0.02905)] = 'fin can sleeve (body part)'
        reg[z > 1.0168] = 'nose'
    else:
        reg = np.full(len(C), patch.replace('rocket_', ''), dtype=object)
    for k in np.unique(reg):
        m = reg == k
        a = rows.setdefault(k, [0.0, 0.0]); a[0] += -Fp[m, 2].sum(); a[1] += -Fv[m, 2].sum()
    tot_p += -Fp[:, 2].sum(); tot_v += -Fv[:, 2].sum()
print(f'{"region":30s} {"pressure":>9s} {"viscous":>9s} {"total N":>9s}')
for k, (p, v) in sorted(rows.items(), key=lambda x: -sum(x[1])):
    print(f'{k:30s} {p:9.2f} {v:9.2f} {p + v:9.2f}')
print(f'{"TOTAL (drag, +aft)":30s} {tot_p:9.2f} {tot_v:9.2f} {tot_p + tot_v:9.2f}')
