"""Concrete adapter stubs, one per system-under-test (plan §3).

Each is a thin registration + metadata now; run() shells out to the system's container
(built under containers/<name>/). Fill run() during Phase 0 bring-up. Keeping them here
as declared stubs lets the orchestrator build/validate the experiment matrix before any
system actually runs.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path

from ..datasets.feeder import FixedRateFeeder
from ..datasets.frame import FrameStream, Modality
from .base import AdapterResult, RunOutcome, SLAMAdapter, register


class _ContainerAdapter(SLAMAdapter):
    """Base for systems that execute inside their own Docker image.

    `_invoke()` mounts stream dir + out_dir, runs the pinned image, and maps
    exit codes into RunOutcome. Shared crash/timeout/lost-track handling.
    """

    image: str = ""
    #: relative path of the TUM trajectory written by the container entrypoint
    traj_name: str = "trajectory.txt"
    #: classical ORB does not need a GPU; GS/GFM images will set True
    needs_gpu: bool = False

    def run(self, stream: FrameStream, out_dir: Path, *, timeout_s: float) -> AdapterResult:
        # Accept FixedRateFeeder or FrameStream — orchestrator may pass either.
        if isinstance(stream, FixedRateFeeder):
            root = stream.stream.root
            fps = stream.fps
            n_frames = len(stream.stream)
            on_marker = stream.on_marker
            inner = stream.stream
        else:
            root = stream.root
            fps = stream.fps
            n_frames = len(stream)
            on_marker = None
            inner = stream

        out_dir.mkdir(parents=True, exist_ok=True)
        return self._invoke(inner, root, out_dir, timeout_s=timeout_s,
                            fps=fps, n_frames=n_frames, on_marker=on_marker)

    def _invoke(
        self,
        stream: FrameStream,
        data_root: Path,
        out_dir: Path,
        *,
        timeout_s: float,
        fps: float,
        n_frames: int,
        on_marker,
    ) -> AdapterResult:
        meta_path = out_dir / "stream_meta.json"
        meta_path.write_text(json.dumps({
            "dataset": stream.dataset,
            "sequence": stream.sequence,
            "fps": fps,
            "n_frames": n_frames,
            "modalities": sorted(m.value for m in stream.modalities),
            "associations": stream.meta.get("associations"),
            "gt_trajectory": str(stream.gt_trajectory) if stream.gt_trajectory else None,
        }, indent=2))

        t0 = time.monotonic()
        if on_marker is not None:
            on_marker(0, t0)

        # Prefer bind-mount `docker run`. On hosts where OPA blocks `-v`, fall back to
        # create + docker cp + exec + docker cp (office shared box).
        result = self._invoke_with_mounts(data_root, out_dir, timeout_s)
        if result is None:
            result = self._invoke_with_cp(data_root, out_dir, timeout_s)

        if on_marker is not None:
            on_marker(max(n_frames - 1, 0), time.monotonic())
        return result

    def _invoke_with_mounts(
        self, data_root: Path, out_dir: Path, timeout_s: float,
    ) -> AdapterResult | None:
        cmd = ["docker", "run", "--rm"]
        if self.needs_gpu:
            cmd += ["--gpus", "device=2", "-e", "CUDA_VISIBLE_DEVICES=0"]
        cmd += [
            "-v", f"{data_root.resolve()}:/data:ro",
            "-v", f"{out_dir.resolve()}:/out",
            self.image,
            "--data", "/data",
            "--out", "/out",
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
        except subprocess.TimeoutExpired:
            return AdapterResult(
                outcome=RunOutcome.TIMEOUT, trajectory_path=None,
                error_detail=f"timeout after {timeout_s}s",
            )
        except FileNotFoundError:
            return AdapterResult(
                outcome=RunOutcome.CRASH, trajectory_path=None,
                error_detail="docker not found on PATH",
            )
        stderr = proc.stderr or ""
        (out_dir / "docker_stdout.log").write_text(proc.stdout or "")
        (out_dir / "docker_stderr.log").write_text(stderr)
        if proc.returncode == 125 and "authorization denied" in stderr:
            return None  # signal fallback to cp/exec
        return self._finalize_traj(out_dir, proc.returncode, f"exit={proc.returncode}")

    def _invoke_with_cp(
        self, data_root: Path, out_dir: Path, timeout_s: float,
    ) -> AdapterResult:
        """OPA-safe path: no bind mounts; copy data in/out of a long-lived container."""
        name = f"harness_{self.name}_{int(time.time())}"
        create = [
            "docker", "run", "-d", "--name", name,
            "--entrypoint", "sleep", self.image, str(max(int(timeout_s) + 60, 120)),
        ]
        if self.needs_gpu:
            create[2:2] = ["--gpus", "device=2", "-e", "CUDA_VISIBLE_DEVICES=0"]
        try:
            c = subprocess.run(create, capture_output=True, text=True, timeout=60)
            if c.returncode != 0:
                return AdapterResult(
                    outcome=RunOutcome.CRASH, trajectory_path=None,
                    error_detail=f"docker create failed: {c.stderr}",
                )
            subprocess.run(
                ["docker", "exec", name, "mkdir", "-p", "/data", "/out"],
                check=False, capture_output=True, timeout=30,
            )
            cp_in = subprocess.run(
                ["docker", "cp", f"{data_root.resolve()}/.", f"{name}:/data/"],
                capture_output=True, text=True, timeout=600,
            )
            if cp_in.returncode != 0:
                return AdapterResult(
                    outcome=RunOutcome.CRASH, trajectory_path=None,
                    error_detail=f"docker cp in failed: {cp_in.stderr}",
                )
            # Detached in-container run: capturing docker-exec stdout on this host can
            # SIGPIPE/kill ORB mid-sequence. Launch inside the container, then poll.
            launch = (
                "mkdir -p /out && cd /out && "
                "nohup /opt/ORB_SLAM3/Examples/RGB-D/rgbd_tum "
                "/opt/ORB_SLAM3/Vocabulary/ORBvoc.txt "
                "/opt/ORB_SLAM3/Examples/RGB-D/TUM1.yaml "
                "/data /data/associations.txt "
                ">/out/run.log 2>&1 & echo $!"
            )
            launch_proc = subprocess.run(
                ["docker", "exec", name, "bash", "-lc", launch],
                capture_output=True, text=True, timeout=60,
            )
            if launch_proc.returncode != 0:
                return AdapterResult(
                    outcome=RunOutcome.CRASH, trajectory_path=None,
                    error_detail=f"launch failed: {launch_proc.stderr}",
                )
            # Poll until rgbd_tum exits or timeout.
            deadline = time.monotonic() + timeout_s
            finished = False
            while time.monotonic() < deadline:
                top = subprocess.run(
                    ["docker", "top", name],
                    capture_output=True, text=True, timeout=30,
                )
                if "rgbd_tum" not in (top.stdout or ""):
                    finished = True
                    break
                time.sleep(2.0)
            if not finished:
                subprocess.run(
                    ["docker", "exec", name, "bash", "-lc", "pkill -9 rgbd_tum || true"],
                    capture_output=True, timeout=30,
                )
                return AdapterResult(
                    outcome=RunOutcome.TIMEOUT, trajectory_path=None,
                    error_detail=f"timeout after {timeout_s}s",
                )
            # Copy logs + trajectory out
            subprocess.run(
                ["docker", "cp", f"{name}:/out/.", f"{out_dir.resolve()}/"],
                capture_output=True, text=True, timeout=120,
            )
            run_log = out_dir / "run.log"
            if run_log.is_file():
                (out_dir / "docker_stdout.log").write_text(run_log.read_text())
            # ORB exit code isn't easily recovered from nohup; infer from artifacts.
            traj = out_dir / "CameraTrajectory.txt"
            rc = 0 if traj.is_file() and traj.stat().st_size > 0 else 1
            return self._finalize_traj(out_dir, rc, "detached rgbd_tum")
        finally:
            subprocess.run(
                ["docker", "rm", "-f", name],
                capture_output=True, timeout=60,
            )

    def _finalize_traj(
        self, out_dir: Path, returncode: int, detail: str,
    ) -> AdapterResult:
        traj = out_dir / self.traj_name
        if not traj.is_file():
            # common ORB-SLAM3 name
            alt = out_dir / "CameraTrajectory.txt"
            if alt.is_file():
                traj = alt
        if returncode != 0:
            outcome = RunOutcome.OOM if returncode == 137 else RunOutcome.CRASH
            return AdapterResult(
                outcome=outcome,
                trajectory_path=traj if traj.is_file() else None,
                error_detail=detail,
            )
        if not traj.is_file() or traj.stat().st_size == 0:
            return AdapterResult(
                outcome=RunOutcome.LOST_TRACK, trajectory_path=None,
                error_detail="no trajectory written",
            )
        canon = out_dir / "CameraTrajectory.txt"
        if traj.resolve() != canon.resolve():
            shutil.copy2(traj, canon)
        return AdapterResult(outcome=RunOutcome.OK, trajectory_path=canon)


# --- Classical --------------------------------------------------------------
@register
class OrbSlam3(_ContainerAdapter):
    name = "orb_slam3"
    family = "classical"
    required_modality = Modality.RGBD
    supported_modalities = frozenset({
        Modality.MONO, Modality.STEREO, Modality.RGBD, Modality.VI,
    })
    renders = False
    image = "harness/orb_slam3:x86"
    traj_name = "CameraTrajectory.txt"
    needs_gpu = False

    def __init__(self) -> None:
        lock = Path(__file__).resolve().parents[2] / "containers" / "orb_slam3" / "commit.lock"
        if lock.is_file():
            for line in lock.read_text().splitlines():
                if line.startswith("commit:"):
                    self.commit = line.split(":", 1)[1].strip()
                    break


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
