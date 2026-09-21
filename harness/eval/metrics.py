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
    lost_track_rate: float          # fraction of frames with no valid pose (plan §7)
    n_frames: int
    n_valid: int


@dataclass
class QualityMetrics:
    psnr: float
    ssim: float
    lpips: float
    recon_error: Optional[float] = None   # vs GT mesh where available (Replica)


def eval_accuracy(est_tum: Path, gt_tum: Path, *, align: bool = True) -> AccuracyMetrics:
    """ATE-RMSE + RPE via `evo`. Uses Sim(3)/SE(3) alignment per modality.

    TODO(rig): call evo_ape / evo_rpe (import evo.core, or shell out to evo_ape tum).
    Interface fixed; wiring is Phase 2. Depends only on trajectories, so runs on the rig.
    """
    raise NotImplementedError("evo wiring TODO (plan §7); interface is stable")


def eval_quality(renders_dir: Path, gt_views_dir: Path) -> QualityMetrics:
    """PSNR/SSIM/LPIPS on held-out views. Rendering systems only.

    TODO(rig): torchmetrics or lpips + skimage. Runs on the office rig (reference tier).
    """
    raise NotImplementedError("quality metric wiring TODO (plan §7)")
