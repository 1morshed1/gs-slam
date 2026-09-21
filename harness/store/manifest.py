"""Per-run reproducibility manifest (plan §10, §13.6).

Captures everything needed to trace a number back to its exact conditions: system commit,
driver/CUDA/torch versions, config, seed, hardware tier, power source, timestamps.
"""

from __future__ import annotations

import json
import platform
import subprocess
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


def _safe(cmd: list[str]) -> Optional[str]:
    try:
        return subprocess.check_output(cmd, text=True, timeout=5).strip()
    except Exception:
        return None


def capture_environment() -> dict[str, Any]:
    """Snapshot host + accelerator + key library versions."""
    env: dict[str, Any] = {
        "platform": platform.platform(),
        "machine": platform.machine(),       # x86_64 (rig) vs aarch64 (Jetson)
        "python": platform.python_version(),
    }
    env["nvidia_driver"] = _safe(["nvidia-smi", "--query-gpu=driver_version",
                                  "--format=csv,noheader"])
    env["gpu_name"] = _safe(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"])
    env["cuda"] = _safe(["nvcc", "--version"])
    for mod in ("torch", "torchvision", "numpy"):
        try:
            m = __import__(mod)
            env[f"{mod}_version"] = getattr(m, "__version__", None)
        except Exception:
            env[f"{mod}_version"] = None
    return env


@dataclass
class RunManifest:
    """One row of provenance per experiment cell."""

    run_id: str
    system: str
    system_commit: str
    family: str
    dataset: str
    sequence: str
    modality: str
    corruption: str = "none"
    severity: int = 0
    repeat: int = 0
    power_mode: str = "default"     # nvpmodel setting (plan §8, RQ5)
    clocks_locked: bool = False     # jetson_clocks
    hardware_tier: str = "office_rig"   # "office_rig" | "jetson:<model>"
    power_source: str = "nvidia-smi"    # provenance for the energy claim's scope
    seed: int = 0
    config: dict[str, Any] = field(default_factory=dict)
    environment: dict[str, Any] = field(default_factory=capture_environment)
    created_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2))

    @property
    def cell_key(self) -> str:
        """Stable key identifying this matrix cell (for resume/dedup)."""
        return "|".join([
            self.system, self.dataset, self.sequence, self.modality,
            self.corruption, str(self.severity), str(self.repeat),
            self.power_mode, self.hardware_tier,
        ])
