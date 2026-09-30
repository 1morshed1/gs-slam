"""Smoke tests: the decision-independent scaffold imports and its pure logic works.

These pass on the office rig today with only numpy installed (cv2/PIL optional). They
guard the contracts a filler builds against: matrix expansion, energy integration,
corruption registry + seeding, adapter registry.
"""

from __future__ import annotations

import numpy as np


def test_registries_populated():
    from harness.adapters.base import REGISTRY
    from harness.adapters import systems  # noqa: F401  (import registers)
    from harness.corruptions import CORRUPTIONS

    assert {"orb_slam3", "photo_slam", "mast3r_slam"} <= set(REGISTRY)
    assert {"gaussian-noise", "jpeg-compression", "defocus-blur", "motion-blur"} <= set(CORRUPTIONS)


def test_matrix_expansion_and_pruning():
    from harness.orchestrator.matrix import ExperimentConfig, expand_matrix

    cfg = ExperimentConfig(
        systems=["orb_slam3", "photo_slam"],
        sequences=[("tum", "fr1_desk", "rgbd")],
        corruptions=["gaussian-noise"],
        severities=[1, 3, 5],
        fine_severities=[1, 2, 3, 4, 5],
        fine_subset_systems=["photo_slam"],
        repeats=2,
    )
    cells = expand_matrix(cfg)
    # clean control: 2 systems * 1 seq * 2 repeats = 4
    clean = [c for c in cells if c.severity == 0]
    assert len(clean) == 4
    # orb_slam3 (coarse 3 sev) vs photo_slam (fine 5 sev), * 2 repeats
    orb = [c for c in cells if c.system == "orb_slam3" and c.severity > 0]
    photo = [c for c in cells if c.system == "photo_slam" and c.severity > 0]
    assert len(orb) == 3 * 2
    assert len(photo) == 5 * 2
    # no duplicates
    assert len(cells) == len(set(cells))


def test_energy_integration_constant_power():
    from harness.power.base import PowerLog, PowerSample
    from harness.eval.energy import integrate_energy

    # 10 W constant for 2 s, markers at t=0,1,2 → 10 J per 1 s frame window.
    log = PowerLog(source="test", rails=("gpu",))
    for i in range(21):
        t = i * 0.1
        log.samples.append(PowerSample(t, {"gpu": 10.0}))
    log.markers = [(0, 0.0), (1, 1.0), (2, 2.0)]
    m = integrate_energy(log)
    assert abs(m.joules_total - 20.0) < 1e-6
    assert abs(m.joules_per_frame - 10.0) < 1e-6
    assert abs(m.avg_power_w - 10.0) < 1e-6


def test_corruption_determinism_and_severity():
    from harness.corruptions import CORRUPTIONS

    img = (np.arange(4 * 4 * 3) % 256).reshape(4, 4, 3).astype(np.uint8)
    noise = CORRUPTIONS["gaussian-noise"]
    a = noise.apply(img, 3, np.random.default_rng(42))
    b = noise.apply(img, 3, np.random.default_rng(42))
    assert np.array_equal(a, b)                       # deterministic given seed
    assert a.dtype == np.uint8 and a.shape == img.shape
    # higher severity → larger perturbation on average
    lo = noise.apply(img, 1, np.random.default_rng(0)).astype(int)
    hi = noise.apply(img, 5, np.random.default_rng(0)).astype(int)
    assert np.abs(hi - img).mean() > np.abs(lo - img).mean()


