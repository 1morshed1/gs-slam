# Active context

## Current focus

**Rig-first scaffold.** Harness skeleton exists: registries, matrix, energy integrate, a few real corruptions, nvidia-smi power backend, smoke config, scaffold tests. Phase-0 container/adapter bring-up not started.

## Recent changes (2026-09-22)

- Plan draft `edge-slam-energy-robustness-benchmark-plan.md` written.
- `harness/` package scaffolded end-to-end with stubs for Jetson/power-gear-dependent pieces.
- Locked: **modality scope = mono + RGB-D + stereo + VI** (all four).
- Memory bank + `CLAUDE.md` created for agent continuity.

## Active decisions

| Topic | Status |
|---|---|
| Modality | **Locked** — all four |
| Jetson model / RAM / JetPack | **Open** — gates GS/GFM feasibility |
| Power gear (onboard vs + external) | **Open** — scopes energy claims |
| Live camera vs dataset-replay | Prefer replay; live optional |
| Indoor vs outdoor/KITTI | Prefer indoor-first; KITTI stretch |
| Venue / timeline / effort | Open |

## Next steps

1. Phase-0: pick first SUT (likely ORB-SLAM3 or Photo-SLAM), Dockerfile.x86 + adapter `_invoke`, reproduce one paper number.
2. Flesh remaining corruption generators (low-light, exposure, dynamic patches, frame-drop, etc.).
3. Decide Jetson + power gear → unlock L4T containers + tegrastats backend.
4. Dataset acquisition on rig (Replica / TUM / EuRoC / TartanAir) with disk budget.

## Considerations / watchouts

- R1 `sm_120` CUDA build pain is expected to dominate early calendar.
- Shared box: GPU-1 only; Docker/disk hygiene.
- Do not treat office `nvidia-smi` GPU power as edge energy in paper claims.
- Fairness: group by modality; never fold PSNR into cross-family pose ranking.
