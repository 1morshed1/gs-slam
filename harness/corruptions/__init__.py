"""Parameterized perturbation suite (plan §6). Pre-generated to disk, deterministic seeds."""

from .base import Corruption, CORRUPTIONS, register, severity_control
from . import generators  # noqa: F401  (populates CORRUPTIONS via @register)

__all__ = ["Corruption", "CORRUPTIONS", "register", "severity_control"]
