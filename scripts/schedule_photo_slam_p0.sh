#!/usr/bin/env bash
# After Photo-SLAM image builds, wait for GPU-1 and run P0.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
LOG=/tmp/photo_slam_p0_schedule.log
exec > >(tee -a "$LOG") 2>&1

echo "$(date -Is) schedule: wait for docker image harness/photo_slam:x86"
while ! docker image inspect harness/photo_slam:x86 >/dev/null 2>&1; do
  if ! pgrep -f 'docker buildx build.*photo_slam' >/dev/null 2>&1; then
    if ! docker image inspect harness/photo_slam:x86 >/dev/null 2>&1; then
      echo "$(date -Is) build process gone and image missing — see /tmp/photo_slam_build.log"
      tail -80 /tmp/photo_slam_build.log || true
      exit 1
    fi
  fi
  echo "$(date -Is) still building..."
  sleep 60
done
echo "$(date -Is) image ready"

echo "$(date -Is) waiting for GPU-1"
"$ROOT/scripts/wait_gpu.sh"

echo "$(date -Is) launching P0"
"$ROOT/scripts/run_photo_slam_p0.sh"
echo "$(date -Is) schedule done"
