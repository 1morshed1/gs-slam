"""Per-system I/O adapters. FrameStream in → TUM trajectory (+ optional map) out."""

from .base import SLAMAdapter, AdapterResult, RunOutcome

__all__ = ["SLAMAdapter", "AdapterResult", "RunOutcome"]
