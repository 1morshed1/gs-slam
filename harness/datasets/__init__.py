"""Dataset loaders + fixed-rate frame feeder (plan §5, §10)."""

from .frame import Frame, FrameStream, Modality
from .feeder import FixedRateFeeder
from .loaders import LOADERS, load_sequence

__all__ = [
    "Frame",
    "FrameStream",
    "Modality",
    "FixedRateFeeder",
    "LOADERS",
    "load_sequence",
]
