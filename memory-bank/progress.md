# Progress

## What works

| Area | Status |
|---|---|
| Plan document | Draft v0.1 present |
| Package layout `harness/` | Complete + datasets restored |
| Adapter registry | Registered; **ORB-SLAM3 `run()` works** (docker cp/exec) |
| Corruptions | All plan-§6 core kernels implemented; pregenerate writes TUM layout |
| Datasets | Frame model, FixedRateFeeder, TUM RGB-D loader; fr1/desk on disk |
| Power | `nvidia-smi` backend; energy integrate resilient if samples missing |
| Eval | **evo ATE/RPE wired**; quality still TODO |
| Orchestrator | Matrix + `_build_stream` + clean cells store ATE |
| Store | Manifest + sqlite with accuracy columns populated |
| Tests | `tests/test_scaffold.py` — 6 passed |
| Containers | **`harness/orb_slam3:x86` built**; **`harness/photo_slam:x86` built** (OpenCV-CUDA from source + libtorch 2.7 patches); L4T deferred |
| Analysis notebooks | README only |

## Phase status

| Phase | Goal | State |
|---|---|---|
| **P0** Bring-up | Reproduce headline on ≥1 sequence | **ORB-SLAM3 on rig: PASS** (ATE ~1.7–2.3 cm fr1/desk). Photo-SLAM: first run ok on GPU-1, **PASS (confirmed 2026-09-28)** — idle GPU-1 ×11: median ATE ~1.6 cm (paper desktop 2.60 cm), good-mode PSNR ~21.8–22.0 dB (paper 20.87); 2/11 runs hit inherited ORB-SLAM3 tracker failure at t≈9 s (stock ORB-SLAM3: 4/10). Jetson TBD. |
| **P1** Measurement infra | Power sync, idle baselines | Partial (rig GPU backend only) |
| **P2** Clean baseline | Uncorrupted grid → Pareto | Unblocked for ORB only |
| **P3** Robustness sweep | Perturbation × severity | **Smoke grid done ×10 repeats** (noise/jpeg/defocus × sev{1,3,5}); generators ready for full suite |
| **P4** Analysis & write-up | Notebooks + paper | Placeholders |
| **P5** Artifact release | Public harness + data | Later |

## Smoke robustness (2026-09-24)

ORB-SLAM3 × TUM fr1/desk × {gaussian-noise, jpeg-compression, defocus-blur} × sev{1,3,5} × 2 repeats (+ clean controls). 20/20 cells completed.

| Corruption | sev1 mean ATE | sev3 mean ATE | sev5 |
|---|---|---|---|
| none (control) | — | — | 0.0198 m (sev0) |
| gaussian-noise | 0.0166 m | 0.0181 m | 0.021 / **1.27 m** (r0/r1) — high variance |
| jpeg-compression | 0.0174 m | 0.0247 m | 0.0177 m |
| defocus-blur | 0.0176 m | 0.0193 m | **lost_track** both repeats |

Takeaway: pipeline handles corruption end-to-end; sev5 can induce failure or ATE blow-up (first-class outcomes). jpeg sev5 stayed surprisingly stable on this sequence.

## Smoke robustness ×10 repeats (2026-09-29, supersedes the ×2 table)

Same grid, 10 repeats/cell (100 runs). `python -m harness.store.summarize`. ATE in cm, over `ok` runs.

| Corruption | sev | fail | median | IQR | mean ± std | max |
|---|---|---|---|---|---|---|
| none | 0 | 0% | 1.77 | 1.72–2.20 | 2.19 ± 0.82 | 4.12 |
| gaussian-noise | 1 | 0% | 1.70 | 1.68–1.71 | 1.69 ± 0.03 | 1.72 |
| gaussian-noise | 3 | 0% | 1.87 | 1.81–1.94 | 2.00 ± 0.37 | 2.77 |
| gaussian-noise | 5 | 0% | 3.37 | 2.12–125.4 | 51.8 ± 63.7 | 126.8 |
| jpeg-compression | 1 | 0% | 1.73 | 1.72–1.76 | 1.77 ± 0.13 | 2.13 |
| jpeg-compression | 3 | 0% | 1.76 | 1.72–2.75 | 2.28 ± 0.89 | 4.26 |
| jpeg-compression | 5 | 0% | 1.80 | 1.73–1.99 | 1.94 ± 0.39 | 2.95 |
| defocus-blur | 1 | 0% | 1.73 | 1.67–1.76 | 1.73 ± 0.09 | 1.93 |
| defocus-blur | 3 | 0% | 1.76 | 1.71–1.77 | 1.85 ± 0.25 | 2.44 |
| defocus-blur | 5 | **100% lost_track** | – | – | – | – |

- Sev1–3 medians are indistinguishable from clean (1.7–1.9 cm); the ×2 "jpeg sev3 = 2.47 cm" was clean-baseline tracker variance, not a corruption effect.
- gaussian-noise sev5 is **bimodal**: 6/10 at 2.0–3.6 cm, **4/10 at ~125 cm** (a consistent catastrophic mode, outcome still `ok`). Mean ± std is meaningless here → median + mode/failure counts.
- defocus-blur sev5 is a deterministic failure (10/10 `lost_track`).
- Open: classify `ok`-but-catastrophic (e.g. ATE > 0.5 m) as a failure category?

## Known issues / blockers

- Host OPA blocks `docker run -v`; adapter workaround required.
- Jetson model TBD → L4T images + edge feasibility unknown.
- External power meter TBD → claim scope undecided.
- GS/GFM containers: Photo-SLAM needs OpenCV CUDA contrib modules (apt OpenCV insufficient) → built from source in Dockerfile; others not started.
- GPU-1 is shared with other jobs; P0 waits for ≥40 GiB free + ≤5% util.
- Analysis notebooks not created.
- Detached ORB path: no-traj now labeled `lost_track` (was mis-tagged `crash` for defocus sev5).
- Clean fr1/desk is multi-modal for ORB-family trackers (fast rotation at t≈9 s): 2 repeats/cell is underpowered — need ≥5–10 and median + failure-rate reporting.

## Verification (2026-09-23)

```bash
pip/uv: .venv with `.[rig,dev]`
pytest   # 6 passed
python -m harness.orchestrator.run \
  --config harness/orchestrator/configs/smoke.yaml --clean-only
# ATE-RMSE ≈ 0.017–0.023 m on fr1/desk
```
