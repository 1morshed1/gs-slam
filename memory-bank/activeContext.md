# Active context

## Current focus

**Phase-0 Photo-SLAM bring-up in progress.** ORB-SLAM3 P0 + smoke already passed.

## GPU policy (2026-09-27)

**Always use GPU-1** (user directive). Do not use GPU-2 (or GPU-0).

- Containers: `--gpus device=1`; power sampler: `gpu_index=1`; wait script: `scripts/wait_gpu.sh` (default `GPU_INDEX=1`).
- GPU-1 is shared (other jobs present); `wait_gpu.sh` gates on free memory/util.

## Photo-SLAM status

- Build 1 failed on `FLT_MAX` (fixed: `<cfloat>` sed in `simple_knn.cu`).
- Build 2 failed: `opencv2/cudawarping.hpp` / `cudaimgproc.hpp` missing (apt OpenCV has no CUDA modules).
- Fix: Dockerfile builds OpenCV 4.10.0 + contrib from source (`WITH_CUDA`, `CUDA_ARCH_BIN=12.0`, dnn/cudacodec off).
- Build 3 died on a transient GitHub clone error → clone now retried 5×.
- Builds 4–5: libtorch 2.7 API drift, patched via sed in Dockerfile:
  - `c10::guts::to_string(param.unsafeGetTensorImpl())` → raw pointer (Adam state map is keyed by `void*` in torch 2.x; `std::to_string` would compile but break optimizer state lookup).
  - examples: `c10Alloc::Stat*` → `c10::CachingAllocator::Stat*`.
- **Image built (2026-09-28):** `harness/photo_slam:x86` (~17.8 GB).
- **P0 first run (2026-09-28, GPU-1 shared with another job at ~45% util; user OK'd memory-only gate `MAX_UTIL=100`):**
  - outcome `ok`, 573/573 poses, ~40 s wall.
  - ATE-RMSE **0.0626 m**, RPE trans 0.0124 m, RPE rot 0.59°.
  - Mapper: 2381 iters, keyframe PSNR mean **~18.0 dB**, DSSIM 0.67; GPU peak 1.1 GB.
  - Worse than ORB-SLAM3 on same seq (~2 cm) and likely below paper numbers (paper values not yet verified). Suspects: sequence ends → immediate shutdown so mapper gets few iters; single repeat; shared GPU.
  - Output: `runs/photo_slam_p0_fr1_desk/` (`p0_summary.json`, `2381_shutdown/` renders+PSNR).
- Script fixes: scheduler's build-alive check anchored to the real buildx process (was matching the launching shell); `wait_gpu.sh` CSV parsing fixed (was reading `free,util` as one value → never ready).

## Recent changes (2026-09-23)

- Restored missing `harness/datasets/` (`frame`, `feeder`, TUM loader).
- ORB-SLAM3 `supported_modalities` includes RGB-D; container `_invoke` with OPA-safe docker cp/exec + detached `rgbd_tum` (bind mounts blocked on this host).
- Implemented remaining corruption kernels + working `pregenerate`; smoke set under `datasets_corrupted/`.
- Wired `_build_stream`, `eval_accuracy` (evo), clean-only orchestrator path.
- Built `harness/orb_slam3:x86` @ commit `4452a3c4ab75b1cde34e5505a36ec3f9edcdc4c4`.

## P0 measurement (TUM `rgbd_dataset_freiburg1_desk`, RGB-D)

| Repeat | ATE-RMSE | Outcome |
|---|---|---|
| 0 | **0.0228 m** | ok |
| 1 | **0.0167 m** | ok |

In-family with published ORB-SLAM3 RGB-D fr1/desk (~1–2 cm).

## Active decisions

| Topic | Status |
|---|---|
| Modality | **Locked** — mono + RGB-D + stereo + VI |
| First SUT | **ORB-SLAM3** (P0 passed on rig) |
| Office GPU | **GPU-1** (`--gpus device=1`), always |
| Docker mounts | **Blocked by OPA** — adapter uses cp/exec + detached run |
| Jetson model / RAM / JetPack | **Open** |
| Power gear | **Open** — office `nvidia-smi` is context only |

## Next steps

1. ~~Optional: run full smoke matrix (corrupted cells)~~ **Done 2026-09-24** — see progress.md.
2. Phase-0 Photo-SLAM — **first run ok but ATE 6.3 cm**: verify paper fr1/desk ATE/PSNR, run repeats, check realtime feeding / mapper iteration budget before calling P0 pass/fail.
3. Decide Jetson + power gear → L4T + tegrastats.
4. Broader dataset acquisition (Replica / EuRoC / TartanAir) with disk budget.

## Considerations / watchouts

- Never treat office GPU joules as edge energy claims.
- Docker: prefer `docker buildx build --output type=docker` to load images; avoid `-v` on this box.
- Large local artifacts: `containers/orb_slam3/rootfs/`, `*.tar`, `datasets/`, `.venv/` (gitignored).
