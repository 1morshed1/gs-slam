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
import shutil
from pathlib import Path

import numpy as np

from .base import CORRUPTIONS
from . import generators  # noqa: F401


def _seed(sequence_id: str, corruption: str, severity: int) -> int:
    h = hashlib.sha256(f"{sequence_id}|{corruption}|{severity}".encode()).digest()
    return int.from_bytes(h[:8], "big")


def _read_rgb(path: Path) -> np.ndarray:
    try:
        import cv2  # type: ignore
        bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if bgr is None:
            raise RuntimeError(f"failed to read {path}")
        return np.ascontiguousarray(bgr[..., ::-1])
    except ImportError:
        from PIL import Image
        return np.asarray(Image.open(path).convert("RGB"))


def _write_rgb(path: Path, rgb: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import cv2  # type: ignore
        cv2.imwrite(str(path), rgb[..., ::-1])
        return
    except ImportError:
        from PIL import Image
        Image.fromarray(rgb).save(path)


def _parse_list(path: Path) -> list[tuple[float, str]]:
    rows: list[tuple[float, str]] = []
    if not path.is_file():
        return rows
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            rows.append((float(parts[0]), parts[1]))
    return rows


def _parse_assoc(path: Path) -> list[tuple[float, str, float, str]]:
    rows: list[tuple[float, str, float, str]] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 4:
            rows.append((float(parts[0]), parts[1], float(parts[2]), parts[3]))
    return rows


def _copy_sidecar_files(src: Path, dst: Path) -> None:
    for name in ("rgb.txt", "depth.txt", "groundtruth.txt", "accelerometer.txt"):
        p = src / name
        if p.is_file():
            shutil.copy2(p, dst / name)


def pregenerate(
    src: Path,
    dst_root: Path,
    corruption_names: list[str],
    severities: list[int],
    sequence_id: str | None = None,
) -> None:
    """Write corrupted copies. Layout mirrors `src` so loaders stay agnostic."""
    src = src.resolve()
    sequence_id = sequence_id or src.name
    assoc_path = src / "associations.txt"
    if assoc_path.is_file():
        pairs = _parse_assoc(assoc_path)
    else:
        from ..datasets.loaders import associate_rgb_depth, write_associations
        rgb = _parse_list(src / "rgb.txt")
        depth = _parse_list(src / "depth.txt")
        pairs = associate_rgb_depth(rgb, depth)
        write_associations(assoc_path, pairs)

    for cname in corruption_names:
        if cname not in CORRUPTIONS:
            raise KeyError(f"unknown corruption {cname!r}; have {sorted(CORRUPTIONS)}")
        corruption = CORRUPTIONS[cname]
        for sev in severities:
            rng = np.random.default_rng(_seed(sequence_id, cname, sev))
            out_dir = dst_root / cname / f"sev{sev}"
            if out_dir.exists():
                shutil.rmtree(out_dir)
            out_dir.mkdir(parents=True, exist_ok=True)

            keep = np.ones(len(pairs), dtype=bool)
            if cname == "frame-drop":
                keep = corruption.drop_mask(len(pairs), sev, rng)  # type: ignore[attr-defined]

            kept_pairs: list[tuple[float, str, float, str]] = []
            for i, (rt, rf, dt, df) in enumerate(pairs):
                if not keep[i]:
                    continue
                src_rgb = src / rf
                dst_rgb = out_dir / rf
                if cname == "frame-drop":
                    dst_rgb.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_rgb, dst_rgb)
                else:
                    img = _read_rgb(src_rgb)
                    corrupted = corruption.apply(img, sev, rng)
                    _write_rgb(dst_rgb, corrupted)
                # depth copied unchanged
                src_depth = src / df
                dst_depth = out_dir / df
                dst_depth.parent.mkdir(parents=True, exist_ok=True)
                if src_depth.is_file():
                    shutil.copy2(src_depth, dst_depth)
                kept_pairs.append((rt, rf, dt, df))

            # Write associations + list files for kept frames
            lines = [f"{rt:.6f} {rf} {dt:.6f} {df}" for rt, rf, dt, df in kept_pairs]
            (out_dir / "associations.txt").write_text("\n".join(lines) + "\n")
            (out_dir / "rgb.txt").write_text(
                "\n".join(f"{rt:.6f} {rf}" for rt, rf, _, _ in kept_pairs) + "\n"
            )
            (out_dir / "depth.txt").write_text(
                "\n".join(f"{dt:.6f} {df}" for _, _, dt, df in kept_pairs) + "\n"
            )
            gt = src / "groundtruth.txt"
            if gt.is_file():
                shutil.copy2(gt, out_dir / "groundtruth.txt")

            manifest = {
                "sequence_id": sequence_id,
                "corruption": cname,
                "severity": sev,
                "params": corruption.params(sev),
                "seed": _seed(sequence_id, cname, sev),
                "n_src_frames": len(pairs),
                "n_out_frames": len(kept_pairs),
            }
            (out_dir / "corruption.json").write_text(json.dumps(manifest, indent=2))


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
