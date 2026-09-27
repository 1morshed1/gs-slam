# containers/ — one image per system-under-test (plan §10)

Each SUT gets its own Docker image because CUDA/torch/rasterizer deps conflict — this is
the `sm_120` landmine writ large (plan §12 R1). Isolation also stabilizes energy runs.

## Layout (create per system during Phase 0)

```
containers/<system>/
├─ Dockerfile.x86      # office rig (Blackwell sm_120). Pin torch 2.11.0+cu128.
├─ Dockerfile.l4t      # Jetson aarch64 — TODO, needs Jetson tier (plan §14.1)
├─ adapter.py          # entrypoint: reads mounted frame dir → writes TUM traj
├─ commit.lock         # exact upstream commit (plan §3.4)
└─ README.md           # build/run notes, known sm_120 fixes
```

## x86 build rules (office rig, plan §4A / §12 R1)

- `TORCH_CUDA_ARCH_LIST="12.0"` for Blackwell.
- Use `sm_120`-patched rasterizer forks for GS systems (`diff-gaussian-rasterization`).
- Keep torch pinned to the working `2.11.0+cu128`; a blind `pip install` must never
  downgrade it.
- `CUDA_VISIBLE_DEVICES=1` (GPU-1 only) — shared box.

## L4T (Jetson) — deferred

Base images: `nvcr.io/nvidia/l4t-*`. Software rebuilt for aarch64 + JetPack CUDA; x86
images do NOT port. Blocked on the Jetson model decision (plan §14.1).

## Systems (from adapters/systems.py)

classical: `orb_slam3`, `openvins`
gs:        `photo_slam`, `gs_icp_slam`, `monogs`, `splatam` (known-slow ceiling)
gfm:       `mast3r_slam`, `vggt_slam` (stretch)

Phase-0 gate (plan §11): each kept system must reproduce its paper's headline number on
≥1 sequence before it enters the grid. Drop with written justification otherwise.
