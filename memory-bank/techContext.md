# Tech context

## Stack

| Layer | Choice |
|---|---|
| Language | Python ≥3.10 |
| Package | `edge-slam-benchmark` via setuptools (`harness*`) |
| Core deps | numpy, pyyaml |
| Rig extras (`[rig]`) | opencv-headless, pillow, evo, scikit-image, lpips, pandas, pyarrow |
| Dev | pytest |
| Persist | sqlite + parquet under `store/` (gitignored outputs) |
| Containers | Docker; x86 first, L4T (`nvcr.io/nvidia/l4t-*`) deferred |

## Development setup

```bash
# editable install
pip install -e ".[rig,dev]"

# smoke
pytest
python -m harness.orchestrator.run --config harness/orchestrator/configs/smoke.yaml
```

## Office-rig constraints (Blackwell)

- `CUDA_VISIBLE_DEVICES=1` (shared box, GPU-1 only).
- `TORCH_CUDA_ARCH_LIST="12.0"` for custom CUDA.
- Pin torch to working `2.11.0+cu128`; never let blind `pip install` downgrade.
- GS rasterizers: prefer `sm_120`-patched `diff-gaussian-rasterization` forks.
- Disk pressure: datasets + Docker images large — track usage (plan §4A / R8).

## Jetson (deferred)

- Rebuild for aarch64 + JetPack CUDA; x86 images do not port.
- Power: `tegrastats` / jtop INA3221 rails (+ optional external meter).
- Feasibility depends on Orin tier (AGX 64GB ideal for three-family story).

## Systems registered

| Family | Names | Rig status |
|---|---|---|
| classical | `orb_slam3`, `openvins` | **orb_slam3 P0 pass**; openvins stub |
| gs | `photo_slam`, `gs_icp_slam`, `monogs`, `splatam` | stubs |
| gfm | `mast3r_slam`, `vggt_slam` (stretch) | stubs |

ORB image: `harness/orb_slam3:x86` @ `4452a3c4…`. Host OPA blocks `-v`; adapter uses docker cp/exec + detached `rgbd_tum`.

Photo-SLAM image: `harness/photo_slam:x86` @ `f8bfb2f0…` — CUDA 12.8.1 devel, torch 2.7.1 cu128, OpenCV 4.10.0 + contrib (CUDA, `sm_120`) from source, arch list patched to `75;86;120`.

## Datasets

- On disk: TUM `rgbd_dataset_freiburg1_desk` under `datasets/tum/`.
- Smoke corruptions pre-generated under `datasets_corrupted/tum/...`.
- Planned next: Replica, EuRoC, TartanAir (± Bonn/OpenLORIS/KITTI stretch).
