"""Concrete power sampler backends.

NvidiaSmiSampler is real and runs on the office rig TODAY (coarse GPU-only context —
NOT edge energy; the paper must label it as server-class relative context, plan §4A).
Jetson + external-meter backends are stubbed behind the same interface, unblocked once
the hardware decisions land (plan §14.1–14.2).
"""

from __future__ import annotations

import shutil
import subprocess

from .base import PowerSampler


class NvidiaSmiSampler(PowerSampler):
    """Reads GPU power draw via `nvidia-smi`. Office rig only, GPU rail only.

    Honors CUDA_VISIBLE_DEVICES scoping by querying a specific index (plan §4A: GPU-1).
    Caveat baked into the source: this misses CPU/system power and is datacenter silicon,
    so it is *context*, never the edge energy headline.
    """

    source = "nvidia-smi"
    rails = ("gpu",)

    def __init__(self, hz: float = 20.0, gpu_index: int = 1) -> None:
        super().__init__(hz=hz)
        self.gpu_index = gpu_index
        if shutil.which("nvidia-smi") is None:
            raise RuntimeError("nvidia-smi not found on PATH")

    def _read(self) -> dict[str, float]:
        out = subprocess.check_output(
            ["nvidia-smi",
             f"--id={self.gpu_index}",
             "--query-gpu=power.draw",
             "--format=csv,noheader,nounits"],
            text=True, timeout=1.0,
        ).strip()
        return {"gpu": float(out.splitlines()[0])}


class TegrastatsSampler(PowerSampler):
    """Jetson INA3221 module rails via `tegrastats` / jtop (plan §8.1).

    TODO(jetson): parse tegrastats output for VDD_GPU_SOC / VDD_CPU_CVB / VIN_SYS_5V0;
    document which module + rails + INA3221 update rate (tens of Hz). Energy scope =
    module rails only unless an external meter is added.
    """

    source = "tegrastats"
    rails = ("gpu_soc", "cpu_cvb", "sys_5v0")

    def _read(self) -> dict[str, float]:
        raise NotImplementedError("tegrastats backend TODO — needs Jetson (plan §14.1)")


class ExternalMeterSampler(PowerSampler):
    """Full-system draw at the barrel jack (Monsoon / INA226 shunt / bench analyzer).

    TODO(gear): pick device (plan §14.2). Needs frame-marker sync via GPIO/serial pulse
    since it's off-SoC. Validates onboard numbers and upgrades the claim to full-system.
    """

    source = "external-meter"
    rails = ("system",)

    def _read(self) -> dict[str, float]:
        raise NotImplementedError("external meter backend TODO — needs gear choice (plan §14.2)")
