"""Thermal / sustained-load parse (plan §7, §8). Jetson-oriented — stub on the rig.

Parses temperature + throttle events from tegrastats/jtop logs; derives peak temps,
throttle-event count, and a sustained-vs-burst performance decay curve.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ThermalMetrics:
    peak_temp_c: float
    throttle_events: int
    steady_state_reached: bool
    decay_curve: list[float] = field(default_factory=list)  # throughput over time


def parse_thermal(log_path: Path) -> ThermalMetrics:
    """TODO(jetson): parse tegrastats thermal columns + throttle flags (plan §8)."""
    raise NotImplementedError("thermal parse TODO — needs Jetson logs (plan §14.1)")
