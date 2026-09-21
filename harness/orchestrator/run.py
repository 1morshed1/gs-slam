"""Resumable matrix runner (plan §9, §10).

Ties the pieces together: for each cell → build stream (clean or corrupted) → attach
power sampler + frame markers → run adapter → eval → write manifest + store row.
Crash/timeout/lost-track/OOM are recorded as outcomes, not fatal (plan §10).

The wiring marked TODO needs the concrete loaders/adapters that arrive in Phase 0–2.
The control flow, resume logic, and power/marker plumbing are complete so a filler drops
in loaders + adapters without touching orchestration.
"""

from __future__ import annotations

import argparse
import uuid
from pathlib import Path

from ..adapters.base import REGISTRY, RunOutcome
from ..datasets.feeder import FixedRateFeeder
from ..eval.energy import integrate_energy
from ..power.backends import NvidiaSmiSampler
from ..power.base import PowerSampler
from ..store.db import ResultStore
from ..store.manifest import RunManifest
from .matrix import Cell, ExperimentConfig, expand_matrix


def _load_config(path: Path) -> ExperimentConfig:
    import yaml  # pyyaml, optional dep
    raw = yaml.safe_load(path.read_text())
    raw["sequences"] = [tuple(s) for s in raw["sequences"]]
    return ExperimentConfig(**raw)


def _make_sampler(cfg: ExperimentConfig) -> PowerSampler:
    """Pick a power backend from the hardware tier. Rig → nvidia-smi (coarse context)."""
    if cfg.hardware_tier == "office_rig":
        return NvidiaSmiSampler(hz=20.0, gpu_index=1)  # plan §4A: GPU-1 only
    # TODO(jetson): return TegrastatsSampler() / ExternalMeterSampler() per gear choice.
    raise NotImplementedError(f"no power backend wired for tier {cfg.hardware_tier!r}")


def _build_stream(cell: Cell, data_root: Path):
    """Resolve the (possibly corrupted) FrameStream for this cell.

    TODO(P0): use datasets.loaders.LOADERS[cell.dataset](...) and, when cell.corruption
    != 'none', point it at the pre-generated corrupted copy under datasets_corrupted/.
    """
    raise NotImplementedError("stream build TODO — needs loaders (plan §5); interface stable")


def run_cell(cell: Cell, cfg: ExperimentConfig, store: ResultStore,
             data_root: Path, out_root: Path, timeout_s: float) -> None:
    adapter_cls = REGISTRY.get(cell.system)
    if adapter_cls is None:
        raise KeyError(f"no adapter registered for {cell.system!r}")
    adapter = adapter_cls()

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
    # feeder emits frame markers straight into the sampler's shared log
    feeder = FixedRateFeeder(stream, target_fps=stream.fps,
                             on_marker=sampler.log.mark)

    sampler.start()
    try:
        result = adapter.run(feeder, out_dir, timeout_s=timeout_s)  # noqa: F841
    except Exception as exc:  # crash is an outcome, not a stop
        sampler.stop()
        store.upsert(cell_key_for(cell, cfg), {
            "run_id": run_id, "system": cell.system, "family": adapter.family,
            "outcome": RunOutcome.CRASH.value,
            "manifest_path": str(out_dir / "manifest.json"),
            "raw_log_dir": str(out_dir), "extra_json_error": str(exc),
        })
        return
    log = sampler.stop()
    log.to_npz(out_dir / "power.npz")

    energy = integrate_energy(log, keyframe_indices=result.keyframe_indices)
    # TODO(P2): eval_accuracy(result.trajectory_path, gt) + eval_quality(...) when GT wired.
    store.upsert(cell_key_for(cell, cfg), {
        "run_id": run_id, "system": cell.system, "family": adapter.family,
        "dataset": cell.dataset, "sequence": cell.sequence, "modality": cell.modality,
        "corruption": cell.corruption, "severity": cell.severity, "repeat": cell.repeat,
        "power_mode": cell.power_mode, "hardware_tier": cfg.hardware_tier,
        "power_source": sampler.source, "outcome": result.outcome.value,
        "joules_total": energy.joules_total, "joules_per_frame": energy.joules_per_frame,
        "joules_per_keyframe": energy.joules_per_keyframe, "avg_power_w": energy.avg_power_w,
        "dynamic_joules": energy.dynamic_joules, "edp": energy.edp,
        "peak_host_ram_mb": result.peak_host_ram_mb, "peak_vram_mb": result.peak_vram_mb,
        "manifest_path": str(out_dir / "manifest.json"), "raw_log_dir": str(out_dir),
        "created_utc": manifest.created_utc,
    })


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
    a = ap.parse_args()

    cfg = _load_config(a.config)
    store = ResultStore(a.store)
    cells = expand_matrix(cfg)

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
            break  # during bring-up, stop at the first unimplemented piece


if __name__ == "__main__":
    main()
