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
| **P0** Bring-up | Reproduce headline on ≥1 sequence | **ORB-SLAM3 on rig: PASS** (ATE ~1.7–2.3 cm fr1/desk). Photo-SLAM: first run ok on GPU-1, ATE 6.3 cm / PSNR ~18.1 dB on contended GPU (paper desktop 2.6 cm / 20.9 dB); idle-GPU repeats queued. Jetson TBD. |
| **P1** Measurement infra | Power sync, idle baselines | Partial (rig GPU backend only) |
| **P2** Clean baseline | Uncorrupted grid → Pareto | Unblocked for ORB only |
| **P3** Robustness sweep | Perturbation × severity | **Smoke grid done** (noise/jpeg/defocus × sev{1,3,5} × 2); generators ready for full suite |
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

## Known issues / blockers

- Host OPA blocks `docker run -v`; adapter workaround required.
- Jetson model TBD → L4T images + edge feasibility unknown.
- External power meter TBD → claim scope undecided.
- GS/GFM containers: Photo-SLAM needs OpenCV CUDA contrib modules (apt OpenCV insufficient) → built from source in Dockerfile; others not started.
- GPU-1 is shared with other jobs; P0 waits for ≥40 GiB free + ≤5% util.
- Analysis notebooks not created.
- Detached ORB path: no-traj now labeled `lost_track` (was mis-tagged `crash` for defocus sev5).

## Verification (2026-09-23)

```bash
pip/uv: .venv with `.[rig,dev]`
pytest   # 6 passed
python -m harness.orchestrator.run \
  --config harness/orchestrator/configs/smoke.yaml --clean-only
# ATE-RMSE ≈ 0.017–0.023 m on fr1/desk
```
