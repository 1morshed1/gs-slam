#!/usr/bin/env bash
# Container entrypoint: run ORB-SLAM3 RGB-D on a mounted TUM sequence → TUM traj in /out.
set -euo pipefail

DATA=/data
OUT=/out
VOCAB=/opt/ORB_SLAM3/Vocabulary/ORBvoc.txt
SETTINGS=/opt/ORB_SLAM3/Examples/RGB-D/TUM1.yaml
BIN=/opt/ORB_SLAM3/Examples/RGB-D/rgbd_tum

while [[ $# -gt 0 ]]; do
  case "$1" in
    --data) DATA="$2"; shift 2 ;;
    --out)  OUT="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

mkdir -p "$OUT"
cd "$OUT"

ASSOC="$DATA/associations.txt"
if [[ ! -f "$ASSOC" ]]; then
  echo "missing associations.txt under $DATA" >&2
  exit 1
fi

# Prefer ORB-SLAM3's bundled association if filenames match; otherwise use dataset's.
"$BIN" "$VOCAB" "$SETTINGS" "$DATA" "$ASSOC" | tee "$OUT/orb_slam3.log"

# ORB-SLAM3 writes CameraTrajectory.txt / KeyFrameTrajectory.txt into CWD.
if [[ ! -f "$OUT/CameraTrajectory.txt" ]]; then
  echo "ORB-SLAM3 did not write CameraTrajectory.txt" >&2
  exit 1
fi

# Drop comment lines if any; keep TUM rows.
grep -E '^[0-9]' "$OUT/CameraTrajectory.txt" > "$OUT/CameraTrajectory.clean.txt" || true
if [[ -s "$OUT/CameraTrajectory.clean.txt" ]]; then
  mv "$OUT/CameraTrajectory.clean.txt" "$OUT/CameraTrajectory.txt"
fi

wc -l "$OUT/CameraTrajectory.txt"
