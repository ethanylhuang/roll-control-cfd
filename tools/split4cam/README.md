# split4cam — preview RunCam Split 4 footage from your CAD

Renders the frame a RunCam Split 4 V3 (stock lens, 4K 16:9) would record from a camera on the rocket:
airframe, fins and fairings from your exported geometry, flat ground (procedural desert or your own aerial
image), sky, and simple sun shading with shadows.

- **Lens:** measured Gyroflow calibration of the Split 4 (OpenCV fisheye model, `lens/`). Gives 112° × 75°
  horizontal × vertical, the ~1.1x horizontal squeeze of the 16:9 recording, and real barrel distortion.
  The calibration polynomial folds over past ~66° off-axis, so the extreme corners are extrapolated linearly.
- **Renderer:** Open3D ray casting (Embree). 4K frame in a few seconds.

## Run
```bash
cd ~/dev/cfd/tools/split4cam
.venv/bin/python split4cam.py --demo --lens-height 5 --tilt 7          # built-in aero-control rocket
.venv/bin/python split4cam.py example.toml                            # your Onshape export
.venv/bin/python split4cam.py example.toml --width 1920 --supersample 2 --altitude 1500 --out high.png
```
Prints the share of the frame covered by the rocket.

## Exporting from Onshape
1. In the Assembly (or the Part Studio with the tube, fin can, shroud…), right-click parts → **Export** →
   **STL**, units **millimeter**, resolution **fine**. Export each colour group as its own file (airframe, fin can,
   shroud), all in the same origin (don't tick "export in part's own coordinates").
2. Put them in `export/` and list them as `[[mesh]]` entries in the config.
3. Camera pose: in Onshape use **Measure** on the lens-face centre (a sketch point or mate connector there) to read its
   X/Y/Z → `camera.position`. For the direction, either `look` (lens face centre − barrel back centre) + `up`
   (outward radial), or `radial` + `tilt_deg` (camera looks aft, tilted outward). Leave the stand-in camera part
   *out* of the export or it will block the view.
4. `rocket.axis` = the nose direction in the model frame.

## Notes / limits
- Flat ground, no plume/smoke, no motion blur, no rolling shutter. Good for framing and "how much airframe is in shot".
- The demo geometry is the `aero-control.ork` rocket (2.1 in tube, VK nose, 4 freeform fins), camera at 45° between fins.
