#!/usr/bin/env bash
# Save a recorded run as the scenario's demo, for the repo and README.
#
# Usage:
#   scripts/keep_demo.sh <scenario> [timestamp]
#     scenario   name under results/, e.g. perpendicular_hallways
#     timestamp  which run (folder under results/<scenario>/); default: newest
#
# Writes:
#   demos/<scenario>.mp4  compressed full video (tracked with Git LFS)
#   demos/<scenario>.gif  short, small preview that GitHub plays inline in the README (regular git)
#
# Env overrides: GIF_START (s, default 0), GIF_SECONDS (default 15), GIF_WIDTH (px, default 360),
#                GIF_FPS (default 10), CRF (mp4 quality, higher = smaller, default 30)
#
# Run it on the machine you commit from (needs ffmpeg). Copy results/ over first if the run
# happened on another PC, e.g.: rsync -av <user>@<host>:<repo>/results/ results/
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
scenario="${1:-}"
stamp="${2:-}"
if [[ -z "$scenario" ]]; then
  echo "usage: $0 <scenario> [timestamp]" >&2
  echo "scenarios with results:" >&2
  ls "$repo_root/results" >&2 2>/dev/null || echo "  (none - results/ is empty)" >&2
  exit 1
fi
command -v ffmpeg >/dev/null || { echo "ffmpeg not found" >&2; exit 1; }

runs_dir="$repo_root/results/$scenario"
if [[ -z "$stamp" ]]; then
  stamp="$(ls "$runs_dir" 2>/dev/null | sort | tail -n 1)"
fi
src="$runs_dir/$stamp/demo.mp4"
[[ -n "$stamp" && -f "$src" ]] || { echo "no recording found at $src" >&2; exit 1; }

out_dir="$repo_root/demos"
mkdir -p "$out_dir"
mp4="$out_dir/$scenario.mp4"
gif="$out_dir/$scenario.gif"

echo "source: $src"

ffmpeg -loglevel error -y -i "$src" \
  -c:v libx264 -crf "${CRF:-30}" -preset slow -pix_fmt yuv420p -movflags +faststart \
  "$mp4"

ffmpeg -loglevel error -y -ss "${GIF_START:-0}" -t "${GIF_SECONDS:-15}" -i "$src" \
  -vf "fps=${GIF_FPS:-10},scale=${GIF_WIDTH:-360}:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer" \
  -loop 0 "$gif"

size() { du -h "$1" | cut -f1; }
echo "wrote $mp4 ($(size "$mp4"))"
echo "wrote $gif ($(size "$gif"))"
echo
echo "README snippet:"
echo "  ![$scenario](demos/$scenario.gif)"
echo "  [full video](demos/$scenario.mp4)"
echo
echo "then: git add demos/$scenario.mp4 demos/$scenario.gif && git commit"