def test_tum_loader_and_feeder(tmp_path):
    from harness.datasets.frame import Modality
    from harness.datasets.feeder import FixedRateFeeder
    from harness.datasets.loaders import load_tum_rgbd, write_associations

    root = tmp_path / "rgbd_dataset_freiburg1_desk"
    (root / "rgb").mkdir(parents=True)
    (root / "depth").mkdir()
    # minimal 2-frame synthetic TUM layout
    import numpy as np
    try:
        import cv2
    except Exception:
        cv2 = None
    for i, name in enumerate(("a", "b")):
        rgb = root / "rgb" / f"{name}.png"
        depth = root / "depth" / f"{name}.png"
        if cv2 is not None:
            cv2.imwrite(str(rgb), np.zeros((8, 8, 3), np.uint8))
            cv2.imwrite(str(depth), np.zeros((8, 8), np.uint16))
        else:
            rgb.write_bytes(b"\x89PNG\r\n\x1a\n")
            depth.write_bytes(b"\x89PNG\r\n\x1a\n")
    (root / "rgb.txt").write_text("1.0 rgb/a.png\n1.1 rgb/b.png\n")
    (root / "depth.txt").write_text("1.0 depth/a.png\n1.1 depth/b.png\n")
    (root / "groundtruth.txt").write_text(
        "# ts tx ty tz qx qy qz qw\n1.0 0 0 0 0 0 0 1\n1.1 0 0 0 0 0 0 1\n"
    )
    write_associations(
        root / "associations.txt",
        [(1.0, "rgb/a.png", 1.0, "depth/a.png"),
         (1.1, "rgb/b.png", 1.1, "depth/b.png")],
    )
    stream = load_tum_rgbd(root)
    assert len(stream) == 2
    assert Modality.RGBD in stream.modalities
    marks = []
    feeder = FixedRateFeeder(stream, target_fps=100.0, on_marker=lambda i, t: marks.append(i))
    frames = list(feeder)
    assert len(frames) == 2 and marks == [0, 1]


def test_orb_slam3_accepts_rgbd():
    from harness.adapters import systems  # noqa: F401
    from harness.adapters.base import REGISTRY
    from harness.datasets.frame import FrameStream, Modality
    from pathlib import Path

    adapter = REGISTRY["orb_slam3"]()
    stream = FrameStream(
        dataset="tum", sequence="x", root=Path("."),
        frames=[], modalities=frozenset({Modality.RGBD, Modality.MONO}),
    )
    assert adapter.can_run(stream)


def test_summarize_median_and_fail_rate(tmp_path):
    from harness.store.db import ResultStore
    from harness.store.summarize import summarize

    store = ResultStore(tmp_path / "r.sqlite")
    base = dict(system="orb_slam3", dataset="tum", sequence="s", modality="rgbd",
                corruption="none", severity=0, power_mode="default", hardware_tier="office_rig")
    for r, (outcome, ate) in enumerate([("ok", 0.01), ("ok", 0.02), ("ok", 0.09),
                                        ("lost_track", None)]):
        store.upsert(f"k{r}", dict(base, run_id=f"id{r}", repeat=r, outcome=outcome, ate_rmse=ate))
    (s,) = summarize(store.db_path)
    assert s["n"] == 4 and s["n_fail"] == 1 and abs(s["fail_rate"] - 0.25) < 1e-9
    assert abs(s["ate_median"] - 0.02) < 1e-9       # median ignores the failed run
    assert abs(s["ate_max"] - 0.09) < 1e-9


def test_summarize_outcome_taxonomy(tmp_path):
    """converged / diverged / hard-fail split + threshold sensitivity (plan §7)."""
    from harness.store.db import ResultStore
    from harness.store.summarize import summarize

    store = ResultStore(tmp_path / "r.sqlite")
    base = dict(system="orb_slam3", dataset="tum", sequence="s", modality="rgbd",
                corruption="gaussian-noise", severity=5, power_mode="default",
                hardware_tier="office_rig")
    # 6 converged (~2-3.6 cm), 4 diverged (~125 cm, still "ok"), 0 hard failures —
    # the real bimodal gaussian-noise sev5 shape.
    ates = [0.020, 0.021, 0.030, 0.033, 0.035, 0.036, 1.25, 1.26, 1.27, 1.28]
    for r, ate in enumerate(ates):
        store.upsert(f"k{r}", dict(base, run_id=f"id{r}", repeat=r, outcome="ok", ate_rmse=ate))

    (s,) = summarize(store.db_path, catastrophic_ate_m=0.5)
    assert s["n"] == 10 and s["n_converged"] == 6 and s["n_diverged"] == 4
    assert s["n_hard_fail"] == 0 and s["fail_rate"] == 0.0
    assert abs(s["catastrophic_rate"] - 0.4) < 1e-9  # diverged counted as failure
    assert s["ate_max"] <= 0.5                        # stats over converged only
    assert abs(s["div_median"] - 1.265) < 1e-9

    # Bimodal gap → split is stable across any threshold between the modes.
    for thr in (0.1, 0.25, 0.5, 1.0):
        (s,) = summarize(store.db_path, catastrophic_ate_m=thr)
        assert abs(s["catastrophic_rate"] - 0.4) < 1e-9
