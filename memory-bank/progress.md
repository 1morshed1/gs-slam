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
| Containers | **`harness/orb_slam3:x86` built**; L4T deferred |
| Analysis notebooks | README only |

## Phase status

| Phase | Goal | State |
|---|---|---|
| **P0** Bring-up | Reproduce headline on ≥1 sequence | **ORB-SLAM3 on rig: PASS** (ATE ~1.7–2.3 cm fr1/desk). Other SUTs not started. Jetson TBD. |
| **P1** Measurement infra | Power sync, idle baselines | Partial (rig GPU backend only) |
| **P2** Clean baseline | Uncorrupted grid → Pareto | Unblocked for ORB only |
| **P3** Robustness sweep | Perturbation × severity | Generators ready; corrupted ORB runs optional next |
| **P4** Analysis & write-up | Notebooks + paper | Placeholders |
| **P5** Artifact release | Public harness + data | Later |

## Known issues / blockers

- Host OPA blocks `docker run -v`; adapter workaround required.
- Jetson model TBD → L4T images + edge feasibility unknown.
- External power meter TBD → claim scope undecided.
- GS/GFM containers not started (`sm_120` risk).
- Analysis notebooks not created.

## Verification (2026-09-23)

```bash
pip/uv: .venv with `.[rig,dev]`
pytest   # 6 passed
python -m harness.orchestrator.run \
  --config harness/orchestrator/configs/smoke.yaml --clean-only
# ATE-RMSE ≈ 0.017–0.023 m on fr1/desk
```
