"""Power sampler interface + timestamped log with frame markers (plan §8).

The log carries two streams on one monotonic clock:
  - power samples  (t, watts per rail)
  - frame markers  (t, frame_index)  emitted by the feeder
so energy can be integrated over each frame/keyframe window downstream (eval/energy.py).
"""

from __future__ import annotations

import abc
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np


@dataclass
class PowerSample:
    t: float                       # monotonic seconds
    rails: dict[str, float]        # rail name -> watts (e.g. {"gpu": 42.1, "cpu": 8.0})

    @property
    def total_w(self) -> float:
        return float(sum(self.rails.values()))


@dataclass
class PowerLog:
    """Collected samples + frame markers for one run."""

    samples: list[PowerSample] = field(default_factory=list)
    markers: list[tuple[int, float]] = field(default_factory=list)  # (frame_index, t)
    source: str = "unknown"
    rails: tuple[str, ...] = ()
    idle_baseline_w: Optional[float] = None  # for dynamic-energy subtraction (plan §7)

    def mark(self, frame_index: int, t: float) -> None:
        self.markers.append((frame_index, t))

    def to_npz(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        ts = np.array([s.t for s in self.samples], dtype=np.float64)
        rail_names = list(self.rails) or (list(self.samples[0].rails) if self.samples else [])
        watts = np.array([[s.rails.get(r, np.nan) for r in rail_names] for s in self.samples],
                         dtype=np.float64)
        mi = np.array([m[0] for m in self.markers], dtype=np.int64)
        mt = np.array([m[1] for m in self.markers], dtype=np.float64)
        np.savez(path, ts=ts, watts=watts, rail_names=np.array(rail_names),
                 marker_index=mi, marker_t=mt, source=self.source,
                 idle_baseline_w=np.nan if self.idle_baseline_w is None else self.idle_baseline_w)


class PowerSampler(abc.ABC):
    """Background thread that polls a power source at a fixed rate.

    Contract: start() before the run, stop() after; the returned PowerLog shares the
    same monotonic clock (time.monotonic) as the feeder's frame markers.
    """

    source: str = "unknown"
    rails: tuple[str, ...] = ()

    def __init__(self, hz: float = 20.0) -> None:
        self.hz = hz
        self._log = PowerLog(source=self.source, rails=self.rails)
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    @abc.abstractmethod
    def _read(self) -> dict[str, float]:
        """Return current watts per rail. Called at ~self.hz."""

    def _loop(self) -> None:
        period = 1.0 / self.hz
        nxt = time.monotonic()
        while not self._stop.is_set():
            try:
                rails = self._read()
                self._log.samples.append(PowerSample(time.monotonic(), rails))
            except Exception:  # never let a bad read kill the run
                pass
            nxt += period
            slp = nxt - time.monotonic()
            if slp > 0:
                time.sleep(slp)

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> PowerLog:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        return self._log

    @property
    def log(self) -> PowerLog:
        return self._log
