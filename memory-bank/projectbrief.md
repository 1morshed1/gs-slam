# Project brief

## What this is

**edge-slam-benchmark** (`gs-slam` repo): unified measurement harness for comparing visual SLAM families on **energy + robustness** on edge hardware (Jetson), with development/reference runs on an office Blackwell GPU rig.

Working paper title direction: *"Joules, Not Just Frames"* — classical vs 3D-Gaussian-Splatting (GS) vs geometric-foundation-model (GFM) SLAM, jointly on accuracy × energy × robustness.

## Goals

1. Run 3–5 systems across **classical / GS / GFM** through a parameterized perturbation suite.
2. Log accuracy, latency, peak memory, energy (J/frame, J/keyframe), thermal behaviour under reproducible conditions.
3. Deliver measurement paper + open artifact (harness, corrupted-dataset generators, raw logs, analysis notebooks).

## Non-goals (for now)

- Novel SLAM algorithm.
- Claiming energy or robustness are unmeasured in literature (position on the *joint* three-family edge gap).
- Treating office-rig GPU joules as edge energy claims.

## Success looks like

- Phase-0: each kept SUT reproduces a paper headline number on ≥1 sequence (rig + eventually Jetson).
- Clean baseline Pareto (accuracy × energy) with CIs.
- Degradation curves + robustness-normalized energy.
- Claims traceable to `store/` manifests + derived metrics.

## Source of truth

- Plan: `edge-slam-energy-robustness-benchmark-plan.md` (v0.1 draft).
- Code package: `harness/` (`pyproject.toml` name `edge-slam-benchmark`).
