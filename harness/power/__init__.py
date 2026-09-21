"""Out-of-process power sampling with frame-boundary markers (plan §8).

Sampler backends are pluggable so the Jetson gear decision (deferred) doesn't block
the rig build:
  - NvidiaSmiSampler  : office rig, GPU-only, coarse relative context (NOT edge energy)
  - TegrastatsSampler : Jetson INA3221 module rails            [TODO — needs hardware]
  - ExternalMeterSampler : Monsoon / INA226 / bench analyzer   [TODO — needs gear choice]
"""

from .base import PowerSampler, PowerSample, PowerLog
from .backends import NvidiaSmiSampler

__all__ = ["PowerSampler", "PowerSample", "PowerLog", "NvidiaSmiSampler"]
