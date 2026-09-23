"""Frame / FrameStream contracts — the I/O surface every adapter sees."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterator, Optional, Sequence


class Modality(str, Enum):
    MONO = "mono"
    STEREO = "stereo"
    RGBD = "rgbd"
    VI = "vi"


@dataclass(frozen=True)
class Frame:
    """One timestamped observation. Paths are preferred over in-memory pixels."""

    index: int
    timestamp: float
    rgb_path: Path
    depth_path: Optional[Path] = None
    right_path: Optional[Path] = None
    # Optional IMU samples belonging to this frame window (sensor-specific).
    imu: Optional[object] = None


@dataclass
class FrameStream:
    """Path-backed sequence shared by adapters, feeders, and eval."""

    dataset: str
    sequence: str
    root: Path
    frames: list[Frame]
    modalities: frozenset[Modality]
    fps: float = 30.0
    gt_trajectory: Optional[Path] = None  # TUM format when available
    calibration: dict = field(default_factory=dict)
    # Opaque extras (e.g. associations path) for container adapters.
    meta: dict = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.frames)

    def __iter__(self) -> Iterator[Frame]:
        return iter(self.frames)

    @property
    def primary_modality(self) -> Modality:
        # Prefer richest available modality for can_run checks.
        order = (Modality.VI, Modality.RGBD, Modality.STEREO, Modality.MONO)
        for m in order:
            if m in self.modalities:
                return m
        return Modality.MONO
