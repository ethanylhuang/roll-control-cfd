# Sweep findings — 9 September 2026

Full-range ordinary least squares, δ in degrees; seven shared angles −6, 3, 6, 9, 10, 12, 15. Fits include flagged source means. Moments at z=0.330 m.

| Mach | OpenFOAM roll slope (N·m/deg) | SimScale roll slope (N·m/deg) | Difference | OpenFOAM R² | SimScale R² |
|---|---:|---:|---:|---:|---:|
| 0.30 | 0.0064385 | 0.0059359 | -7.81% | 0.99266 | 0.99157 |
| 0.50 | 0.0185857 | 0.0176366 | -5.11% | 0.99475 | 0.99568 |
| 0.60 | 0.0276017 | 0.0261849 | -5.13% | 0.99595 | 0.99759 |
| 0.70 | 0.0394778 | 0.0377044 | -4.49% | 0.99728 | 0.99777 |
| 0.80 | 0.0564717 | 0.0554115 | -1.88% | 0.99847 | 0.99858 |
| 0.85 | 0.0684470 | 0.0689574 | +0.75% | 0.99890 | 0.99847 |

The roll-slope discrepancy narrows with Mach: −7.81% at M0.30 to +0.75% at M0.85. This does not mean every individual deflection agrees as closely. At M0.30, for example, SimScale roll at +6° is about 16% lower than OpenFOAM.

Yaw-coefficient slope differences range from −18.44% at M0.30 to +4.59% at M0.85, after shifting both moment reference points. Roll and yaw are broadly linear over this interval, but the slope depends on the selected interval. At M0.60 the 3°–10° yaw slope is about 8.95% higher in SimScale; the full-range yaw slope is 3.45% lower.

The axial-coefficient linear fits have much lower R² (roughly 0.37–0.73 across the paired sweep). Their fitted slopes should not be treated as a strong linear law. The dashboard flags R² below 0.95 as a weak linear model; this display threshold is a heuristic, not a convergence standard.

The roll means carry 26 source-flagged points across the 98 fine-mesh conditions. OpenFOAM raw iteration scatter and SimScale block-mean scatter are not equivalent. Default fits describe the reported mean response and do not establish physical accuracy.

M0.90 has no paired SimScale steady sweep. The OpenFOAM 15° steady extension is still flagged (6.92% drift and 14.74% raw scatter), while its later 15 ms transient diagnostic reports 1.251302 N·m with 0.144% scatter in its final window. These are different solver modes and are intentionally kept separate.

Reference constants: density 1.18915 kg/m³; area 0.0026248 m²; diameter 0.05781 m. Cl means roll coefficient, Cn yaw coefficient, and CN normal-force coefficient. Yaw is signed; adverse yaw requires a commanded-turn convention.
