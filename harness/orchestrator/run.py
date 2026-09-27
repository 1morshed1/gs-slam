"""Resumable matrix runner (plan §9, §10).

Ties the pieces together: for each cell → build stream (clean or corrupted) → attach
power sampler + frame markers → run adapter → eval → write manifest + store row.
Crash/timeout/lost-track/OOM are recorded as outcomes, not fatal (plan §10).
"""

from __future__ import annotations

import argparse
import uuid
from pathlib import Path

from ..adapters import systems as _systems  # noqa: F401  registers adapters
from ..adapters.base import REGISTRY, RunOutcome
from ..datasets.feeder import FixedRateFeeder
from ..datasets.loaders import load_sequence
from ..eval.energy import integrate_energy
from ..eval.metrics import eval_accuracy
from ..power.backends import NvidiaSmiSampler
from ..power.base import PowerSampler
from ..store.db import ResultStore
from ..store.manifest import RunManifest
from .matrix import Cell, ExperimentConfig, expand_matrix


def _load_config(path: Path) -> ExperimentConfig:
    import yaml
    raw = yaml.safe_load(path.read_text())
    raw["sequences"] = [tuple(s) for s in raw["sequences"]]
    known = {f.name for f in ExperimentConfig.__dataclass_fields__.values()}  # type: ignore
    raw = {k: v for k, v in raw.items() if k in known}
    return ExperimentConfig(**raw)


def _make_sampler(cfg: ExperimentConfig) -> PowerSampler:
    if cfg.hardware_tier == "office_rig":
        return NvidiaSmiSampler(hz=20.0, gpu_index=1)
    raise NotImplementedError(f"no power backend wired for tier {cfg.hardware_tier!r}")


def corrupted_root(data_root: Path, cell: Cell) -> Path:
    """Layout: datasets_corrupted/<dataset>/<sequence>/<corruption>/sevN/."""
    base = data_root.parent / "datasets_corrupted" if data_root.name == "datasets" else data_root / ".." / "datasets_corrupted"
    return (base / cell.dataset / cell.sequence / cell.corruption / f"sev{cell.severity}").resolve()


def _build_stream(cell: Cell, data_root: Path):
    if cell.corruption == "none" or cell.severity == 0:
        return load_sequence(cell.dataset, cell.sequence, data_root, modality=cell.modality)
    root = corrupted_root(data_root, cell)
    if not root.is_dir():
        raise FileNotFoundError(
            f"corrupted sequence missing: {root} — run harness.corruptions.pregenerate first"
        )
    from ..datasets.loaders import LOADERS
    return LOADERS[cell.dataset](root, sequence=cell.sequence)


def _load_orb_commit() -> str:
    lock = Path(__file__).resolve().parents[2] / "containers" / "orb_slam3" / "commit.lock"
    if not lock.is_file():
        return "UNPINNED"
    for line in lock.read_text().splitlines():
        if line.startswith("commit:"):
            return line.split(":", 1)[1].strip()
    return "UNPINNED"


