#!/bin/zsh
# anim_still.sh <case_dir> [tag]: sample the animation planes on a finished steady case (latest time) and render one 6-panel still
# into results/anim/<tag>_<case>_still.png (postProcess -dict, no solver). Uses pipeline/animFO and anim_render.py.
cd /Users/trasomi/dev/cfd; C=${1%/}; name=$(basename $C); tag=$(basename $(dirname $C))
grep -v MachNoAnim pipeline/animFO > $C/system/animFO;   # MachNoAnim needs the solver thermo; in postProcess it fails and unregisters the Ma loaded from disk awk '/^functions/{exit} {print}' $C/system/controlDict > $C/system/animStillDict; printf 'functions\n{\n    #include "animFO"\n}\n' >> $C/system/animStillDict
rm -rf $C/postProcessing/animSlices $C/postProcessing/animRocket $C/postProcessing/animQ
/Applications/OpenFOAM-v2606.app/Contents/Resources/etc/openfoam -c "cd $C && postProcess -dict system/animStillDict -latestTime -fields '(p U rho T Ma)'" > $C/log.animStill 2>&1 || { echo "postProcess failed (see $C/log.animStill)"; exit 1; }
./venv/bin/python anim_render.py $C --times last --no-video && cp $C/anim/frames/frame_0000.png results/anim/${tag}_${name}_still.png && echo "still: results/anim/${tag}_${name}_still.png"
