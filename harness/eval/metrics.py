"""Accuracy (pose) + quality (render) metrics (plan §7).

Pose metrics are cross-family fair (ATE/RPE via evo). Quality metrics apply ONLY to
rendering systems (GS/GFM) and are reported separately — never mixed into the pose
ranking (plan §7).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class AccuracyMetrics:
    ate_rmse: float
    rpe_trans: float
    rpe_rot: float
    lost_track_rate: float
    n_frames: int
    n_valid: int


@dataclass
class QualityMetrics:
    psnr: float
    ssim: float
    lpips: float
    recon_error: Optional[float] = None


def _count_tum_poses(path: Path) -> int:
    n = 0
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        n += 1
    return n


def eval_accuracy(est_tum: Path, gt_tum: Path, *, align: bool = True) -> AccuracyMetrics:
    """ATE-RMSE + RPE via `evo`."""
    try:
        from evo.core import sync
        from evo.core.metrics import APE, PoseRelation, RPE, Unit
        from evo.tools import file_interface
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("evo required for eval_accuracy; pip install -e '.[rig]'") from e

    traj_ref = file_interface.read_tum_trajectory_file(str(gt_tum))
    traj_est = file_interface.read_tum_trajectory_file(str(est_tum))
    traj_ref, traj_est = sync.associate_trajectories(traj_ref, traj_est, max_diff=0.02)
    if align:
        traj_est.align(traj_ref, correct_scale=False)

    ape = APE(PoseRelation.translation_part)
    ape.process_data((traj_ref, traj_est))
    ape_stats = ape.get_all_statistics()

    rpe_trans = float("nan")
    rpe_rot = float("nan")
    try:
        rpe = RPE(PoseRelation.translation_part, delta=1.0, delta_unit=Unit.frames)
        rpe.process_data((traj_ref, traj_est))
        rpe_trans = float(rpe.get_all_statistics()["rmse"])
    except Exception:
        pass
    try:
        rpe_r = RPE(PoseRelation.rotation_angle_deg, delta=1.0, delta_unit=Unit.frames)
        rpe_r.process_data((traj_ref, traj_est))
        rpe_rot = float(rpe_r.get_all_statistics()["rmse"])
    except Exception:
        pass

    n_est = _count_tum_poses(est_tum)
    n_gt = _count_tum_poses(gt_tum)
    n_valid = int(traj_est.num_poses)
    # lost-track vs estimated poses that failed association, not vs denser GT rate
    lost = 1.0 - (n_valid / n_est) if n_est > 0 else 1.0

    return AccuracyMetrics(
        ate_rmse=float(ape_stats["rmse"]),
        rpe_trans=rpe_trans,
        rpe_rot=rpe_rot,
        lost_track_rate=float(max(0.0, min(1.0, lost))),
        n_frames=n_est,
        n_valid=n_valid,
    )


def eval_quality(renders_dir: Path, gt_views_dir: Path) -> QualityMetrics:
    raise NotImplementedError("quality metric wiring TODO (plan §7)")
