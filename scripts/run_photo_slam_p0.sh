#!/usr/bin/env bash
# Phase-0 Photo-SLAM: REPEATS clean TUM fr1/desk runs, each gated on an idle GPU-1.
# Photo-SLAM maps online in a fixed real-time window, so GPU contention changes
# its accuracy/quality — every repeat waits for wait_gpu.sh first.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export CUDA_VISIBLE_DEVICES=1
export PYTHONUNBUFFERED=1
REPEATS="${REPEATS:-3}"
OUT_BASE="${OUT_BASE:-runs/photo_slam_p0_fr1_desk}"

for ((r = 0; r < REPEATS; r++)); do
  echo "$(date -Is) repeat r${r}: waiting for GPU-1"
  "$ROOT/scripts/wait_gpu.sh"
  gpu_state="$(nvidia-smi -i 1 --query-gpu=memory.free,utilization.gpu --format=csv,noheader,nounits)"
  echo "$(date -Is) starting Photo-SLAM P0 r${r} (clean fr1/desk)"
  OUT="$OUT_BASE/r${r}" GPU_STATE="$gpu_state" .venv/bin/python - <<'PY'
import json
import os
from pathlib import Path

from harness.adapters import systems
from harness.datasets.loaders import load_tum_rgbd
from harness.eval.metrics import eval_accuracy

stream = load_tum_rgbd(Path("datasets/tum/rgbd_dataset_freiburg1_desk"))
out = Path(os.environ["OUT"])
out.mkdir(parents=True, exist_ok=True)
adapter = systems.PhotoSlam()
print("image", adapter.image, "commit", adapter.commit, "needs_gpu", adapter.needs_gpu)
result = adapter.run(stream, out, timeout_s=7200)
print(result)
free_mib, util = (v.strip() for v in os.environ["GPU_STATE"].split(","))
summary = {
    "outcome": result.outcome.value,
    "error": result.error_detail,
    "gpu1_at_start": {"free_mib": int(free_mib), "util_pct": int(util)},
}
shutdown_dirs = sorted(out.glob("*_shutdown"))
if shutdown_dirs:
    d = shutdown_dirs[-1]
    summary["mapper_iterations"] = int(d.name.split("_")[0])
    vals = [float(l.split()[-1]) for l in (d / "psnr.txt").read_text().splitlines()
            if l and not l.startswith("#")]
    summary["keyframe_psnr_mean"] = sum(vals) / len(vals) if vals else None
if result.trajectory_path and stream.gt_trajectory:
    acc = eval_accuracy(result.trajectory_path, stream.gt_trajectory)
    summary.update({
        "ate_rmse": acc.ate_rmse,
        "rpe_trans": acc.rpe_trans,
        "rpe_rot": acc.rpe_rot,
        "n_valid": acc.n_valid,
    })
    print(f"ATE-RMSE={acc.ate_rmse:.4f} m")
(out / "p0_summary.json").write_text(json.dumps(summary, indent=2))
print(json.dumps(summary))
PY
done
echo "$(date -Is) all ${REPEATS} repeats done"
