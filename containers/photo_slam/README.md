# Photo-SLAM container (Phase 0 GS)

## Build (office rig, GPU-1 / sm_120)

```bash
COMMIT=f8bfb2f0809c003ccc3fd577dc43c576fcafa4ac
docker buildx build \
  -f containers/photo_slam/Dockerfile.x86 \
  --build-arg PHOTO_SLAM_COMMIT="$COMMIT" \
  --output type=docker,name=harness/photo_slam:x86 \
  -t harness/photo_slam:x86 \
  containers/photo_slam
```

Notes:
- Patches `CUDA_ARCHITECTURES` to include `120` (Blackwell).
- Torch via pip `2.7.1+cu128`; `TORCH_CUDA_ARCH_LIST=12.0`.
- Host OPA blocks `-v`; harness uses docker cp/exec (same as ORB).

## P0 gate

TUM `rgbd_dataset_freiburg1_desk` RGB-D → `CameraTrajectory_TUM.txt` → evo ATE.
Paper numbers are typically reported on Replica; fr1/desk is the harness smoke sequence for cross-SUT compare.

## GPU waiter

```bash
scripts/wait_gpu.sh && scripts/run_photo_slam_p0.sh
```
