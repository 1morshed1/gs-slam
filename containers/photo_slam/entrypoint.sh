#!/usr/bin/env bash
# Photo-SLAM TUM RGB-D entrypoint (no_viewer). Writes CameraTrajectory_TUM.txt under /out.
set -euo pipefail

DATA=/data
OUT=/out
ROOT=/opt/Photo-SLAM

while [[ $# -gt 0 ]]; do
  case "$1" in
    --data) DATA="$2"; shift 2 ;;
    --out)  OUT="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

mkdir -p "$OUT"
cd "$OUT"

ASSOC="${DATA}/associations.txt"
# Prefer Photo-SLAM bundled fr1/desk associations when present (paper script).
BUNDLED="${ROOT}/cfg/ORB_SLAM3/RGB-D/TUM/associations/tum_freiburg1_desk.txt"
if [[ -f "$BUNDLED" ]]; then
  ASSOC="$BUNDLED"
fi

VOCAB="${ROOT}/ORB-SLAM3/Vocabulary/ORBvoc.txt"
ORB_CFG="${ROOT}/cfg/ORB_SLAM3/RGB-D/TUM/tum_freiburg1_desk.yaml"
GS_CFG="${ROOT}/cfg/gaussian_mapper/RGB-D/TUM/tum_rgbd.yaml"
BIN="${ROOT}/bin/tum_rgbd"

"$BIN" "$VOCAB" "$ORB_CFG" "$GS_CFG" "$DATA" "$ASSOC" "$OUT" no_viewer \
  | tee "$OUT/photo_slam.log"

# Canonical name for harness eval
if [[ -f "$OUT/CameraTrajectory_TUM.txt" ]]; then
  cp -f "$OUT/CameraTrajectory_TUM.txt" "$OUT/CameraTrajectory.txt"
fi

if [[ ! -s "$OUT/CameraTrajectory.txt" ]]; then
  echo "Photo-SLAM did not write a TUM trajectory" >&2
  exit 1
fi

wc -l "$OUT/CameraTrajectory.txt"
