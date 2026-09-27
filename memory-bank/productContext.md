# Product context

## Why it exists

Prior art covers SLAM energy (SLAMBench2, Jetson ORB studies, Orin VIO/SLAM power) and fragments of robustness. Gap: **head-to-head** of classical + GS-SLAM + GFM-SLAM on **energy AND robustness-under-degradation, jointly, on current edge silicon**, including first systematic edge-energy profile of GFM-SLAM (MASt3R/VGGT lineage).

## Problems it solves

- Fair cross-family compare needs one I/O + eval contract (TUM traj, shared frame feed).
- Energy numbers polluted if corruption/generation runs inside measured loop → pre-generate corruptions.
- Conflicting CUDA/torch/rasterizer stacks → one container per SUT.
- Jetson vs office rig roles must stay separate or energy claims become unpublishable.

## How it should work (user journey)

1. **Dev/rig:** generate datasets + corruptions, build adapters/containers, sanity-check accuracy on `vm-130-131` (GPU-1, Blackwell `sm_120`).
2. **Measure:** replay fixed-rate frames on Jetson; power daemon samples with frame markers; orchestrator runs config-as-code matrix, resumes, records crashes/timeouts/lost-track as outcomes.
3. **Eval:** evo ATE/RPE; optional PSNR/SSIM/LPIPS for renderers; energy integrate from power log; thermal parse.
4. **Analyze:** notebooks read `store/` only — Pareto, severity curves, power-mode sweep, thermal sustained.

## Experience goals

- Reproducible: pinned commits, seeds, per-run manifests.
- Honest: modality fairness grouping; map quality never mixed into pose ranking; onboard-only power scoped as module-rail if no external meter.
- Crash = data: lost-track / timeout / OOM are first-class results.
