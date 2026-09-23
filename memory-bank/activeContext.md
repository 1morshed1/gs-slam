# Active context

## Current focus

**Phase-0 ORB-SLAM3 gate passed on office rig.** Harness foundations restored; TUM fr1/desk downloaded; smoke corruptions pre-generated; ORB-SLAM3 container built; clean matrix cells run end-to-end with ATE.

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
| Office GPU | **GPU-2** (`CUDA_VISIBLE_DEVICES=2`) |
| Docker mounts | **Blocked by OPA** — adapter uses cp/exec + detached run |
| Jetson model / RAM / JetPack | **Open** |
| Power gear | **Open** — office `nvidia-smi` is context only |

## Next steps

1. Optional: run full smoke matrix (corrupted cells) once clean gate is trusted.
2. Phase-0 next SUT (Photo-SLAM) — expect `sm_120` pain.
3. Decide Jetson + power gear → L4T + tegrastats.
4. Broader dataset acquisition (Replica / EuRoC / TartanAir) with disk budget.

## Considerations / watchouts

- Never treat office GPU joules as edge energy claims.
- Docker: prefer `docker buildx build --output type=docker` to load images; avoid `-v` on this box.
- Large local artifacts: `containers/orb_slam3/rootfs/`, `*.tar`, `datasets/`, `.venv/` (gitignored).
