#!/usr/bin/env python3
"""Run the v5 sealed-sweep recipe (run_simscale_match.py, run_q18/q19 flags) on the camera-shroud geometry
built by build_geometry.py. Isolated roots: models_v5cam / runs_v5cam. Template = case_simscale with the inlet
moved 3 background cells upstream (z 2.00 -> 2.1714, 112 -> 115 cells, same cell size) so the 158 mm longer
nose keeps the old upstream distance (0.676 m vs 0.663 m)."""
import os, sys
ROOT = '/Users/trasomi/dev/cfd'
os.chdir(ROOT)
sys.path.insert(0, ROOT)
import run_simscale_match as rsm

_load = rsm.rs.load
def load(root, config_path=None):
    cfg = _load(root, config_path)
    sfx = os.environ.get('V5CAM_VARIANT', '')          # '' = as-assembled, '_bt' = + Part Studio boattail
    cfg['roots'] = dict(cfg['roots'], models='models_v5cam' + sfx, runs='runs_v5cam' + sfx, results='results/v5cam' + sfx)
    return cfg
rsm.rs.load = load
rsm.TPL = os.path.join(ROOT, 'newgeom_cam', 'template_case_simscale')

if __name__ == '__main__':
    sys.argv = [sys.argv[0]] + sys.argv[1:]
    rsm.main()
