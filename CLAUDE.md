# CLAUDE.md — edge-slam-benchmark (`gs-slam`)

## Project

Energy + robustness benchmark harness for edge visual SLAM across **classical / GS / GFM** families. Plan: `edge-slam-energy-robustness-benchmark-plan.md`. Code: `harness/` package (`pyproject.toml` → `edge-slam-benchmark`).

Agent continuity: read **`memory-bank/`** at start of non-trivial work (`projectbrief` → `productContext` / `systemPatterns` / `techContext` → `activeContext` → `progress`). Update `activeContext.md` + `progress.md` after significant changes. On **"update memory bank"**, review all six files.

## Hard contracts (never break)

1. Adapters only: `FrameStream` in → **TUM trajectory** out (+ optional map). Eval ignores system internals.
2. Corruptions **pre-generated to disk**, seeded. No corruption inside measured energy loop.
3. Power sampler **out-of-process**; frame-boundary markers; merge by monotonic clock.
4. Every run writes a **manifest** to `store/`.
5. Crashes / timeouts / lost-track = **first-class outcomes**, not silent failures.
6. Office-rig GPU power ≠ edge energy claim. Jetson is DUT for energy/thermal paper numbers.

## Hardware

| Tier | Machine | Role |
|---|---|---|
| A | Office `vm-130-131`, Blackwell `sm_120`, **GPU-2 only** | Dev, corruptions, accuracy/quality reference, analysis |
| B | Jetson (model **TBD**) | Real J/frame, thermal, edge feasibility |

Rig rules: `CUDA_VISIBLE_DEVICES=2`, `TORCH_CUDA_ARCH_LIST=12.0`, pin torch `2.11.0+cu128`, patched GS rasterizers for `sm_120`.

## Locked / open

- **Locked:** modality = mono + RGB-D + stereo + VI.
- **Open:** Jetson model, power-measurement gear, venue/timeline.

## Layout cheat sheet

```
harness/adapters|datasets|corruptions|power|orchestrator|eval|store|analysis|containers
tests/test_scaffold.py
store/          # outputs gitignored
datasets/       # gitignored
```

SUTs (stubs in `adapters/systems.py`): classical `orb_slam3` `openvins`; gs `photo_slam` `gs_icp_slam` `monogs` `splatam`; gfm `mast3r_slam` `vggt_slam`.

## Commands

```bash
pip install -e ".[rig,dev]"
pytest
python -m harness.orchestrator.run --config harness/orchestrator/configs/smoke.yaml
```

## Working style for this repo

- Prefer surgical changes; don't "improve" adjacent stubs.
- Fill behind existing interfaces (`SLAMAdapter`, power backends, corruption registry) — don't invent parallel APIs.
- Phase-0 gate: reproduce paper headline on ≥1 sequence before adding a system to the grid; drop with written justification otherwise.
- Fairness: group by modality; report render metrics (PSNR/SSIM/LPIPS) separately from pose ranking.
- Large data paths stay gitignored (`datasets/`, `datasets_corrupted/`, `runs/`, `store/*.sqlite`).

## Phases (see plan §11)

P0 bring-up → P1 power infra → P2 clean baseline → P3 robustness → P4 analysis/paper → P5 artifact. **P0 dominates** (`sm_120` + later L4T).

## Caveman / memory

If user enables caveman mode, keep technical terms exact (API names, paths, error strings). Memory-bank prose stays readable for humans; compress only when user asks (`caveman-compress`).
