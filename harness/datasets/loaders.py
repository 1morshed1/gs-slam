"""Sequence loaders. Keep on-disk layout identical for clean vs corrupted copies."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from .frame import Frame, FrameStream, Modality


def _parse_list_file(path: Path) -> list[tuple[float, str]]:
    """Parse TUM-style `timestamp filename` lists (skip comments / blanks)."""
    rows: list[tuple[float, str]] = []
    if not path.is_file():
        return rows
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        rows.append((float(parts[0]), parts[1]))
    return rows


def _parse_associations(path: Path) -> list[tuple[float, str, float, str]]:
    """rgb_ts rgb_file depth_ts depth_file."""
    rows: list[tuple[float, str, float, str]] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 4:
            continue
        rows.append((float(parts[0]), parts[1], float(parts[2]), parts[3]))
    return rows


def associate_rgb_depth(
    rgb: list[tuple[float, str]],
    depth: list[tuple[float, str]],
    *,
    max_dt: float = 0.02,
) -> list[tuple[float, str, float, str]]:
    """Greedy nearest-neighbor association (TUM associate.py style)."""
    depth_unused = list(depth)
    out: list[tuple[float, str, float, str]] = []
    for rt, rf in rgb:
        best_i = -1
        best_dt = max_dt
        for i, (dt, df) in enumerate(depth_unused):
            d = abs(rt - dt)
            if d < best_dt:
                best_dt = d
                best_i = i
        if best_i < 0:
            continue
        dt, df = depth_unused.pop(best_i)
        out.append((rt, rf, dt, df))
    return out


def write_associations(path: Path, rows: list[tuple[float, str, float, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{rt:.6f} {rf} {dt:.6f} {df}" for rt, rf, dt, df in rows]
    path.write_text("\n".join(lines) + ("\n" if lines else ""))


def load_tum_rgbd(root: Path, *, sequence: Optional[str] = None, fps: float = 30.0) -> FrameStream:
    """Load a TUM RGB-D sequence directory.

    Expects: rgb.txt, depth.txt, groundtruth.txt; associations.txt preferred
    (generated from rgb/depth if missing).
    """
    root = root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"TUM sequence not found: {root}")

    assoc_path = root / "associations.txt"
    if assoc_path.is_file():
        pairs = _parse_associations(assoc_path)
    else:
        rgb = _parse_list_file(root / "rgb.txt")
        depth = _parse_list_file(root / "depth.txt")
        if not rgb or not depth:
            raise FileNotFoundError(
                f"{root}: need associations.txt or both rgb.txt and depth.txt"
            )
        pairs = associate_rgb_depth(rgb, depth)
        write_associations(assoc_path, pairs)

    frames: list[Frame] = []
    for i, (rt, rf, _dt, df) in enumerate(pairs):
        frames.append(
            Frame(
                index=i,
                timestamp=rt,
                rgb_path=root / rf,
                depth_path=root / df,
            )
        )

    gt = root / "groundtruth.txt"
    seq_name = sequence or root.name
    return FrameStream(
        dataset="tum",
        sequence=seq_name,
        root=root,
        frames=frames,
        modalities=frozenset({Modality.RGBD, Modality.MONO}),
        fps=fps,
        gt_trajectory=gt if gt.is_file() else None,
        meta={"associations": str(assoc_path)},
    )


LOADERS: dict[str, Callable[..., FrameStream]] = {
    "tum": load_tum_rgbd,
}


def load_sequence(
    dataset: str,
    sequence: str,
    data_root: Path,
    *,
    modality: str = "rgbd",
) -> FrameStream:
    """Resolve `data_root/<dataset>/<sequence>` via the dataset loader registry."""
    if dataset not in LOADERS:
        raise KeyError(f"unknown dataset {dataset!r}; have {sorted(LOADERS)}")
    root = data_root / dataset / sequence
    stream = LOADERS[dataset](root, sequence=sequence)
    # modality arg is recorded for matrix cells; stream modalities come from files.
    _ = modality
    return stream
