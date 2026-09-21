"""Pre-generate corrupted sequences to disk (plan §6 core rule).

Given a clean sequence dir, write out a corrupted copy per (corruption, severity) with a
deterministic seed derived from (sequence_id, corruption, severity). Records the exact
params used into a sidecar manifest so every corrupted frame is reproducible.

Usage:
    python -m harness.corruptions.pregenerate \
        --src datasets/tum/rgbd_dataset_freiburg1_desk \
        --dst datasets_corrupted/tum_fr1_desk \
        --corruptions gaussian-noise jpeg-compression defocus-blur \
        --severities 1 3 5
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from .base import CORRUPTIONS


def _seed(sequence_id: str, corruption: str, severity: int) -> int:
    h = hashlib.sha256(f"{sequence_id}|{corruption}|{severity}".encode()).digest()
    return int.from_bytes(h[:8], "big")


def pregenerate(
    src: Path,
    dst_root: Path,
    corruption_names: list[str],
    severities: list[int],
    sequence_id: str | None = None,
) -> None:
    """Write corrupted copies. Image I/O left to the filler (cv2/PIL) — see TODO."""
    sequence_id = sequence_id or src.name
    for cname in corruption_names:
        if cname not in CORRUPTIONS:
            raise KeyError(f"unknown corruption {cname!r}; have {sorted(CORRUPTIONS)}")
        corruption = CORRUPTIONS[cname]
        for sev in severities:
            rng = np.random.default_rng(_seed(sequence_id, cname, sev))
            out_dir = dst_root / cname / f"sev{sev}"
            out_dir.mkdir(parents=True, exist_ok=True)
            manifest = {
                "sequence_id": sequence_id,
                "corruption": cname,
                "severity": sev,
                "params": corruption.params(sev),
                "seed": _seed(sequence_id, cname, sev),
            }
            (out_dir / "corruption.json").write_text(json.dumps(manifest, indent=2))
            # TODO(rig): iterate frames of `src`, apply corruption.apply(img, sev, rng),
            # write corrupted image alongside copied depth/right/imu + timestamp files.
            # Keep the on-disk layout identical to `src` so loaders are corruption-agnostic.
            raise NotImplementedError(
                "frame iteration + image write TODO — interface + seeding are done"
            )


def _cli() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, required=True)
    ap.add_argument("--dst", type=Path, required=True)
    ap.add_argument("--corruptions", nargs="+", required=True)
    ap.add_argument("--severities", nargs="+", type=int, default=[1, 3, 5])
    ap.add_argument("--sequence-id", default=None)
    a = ap.parse_args()
    pregenerate(a.src, a.dst, a.corruptions, a.severities, a.sequence_id)


if __name__ == "__main__":
    _cli()
