"""Fixed-rate frame feeder with power-log frame markers (plan §8)."""

from __future__ import annotations

import time
from typing import Callable, Iterator, Optional

from .frame import Frame, FrameStream

MarkerFn = Callable[[int, float], None]


class FixedRateFeeder:
    """Iterate a FrameStream at a target fps, emitting markers on a monotonic clock.

    Adapters that consume frames in-process can iterate this feeder. Container adapters
    typically mount `stream.root` and ignore pacing; markers still fire if the host
    walks the feeder, or the adapter can mark boundaries itself.
    """

    def __init__(
        self,
        stream: FrameStream,
        *,
        target_fps: Optional[float] = None,
        on_marker: Optional[MarkerFn] = None,
        realtime: bool = False,
    ) -> None:
        self.stream = stream
        self.target_fps = float(target_fps if target_fps is not None else stream.fps)
        self.on_marker = on_marker
        self.realtime = realtime

    def __len__(self) -> int:
        return len(self.stream)

    def __iter__(self) -> Iterator[Frame]:
        period = 1.0 / self.target_fps if self.target_fps > 0 else 0.0
        t0 = time.monotonic()
        for frame in self.stream:
            t = time.monotonic()
            if self.on_marker is not None:
                self.on_marker(frame.index, t)
            yield frame
            if self.realtime and period > 0:
                due = t0 + (frame.index + 1) * period
                slp = due - time.monotonic()
                if slp > 0:
                    time.sleep(slp)

    @property
    def root(self):
        return self.stream.root

    @property
    def fps(self) -> float:
        return self.target_fps
