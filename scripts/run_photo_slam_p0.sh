#!/usr/bin/env bash
# Phase-0 Photo-SLAM: one clean TUM fr1/desk run.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export CUDA_VISIBLE_DEVICES=1
export PYTHONUNBUFFERED=1

echo "$(date -Is) starting Photo-SLAM P0 (clean fr1/desk)"
.venv/bin/python - <<'PY'
from pathlib import Path
from harness.adapters import systems
from harness.datasets.loaders import load_tum_rgbd
from harness.eval.metrics import eval_accuracy
import json

stream = load_tum_rgbd(Path("datasets/tum/rgbd_dataset_freiburg1_desk"))
out = Path("runs/photo_slam_p0_fr1_desk")
out.mkdir(parents=True, exist_ok=True)
adapter = systems.PhotoSlam()
print("image", adapter.image, "commit", adapter.commit, "needs_gpu", adapter.needs_gpu)
result = adapter.run(stream, out, timeout_s=7200)
print(result)
summary = {"outcome": result.outcome.value, "error": result.error_detail}
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
print("wrote", out / "p0_summary.json")
PY
