"""Concrete adapter stubs, one per system-under-test (plan §3).

Each is a thin registration + metadata now; run() shells out to the system's container
(built under containers/<name>/). Fill run() during Phase 0 bring-up. Keeping them here
as declared stubs lets the orchestrator build/validate the experiment matrix before any
system actually runs.
"""

from __future__ import annotations

from pathlib import Path

from ..datasets.frame import FrameStream, Modality
from .base import AdapterResult, RunOutcome, SLAMAdapter, register


class _ContainerAdapter(SLAMAdapter):
    """Base for systems that execute inside their own Docker image.

    TODO(P0): implement _invoke() — mount stream dir + out_dir, run the pinned image,
    parse stdout/exit-code into RunOutcome, read back TUM trajectory. Shared so every
    system inherits identical crash/timeout/lost-track handling.
    """

    image: str = ""

    def run(self, stream: FrameStream, out_dir: Path, *, timeout_s: float) -> AdapterResult:
        raise NotImplementedError(
            f"{self.name}: container adapter not built yet (image={self.image!r}). "
            "See containers/{name}/ and plan §11 Phase 0."
        )


# --- Classical --------------------------------------------------------------
@register
class OrbSlam3(_ContainerAdapter):
    name = "orb_slam3"
    family = "classical"
    required_modality = Modality.MONO  # supports mono/stereo/rgbd/VI; set per-cell
    renders = False
    image = "harness/orb_slam3:x86"


@register
class OpenVins(_ContainerAdapter):
    name = "openvins"
    family = "classical"
    required_modality = Modality.VI
    renders = False
    image = "harness/openvins:x86"


# --- GS-SLAM ----------------------------------------------------------------
@register
class PhotoSlam(_ContainerAdapter):
    name = "photo_slam"
    family = "gs"
    required_modality = Modality.RGBD  # also mono/stereo
    renders = True
    image = "harness/photo_slam:x86"


@register
class GsIcpSlam(_ContainerAdapter):
    name = "gs_icp_slam"
    family = "gs"
    required_modality = Modality.RGBD
    renders = True
    image = "harness/gs_icp_slam:x86"


@register
class MonoGS(_ContainerAdapter):
    name = "monogs"
    family = "gs"
    required_modality = Modality.MONO
    renders = True
    image = "harness/monogs:x86"


@register
class SplaTAM(_ContainerAdapter):
    """Known-slow — included as quality/energy ceiling (plan §3.3)."""
    name = "splatam"
    family = "gs"
    required_modality = Modality.RGBD
    renders = True
    image = "harness/splatam:x86"


# --- GFM-SLAM ---------------------------------------------------------------
@register
class Mast3rSlam(_ContainerAdapter):
    name = "mast3r_slam"
    family = "gfm"
    required_modality = Modality.MONO  # calib-free
    renders = True
    image = "harness/mast3r_slam:x86"


@register
class VggtSlam(_ContainerAdapter):
    """Stretch target (plan §3)."""
    name = "vggt_slam"
    family = "gfm"
    required_modality = Modality.MONO
    renders = True
    image = "harness/vggt_slam:x86"
