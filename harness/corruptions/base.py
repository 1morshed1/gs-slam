"""Corruption interface, ImageNet-C style (plan §6).

Every corruption:
  - has severity in {1..5} with documented parameter ranges (severity 0 = clean control),
  - is deterministic given (image, severity, seed) so sequences reproduce exactly,
  - is applied ONCE, pre-generated to disk — never inside the measured loop.

A corruption operates on a single uint8 RGB frame. Photometric corruptions assume
sRGB input; if a sensor linearization step is added it must run before photometric ops
and be documented (plan §6 design rule).
"""

from __future__ import annotations

import abc
import numpy as np

SEVERITIES = (1, 2, 3, 4, 5)


def severity_control() -> int:
    """The uncorrupted control level."""
    return 0


class Corruption(abc.ABC):
    """Base for one perturbation type."""

    #: kebab key, e.g. "motion-blur"
    name: str = "unnamed"

    @abc.abstractmethod
    def apply(self, image: np.ndarray, severity: int, rng: np.random.Generator) -> np.ndarray:
        """Return a corrupted copy. severity in {1..5}; caller handles severity 0 (passthrough).

        Must be pure w.r.t. `rng` — all randomness draws from it so seeding is reproducible.
        """

    def params(self, severity: int) -> dict:
        """Document the exact parameters used at this severity (goes into the manifest)."""
        return {}


CORRUPTIONS: dict[str, Corruption] = {}


def register(cls: type[Corruption]) -> type[Corruption]:
    CORRUPTIONS[cls.name] = cls()
    return cls
