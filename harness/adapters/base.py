"""The adapter contract — the single interface every SLAM system is wrapped behind.

This is what keeps cross-family comparison fair (plan §10): eval only ever sees a
TUM-format trajectory + declared map artifacts, never a system's internals. Adapters
declare required modality and whether they render (GS/GFM → PSNR/SSIM/LPIPS eligible).

Crash / timeout / lost-track are first-class outcomes, not exceptions to swallow
(plan §10, §7): they are recorded as results.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from ..datasets.frame import FrameStream, Modality


class RunOutcome(str, Enum):
    OK = "ok"
    LOST_TRACK = "lost_track"       # tracker reported failure / ATE spike
    TIMEOUT = "timeout"
    CRASH = "crash"
    OOM = "oom"
    INFEASIBLE = "infeasible"       # e.g. GFM on constrained edge — a *finding* (plan R2)


@dataclass
class AdapterResult:
    """What every run produces, regardless of system/family."""

    outcome: RunOutcome
    trajectory_path: Optional[Path]     # TUM format: "ts tx ty tz qx qy qz qw" per line
    map_path: Optional[Path] = None     # optional: point cloud / gaussians / pointmap
    renders_dir: Optional[Path] = None  # optional: held-out-view renders for PSNR/SSIM/LPIPS
    # Per-frame timing collected by the adapter (tracking vs mapping breakdown, plan §7).
    per_frame_ms: list[float] = field(default_factory=list)
    tracking_ms: list[float] = field(default_factory=list)
    mapping_ms: list[float] = field(default_factory=list)
    keyframe_indices: list[int] = field(default_factory=list)
    peak_host_ram_mb: Optional[float] = None
    peak_vram_mb: Optional[float] = None
    error_detail: str = ""


class SLAMAdapter(abc.ABC):
    """Wraps one SLAM system behind a uniform run() call.

    Subclasses live in `containers/<system>/adapter.py` or here for pure-python ones,
    and are registered in `REGISTRY`. Heavy systems run inside their own container and
    this class shells out to it; the trajectory comes back over a mounted volume.
    """

    #: unique key, e.g. "orb_slam3", "photo_slam", "mast3r_slam"
    name: str = "unnamed"
    #: one of the three families for grouping (plan §3)
    family: str = "classical"  # "classical" | "gs" | "gfm"
    #: exact commit pinned in the run manifest (plan §3.4, §10)
    commit: str = "UNPINNED"
    #: modality this adapter needs from the stream (legacy single-modality)
    required_modality: Modality = Modality.MONO
    #: if set, any of these modalities on the stream is enough (plan §9.4)
    supported_modalities: Optional[frozenset[Modality]] = None
    #: True for GS/GFM systems that produce renderable maps
    renders: bool = False

    @abc.abstractmethod
    def run(self, stream: FrameStream, out_dir: Path, *, timeout_s: float) -> AdapterResult:
        """Process the whole stream, write a TUM trajectory into out_dir, return result.

        Contract:
          - MUST NOT corrupt/preprocess frames beyond the system's own pipeline
            (corruptions are pre-applied to the stream on disk).
          - MUST return an AdapterResult even on failure (set outcome accordingly).
          - SHOULD populate per-frame timing so eval can split tracking vs mapping.
        """

    def can_run(self, stream: FrameStream) -> bool:
        """Skip modality-incompatible cells cleanly (plan §9.4)."""
        needed = self.supported_modalities
        if needed is None:
            needed = frozenset({self.required_modality})
        return bool(needed & stream.modalities)


# system name -> adapter class. Populated by concrete adapter modules on import.
REGISTRY: dict[str, type[SLAMAdapter]] = {}


def register(cls: type[SLAMAdapter]) -> type[SLAMAdapter]:
    REGISTRY[cls.name] = cls
    return cls
