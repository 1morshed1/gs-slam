"""Energy integration from a PowerLog + frame markers (plan §7 headline axis).

This is real and backend-agnostic: it integrates whatever watts the sampler produced
(nvidia-smi on the rig now; tegrastats/external later) over per-frame windows defined by
the feeder's frame markers. Trapezoidal integration on the shared monotonic clock.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from ..power.base import PowerLog


@dataclass
class EnergyMetrics:
    joules_total: float
    joules_per_frame: float
    joules_per_keyframe: Optional[float]
    avg_power_w: float
    dynamic_joules: Optional[float]        # total - idle baseline (plan §7)
    edp: float                              # energy-delay product = joules * seconds
    n_frames: int


def _integrate(ts: np.ndarray, watts: np.ndarray, t0: float, t1: float) -> float:
    """Trapezoidal ∫ power dt over [t0, t1] with interpolation at the window edges."""
    if len(ts) < 2:
        return 0.0
    grid = np.clip(np.array([t0, t1]), ts[0], ts[-1])
    edge_w = np.interp(grid, ts, watts)
    mask = (ts > t0) & (ts < t1)
    xs = np.concatenate(([grid[0]], ts[mask], [grid[1]]))
    ys = np.concatenate(([edge_w[0]], watts[mask], [edge_w[1]]))
    return float(np.trapezoid(ys, xs) if hasattr(np, "trapezoid") else np.trapz(ys, xs))


def integrate_energy(
    log: PowerLog,
    keyframe_indices: Optional[list[int]] = None,
    duration_s: Optional[float] = None,
) -> EnergyMetrics:
    """Compute energy metrics from a power log + its frame markers.

    Per-frame energy = integral of total power between consecutive frame markers.
    """
    if len(log.samples) < 2:
        raise ValueError("need >=2 power samples to integrate")
    ts = np.array([s.t for s in log.samples], dtype=np.float64)
    watts = np.array([s.total_w for s in log.samples], dtype=np.float64)

    markers = sorted(log.markers, key=lambda m: m[1])
    per_frame_j: list[float] = []
    kf = set(keyframe_indices or [])
    per_kf_j: list[float] = []
    for (idx_a, t_a), (idx_b, t_b) in zip(markers, markers[1:]):
        e = _integrate(ts, watts, t_a, t_b)
        per_frame_j.append(e)
        if idx_a in kf:
            per_kf_j.append(e)

    span = (duration_s if duration_s is not None
            else (markers[-1][1] - markers[0][1]) if len(markers) >= 2
            else ts[-1] - ts[0])
    total_j = _integrate(ts, watts, ts[0], ts[-1])
    avg_w = total_j / span if span > 0 else 0.0

    dyn = None
    if log.idle_baseline_w is not None:
        dyn = total_j - log.idle_baseline_w * span

    return EnergyMetrics(
        joules_total=total_j,
        joules_per_frame=float(np.mean(per_frame_j)) if per_frame_j else 0.0,
        joules_per_keyframe=float(np.mean(per_kf_j)) if per_kf_j else None,
        avg_power_w=avg_w,
        dynamic_joules=dyn,
        edp=total_j * span,
        n_frames=len(per_frame_j),
    )
