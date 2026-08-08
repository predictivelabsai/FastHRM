#!/usr/bin/env bash
# Build the animated demo GIF from per-screen PNG frames.
#
# Capture the guide screenshots and curated frame set first, then run this script:
#
#   DEMO_BASE_URL=http://localhost:5010 .venv/bin/python \
#     scripts/capture_guide_screenshots.py --demo-frames docs/demo/frames
#   bash scripts/build_demo_gif.sh
#
# Output: docs/demo/fasthr-walkthrough.gif  (1 frame ≈ 1.6s, looping)
#
# Generic across the fasthtml-oss-migrations repos — only the output name and
# paths differ. Uses ImageMagick `convert`; falls back to ffmpeg if present.
set -euo pipefail
cd "$(dirname "$0")/.."

FRAMES_DIR="docs/demo/frames"
OUT="docs/demo/fasthr-walkthrough.gif"
DELAY="${DELAY:-160}"        # hundredths of a second between frames
WIDTH="${WIDTH:-1100}"       # downscale width for a smaller GIF

if ! ls "$FRAMES_DIR"/*.png >/dev/null 2>&1; then
  echo "No frames in $FRAMES_DIR/. Capture screenshots there first." >&2
  exit 1
fi

mkdir -p "$(dirname "$OUT")"

if command -v convert >/dev/null 2>&1; then
  convert -loop 0 -delay "$DELAY" \
    -resize "${WIDTH}x" \
    "$FRAMES_DIR"/*.png \
    -layers Optimize "$OUT"
elif command -v ffmpeg >/dev/null 2>&1; then
  ffmpeg -y -framerate "$(awk "BEGIN{print 100/$DELAY}")" \
    -pattern_type glob -i "$FRAMES_DIR/*.png" \
    -vf "scale=${WIDTH}:-1:flags=lanczos" "$OUT"
else
  echo "Need ImageMagick (convert) or ffmpeg installed." >&2
  exit 1
fi

echo "Wrote $OUT ($(du -h "$OUT" | cut -f1))"

# The landing page serves its tour from static/, which the docs/ copy is not
# reachable from. Publish both from the same build so they cannot drift — that
# is exactly how the landing page ended up a release behind before.
LANDING="static/product-demo.gif"
cp "$OUT" "$LANDING"
echo "Wrote $LANDING (landing-page product tour)"
