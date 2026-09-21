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
