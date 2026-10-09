#!/usr/bin/env bash
# Build the whole take-home: generate Before (4 bolts) and After (6 bolts),
# render screenshots, and package takehome.zip in the required layout.
#
# Requires: FreeCAD 1.1.x installed (FreeCADCmd), python3 with numpy+matplotlib.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
TH="$ROOT/takehome"

# locate FreeCADCmd
FCCMD="${FREECADCMD:-}"
if [ -z "$FCCMD" ]; then
  for c in \
    /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd \
    /Applications/FreeCAD.app/Contents/MacOS/FreeCADCmd \
    "$(command -v freecadcmd || true)"; do
    if [ -n "$c" ] && [ -x "$c" ]; then FCCMD="$c"; break; fi
  done
fi
if [ -z "$FCCMD" ]; then
  echo "ERROR: FreeCADCmd not found. Set FREECADCMD=/path/to/freecadcmd" >&2
  exit 1
fi
echo "Using FreeCADCmd: $FCCMD"

# 1) Before = 4 bolts, After = 6 bolts
"$FCCMD" "$HERE/build_coupling.py" -- 4 "$TH/Before" input
"$FCCMD" "$HERE/build_coupling.py" -- 6 "$TH/After"  solution

# 2) screenshots
python3 "$HERE/render_png.py" "$TH/Before/input.obj" "$TH/Before/input.png" \
  "BEFORE - flange coupling, 4 bolts"
python3 "$HERE/render_png.py" "$TH/After/solution.obj" "$TH/After/solution.png" \
  "AFTER - flange coupling, 6 bolts"

# 3) keep Defective/ present but empty
touch "$TH/Defective/.gitkeep"

# 4) clean intermediates (FreeCAD backups + render meshes)
find "$TH" \( -name '*.FCBak' -o -name '*.FCStd1' -o -name '*.obj' \) -delete

# 5) zip the deliverable
cd "$ROOT"
rm -f takehome.zip
( cd "$ROOT" && zip -r takehome.zip takehome -x '*/.gitkeep' >/dev/null )
echo "Built $ROOT/takehome.zip"