def run_cell(cell: Cell, cfg: ExperimentConfig, store: ResultStore,
             data_root: Path, out_root: Path, timeout_s: float) -> None:
    adapter_cls = REGISTRY.get(cell.system)
    if adapter_cls is None:
        raise KeyError(f"no adapter registered for {cell.system!r}")
    adapter = adapter_cls()
    if cell.system == "orb_slam3" and adapter.commit == "UNPINNED":
        adapter.commit = _load_orb_commit()

    run_id = uuid.uuid4().hex[:12]
    out_dir = out_root / cell.system / f"{cell.dataset}_{cell.sequence}" / \
        f"{cell.corruption}_sev{cell.severity}_r{cell.repeat}" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = RunManifest(
        run_id=run_id, system=cell.system, system_commit=adapter.commit,
        family=adapter.family, dataset=cell.dataset, sequence=cell.sequence,
        modality=cell.modality, corruption=cell.corruption, severity=cell.severity,
        repeat=cell.repeat, power_mode=cell.power_mode,
        hardware_tier=cfg.hardware_tier,
    )
    manifest.write(out_dir / "manifest.json")

    stream = _build_stream(cell, data_root)
    if not adapter.can_run(stream):
        store.upsert(cell_key_for(cell, cfg), {
            "run_id": run_id, "system": cell.system, "outcome": "skipped_modality",
            "manifest_path": str(out_dir / "manifest.json"), "raw_log_dir": str(out_dir),
        })
        return

    sampler = _make_sampler(cfg)
    feeder = FixedRateFeeder(stream, target_fps=stream.fps, on_marker=sampler.log.mark)

    sampler.start()
    try:
        result = adapter.run(feeder, out_dir, timeout_s=timeout_s)
    except Exception as exc:
        sampler.stop()
        store.upsert(cell_key_for(cell, cfg), {
            "run_id": run_id, "system": cell.system, "family": adapter.family,
            "outcome": RunOutcome.CRASH.value,
            "manifest_path": str(out_dir / "manifest.json"),
            "raw_log_dir": str(out_dir), "extra_json_error": str(exc),
        })
        return
    log = sampler.stop()
    try:
        log.to_npz(out_dir / "power.npz")
    except Exception:
        pass

    try:
        energy = integrate_energy(log, keyframe_indices=result.keyframe_indices)
        energy_fields = {
            "joules_total": energy.joules_total,
            "joules_per_frame": energy.joules_per_frame,
            "joules_per_keyframe": energy.joules_per_keyframe,
            "avg_power_w": energy.avg_power_w,
            "dynamic_joules": energy.dynamic_joules,
            "edp": energy.edp,
        }
    except ValueError as e:
        # Short runs / failed nvidia-smi polls — still record the SLAM outcome.
        print(f"  energy integrate skipped: {e}")
        energy_fields = {}

    row = {
        "run_id": run_id, "system": cell.system, "family": adapter.family,
        "dataset": cell.dataset, "sequence": cell.sequence, "modality": cell.modality,
        "corruption": cell.corruption, "severity": cell.severity, "repeat": cell.repeat,
        "power_mode": cell.power_mode, "hardware_tier": cfg.hardware_tier,
        "power_source": sampler.source, "outcome": result.outcome.value,
        **energy_fields,
        "peak_host_ram_mb": result.peak_host_ram_mb, "peak_vram_mb": result.peak_vram_mb,
        "manifest_path": str(out_dir / "manifest.json"), "raw_log_dir": str(out_dir),
        "created_utc": manifest.created_utc,
    }

    if result.outcome == RunOutcome.OK and result.trajectory_path and stream.gt_trajectory:
        try:
            acc = eval_accuracy(result.trajectory_path, stream.gt_trajectory)
            row.update({
                "ate_rmse": acc.ate_rmse,
                "rpe_trans": acc.rpe_trans,
                "rpe_rot": acc.rpe_rot,
                "lost_track_rate": acc.lost_track_rate,
            })
            (out_dir / "accuracy.json").write_text(
                __import__("json").dumps({
                    "ate_rmse": acc.ate_rmse,
                    "rpe_trans": acc.rpe_trans,
                    "rpe_rot": acc.rpe_rot,
                    "lost_track_rate": acc.lost_track_rate,
                    "n_frames": acc.n_frames,
                    "n_valid": acc.n_valid,
                }, indent=2)
            )
            print(f"  ATE-RMSE={acc.ate_rmse:.4f} m  (n_valid={acc.n_valid})")
        except Exception as e:
            print(f"  eval_accuracy failed: {e}")
            row["extra_json_eval_error"] = str(e)

    store.upsert(cell_key_for(cell, cfg), row)


def cell_key_for(cell: Cell, cfg: ExperimentConfig) -> str:
    return "|".join([cell.system, cell.dataset, cell.sequence, cell.modality,
                     cell.corruption, str(cell.severity), str(cell.repeat),
                     cell.power_mode, cfg.hardware_tier])


def main() -> None:
    ap = argparse.ArgumentParser(description="Run the SLAM benchmark matrix (resumable).")
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--data-root", type=Path, default=Path("datasets"))
    ap.add_argument("--out-root", type=Path, default=Path("runs"))
    ap.add_argument("--store", type=Path, default=Path("store/results.sqlite"))
    ap.add_argument("--timeout-s", type=float, default=1800.0)
    ap.add_argument("--dry-run", action="store_true", help="print cells, run nothing")
    ap.add_argument("--clean-only", action="store_true",
                    help="run only severity-0 clean control cells")
    a = ap.parse_args()

    cfg = _load_config(a.config)
    store = ResultStore(a.store)
    cells = expand_matrix(cfg)
    if a.clean_only:
        cells = [c for c in cells if c.severity == 0]

    todo = [c for c in cells if not store.has_cell(cell_key_for(c, cfg))]
    print(f"matrix: {len(cells)} cells, {len(todo)} remaining "
          f"({len(cells) - len(todo)} already in store)")
    if a.dry_run:
        for c in todo:
            print(" ", cell_key_for(c, cfg))
        return

    for i, cell in enumerate(todo, 1):
        print(f"[{i}/{len(todo)}] {cell_key_for(cell, cfg)}")
        try:
            run_cell(cell, cfg, store, a.data_root, a.out_root, a.timeout_s)
        except NotImplementedError as e:
            print(f"  not wired yet: {e}")
            break
        except FileNotFoundError as e:
            print(f"  missing data: {e}")
            if cell.severity > 0:
                continue
            break


if __name__ == "__main__":
    main()
