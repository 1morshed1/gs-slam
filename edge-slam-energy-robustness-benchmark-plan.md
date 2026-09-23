# Energy-first + Robustness Benchmark for Edge Visual SLAM — Project Plan (v0.1)

> **Status:** Draft pending answers to the *Open Decisions* section (§15). Several choices below branch on your **Jetson model** and **power-measurement gear**; those branches are flagged inline with ⚠️.
>
> **Working title:** *"Joules, Not Just Frames: An Energy- and Robustness-First Benchmark of Classical, Gaussian-Splatting, and Foundation-Model Visual SLAM on Edge Hardware."*

---

## 1. Executive summary

We build a **unified measurement harness** that runs 3–5 visual-SLAM systems drawn from three distinct algorithmic families — **classical**, **3D-Gaussian-Splatting (GS-SLAM)**, and **geometric-foundation-model (GFM-SLAM)** — through a **parameterized perturbation suite** on **real edge hardware (Jetson)**, logging **accuracy, latency, peak memory, energy-per-frame / per-keyframe, and thermal behaviour** under controlled, reproducible conditions.

The deliverable is a **measurement paper + open artifact** (harness, corrupted-dataset generators, raw logs, analysis notebooks). The core intellectual contribution is not any single number but the **joint characterization of the accuracy ↔ energy ↔ robustness trade-off across families that have never been compared this way on the edge**, plus the first edge-energy profile of foundation-model SLAM.

### Why it's publishable (honest positioning)
- Energy *has* been measured for SLAM before (SLAMBench2; a 2019 ORB-SLAM2 Jetson power study; a recent AGX-Orin study of RDS-SLAM/VDO-SLAM/DeepVO; DL-VINS-Factory 2026 for learned VIO front-ends). **We do not claim energy is unmeasured.**
- Robustness benchmarks for SLAM also exist in fragments (illumination/dynamic-scene datasets, corruption studies).
- **The gap we fill:** a *head-to-head* of the **three modern families** on **energy AND robustness-under-degradation, jointly, on current edge silicon**, with the **first systematic edge-energy characterization of GFM-SLAM** (MASt3R-SLAM / VGGT-SLAM lineage). This is differentiated and low-risk because it leans on measurement discipline rather than a novel algorithm.

---

## 2. Research questions & hypotheses

**RQ1 (energy).** What is the energy cost — J/frame, J/keyframe, and *energy-to-reach-an-accuracy-threshold* — of each family on edge hardware, and how does it decompose (tracking vs. mapping; CPU vs. GPU rails)?

**RQ2 (robustness).** How does accuracy degrade as a function of perturbation *type* and *severity* (motion blur, low light, exposure change, dynamic objects, noise, compression), and how does that degradation slope differ across families?

**RQ3 (joint trade-off).** Where does each system sit on the **accuracy × energy × robustness** Pareto surface? Is there a family that is Pareto-dominated on the edge? Is "photorealistic map quality" (GS/GFM) worth its energy multiplier for pose accuracy alone?

**RQ4 (edge feasibility).** *Can* GS-SLAM and GFM-SLAM even run within the Jetson's memory/thermal envelope in real time, and what is the **energy penalty of quality** (dense/photorealistic map) versus classical sparse pose estimation?

**RQ5 (operating point).** How do Jetson **power modes (`nvpmodel`)** and **clock locking (`jetson_clocks`)** move each system on the energy–latency–accuracy surface? Is the "max clocks" default actually the most energy-efficient per completed frame?

**Working hypotheses (to be confirmed/refuted — refutation is fine and still publishable):**
- H1: Classical methods dominate the energy-per-accurate-pose frontier; GS/GFM buy map quality at a large (≥5–10×) energy premium.
- H2: GFM-SLAM is the most *robust* to appearance degradation (learned priors) but the *least* energy-efficient and may not fit the edge memory/thermal budget in real time.
- H3: Within GS-SLAM, edge-viability spans >30× in throughput (e.g., keyframe-based Photo-SLAM/GS-ICP vs. per-frame SplaTAM), so "GS-SLAM" must be treated as a spectrum, not a point.
- H4: Ranking by fps and ranking by J/frame **disagree**, because thermal throttling and idle/leakage power reshape the picture under sustained load.

---

## 3. System-under-test (SUT) selection

Pick **1–2 systems per family** for the core grid; keep 1–2 more as "stretch" targets. Final list depends on ⚠️ **Jetson tier** (§5) and modality scope (§15).

| Family | Candidate systems | Input | Map type | Edge reality (from literature) |
|---|---|---|---|---|
| **Classical (sparse/direct)** | **ORB-SLAM3** (primary), DSO / SVO, **OpenVINS** or **VINS-Fusion** (if VI in scope), Stereo **Jetson-SLAM** | mono / stereo / RGB-D / VI | sparse points | Real-time on Jetson; low power (single-digit–low-tens W). Baseline anchor. |
| **GS-SLAM** | **Photo-SLAM** (primary, runs live on AGX Orin), **GS-ICP SLAM** (RGB-D, fast), **MonoGS** (heavy, mono, per-quality), *SplaTAM* (very slow on edge — include as "quality/energy ceiling") | mono / stereo / RGB-D | 3D Gaussians | Huge spread: keyframe methods ~30 fps on AGX Orin; SplaTAM <1 fps, GS-SLAM ~2 fps on Orin-NX-class. MemGS targets Jetson memory. |
| **GFM-SLAM** | **MASt3R-SLAM** (primary), **VGGT-SLAM** (stretch), *MASt3R-Fusion* (VI, stretch) | mono RGB (calib-free) | dense pointmaps | Real-time on **desktop** GPUs; **edge feasibility unknown → this is a headline result.** Expect fp16/int8, reduced resolution, or "does not fit." |

**Selection principles**
1. **Prefer maintained, open-source repos with reproducible headline numbers.** Reproducing each paper's own number on one sequence is the Phase-0 gate.
2. **Match modality deliberately.** Comparing a mono method against an RGB-D method on ATE is only fair within-modality; group comparisons and state depth availability explicitly. (See fairness caveats, §13.)
3. **Include at least one "known-slow" GS system** on purpose — the energy-to-completion of a 0.8 fps method is a compelling data point, even off the real-time frontier.
4. **Freeze exact commits** and record them in the run manifest.

---

## 4. Hardware roles — a two-tier design

You have two very different machines. Their roles are **not** interchangeable, and conflating them is the fastest way to an unpublishable energy claim.

### Tier A — Office rig `vm-130-131` (Blackwell, `sm_120`, GPU-2 only)
**Role: development, dataset/perturbation generation, accuracy ground-truth, quality (PSNR/SSIM/LPIPS) upper bound, feasibility ("does it build/run"), and analysis.**
- **Not** the primary energy device. It's a shared KVM guest; `nvidia-smi` reports **GPU-only** power (not CPU/system), and datacenter-GPU joules are not "edge." At most it yields a *coarse relative* server-class energy point for context — clearly labelled as such.
- 96 GiB VRAM makes it the place to run the *reference* tier of heavy GS/GFM systems at full resolution to get "best-case accuracy/quality" numbers the Jetson results are compared against.
- ⚠️ **Blackwell `sm_120` is the hard part.** GS rasterizers (`diff-gaussian-rasterization`), DROID/lietorch-style custom ops, and MASt3R/VGGT kernels frequently fail to compile on brand-new arches. Budget real time here (§13, Risk R1). Mitigations: `TORCH_CUDA_ARCH_LIST="12.0"`, use `sm_120`-patched rasterizer forks, keep torch pinned to your working `2.11.0+cu128`, never let a blind `pip install` downgrade torch.
- **Shared-box hygiene:** GPU-2 only (`CUDA_VISIBLE_DEVICES=2`); watch disk — the box was recently near-full and Docker already holds ~200 GiB. GS/foundation datasets (Replica, ScanNet++, TartanAir) + per-system images will add tens–hundreds of GiB. Reserve/track disk in Phase 0.

### Tier B — Jetson (the *actual* device-under-test) ⚠️ model TBD
**Role: the real edge measurements — J/frame, J/keyframe, latency, peak memory, thermal throttling, sustained vs. burst.** This is the heart of the paper.
- aarch64 + JetPack/L4T with its own CUDA — **software must be rebuilt for Jetson**; do not assume x86 images port. Use `nvcr.io/nvidia/l4t-*` base images.
- Feasibility depends heavily on tier:
  - **AGX Orin 64GB (ideal):** GS-SLAM viable; GFM-SLAM *maybe* (quantized/reduced res). Enables the full three-family story.
  - **Orin NX 8/16GB:** GS-SLAM constrained (keyframe methods only); GFM-SLAM likely infeasible → still a result.
  - **Orin Nano 8GB / Xavier:** classical + light GS only; GFM out.
- **No camera on the office rig** → the credible, reproducible path is **dataset replay** on the Jetson (frames fed at a controlled rate), optionally cross-checked with a live RealSense/OAK sequence if you have one.

---

## 5. Datasets & sequences

Choose a compact set that spans modality, indoor/outdoor, synthetic/real, and *native* degradation, so the perturbation suite (§7) layers on top cleanly.

| Dataset | Modality | Why included | Native challenge factors |
|---|---|---|---|
| **Replica** | RGB-D (synthetic) | Standard GS/NeRF-SLAM benchmark; GT mesh → clean PSNR/recon | photorealistic, controlled |
| **TUM RGB-D** (fr1/fr2/fr3) | RGB-D | Classic pose benchmark; **has dynamic sequences** (walking/sitting) | dynamic objects, texture/illumination variants |
| **EuRoC MAV** | stereo + IMU | VI methods; **fast motion / motion blur** natively | fast motion, exposure |
| **TartanAir** | mono/stereo (synthetic) | Rich hard conditions; great for degradation curves | weather, lighting, dynamic, hard motion |
| *(stretch)* **Bonn Dynamic RGB-D** / **OpenLORIS-Scene** | RGB-D | Explicit real-world dynamic + illumination challenge splits | dynamic, lighting, real robot |
| *(if outdoor in scope)* **KITTI** | stereo | Driving, outdoor scale | scale, dynamic traffic |

Recommendation for a first paper: **Replica + TUM RGB-D + EuRoC + TartanAir** (covers RGB-D, stereo-VI, mono, synthetic control + real). Pick ~3 sequences each → ~12 base sequences.

---

## 6. Perturbation / degradation suite (a core contribution)

Model this on **ImageNet-C-style severity levels** so every perturbation is *parameterized* and *reproducible*, yielding **accuracy-vs-severity curves** per system that you then cross with energy.

**Design rules**
- **Pre-generate** corrupted sequences to disk (deterministic seeds). Never pay corruption cost inside the measured loop — it would pollute energy numbers.
- Each perturbation has **severity ∈ {1..5}** with documented parameter ranges.
- Keep an **uncorrupted control** (severity 0) for every sequence.
- Apply photometric corruptions **after** any linear→sRGB handling consistent with the sensor model; document the pipeline.

| Perturbation | Parameterization (sev 1→5) | Notes |
|---|---|---|
| **Motion blur** | linear/kernel length scaled by inter-frame pose velocity; or fixed kernel px 3→31 | physically-motivated variant uses GT pose deltas |
| **Low light / underexposure** | gain/gamma reduction + sensor-model Poisson-Gaussian noise | pair darkening with realistic read/shot noise |
| **Exposure change / auto-exposure artifacts** | sudden gain step, over/under-exposure ramps, clipping | tests photometric front-ends |
| **Dynamic objects** | use native dynamic splits; *and* synthetic moving-patch insertion for controlled severity | separates "appearance" vs. "geometry" robustness |
| **Sensor noise** | Gaussian/Poisson σ increasing | classic corruption |
| **Compression / bitrate** | JPEG quality 90→10; or H.264 CRF sweep | matters for real deployments |
| **Defocus / blur** | Gaussian blur radius | complements motion blur |
| **Resolution / frame drops** | downscale factor; drop k% frames | stresses tracking continuity |
| *(stretch)* **Rolling shutter** | simulated readout skew | for completeness |

**Analysis artifacts:** per-system **degradation slope**, **area-under-accuracy-vs-severity**, **failure/lost-track rate**, and **recovery** after a transient corruption burst.

---

## 7. Metrics (exact definitions)

**Accuracy (pose-centric, cross-family fair):**
- **ATE-RMSE** (aligned trajectory error), **RPE** (translational/rotational drift) — via `evo`.
- **Failure/lost-track rate**: fraction of frames with no valid pose; define a lost-track detector (e.g., tracker reports failure or ATE spike beyond threshold).

**Map/render quality (only for methods that render — GS, some GFM):**
- **PSNR / SSIM / LPIPS** on held-out views; **reconstruction error** vs. GT mesh where available (Replica). Reported *separately* — never mixed into the cross-family pose ranking.

**Latency / throughput:**
- per-frame ms (p50/p95), **tracking vs. mapping breakdown**, throughput fps, **real-time factor** (fps ÷ sequence fps).

**Memory:** peak host RAM, peak VRAM (Jetson unified memory: report the unified peak and, if possible, GPU vs. CPU attribution).

**Energy (the headline axis):**
- **J/frame** and **J/keyframe** (integrate power over the per-item processing window).
- **Energy-to-solution**: total J to process a sequence *and reach an accuracy threshold* (penalizes slow/inaccurate methods fairly).
- **Average power (W)**, **Energy-Delay Product (EDP = energy × latency)**.
- **Dynamic energy** = total − idle-baseline (task-attributable), reported alongside total.
- **Rail decomposition**: CPU vs. GPU vs. SoC/system where sensors allow.

**Thermal / sustained:**
- peak temps, **throttle events**, **sustained-vs-burst** performance (thermal-soak test: run long enough to hit steady state), performance decay curve.

**Robustness (derived, §6):** degradation slope, AUC, failure rate vs. severity, **robustness-normalized energy** = energy per *successfully tracked* frame.

---

## 8. Measurement methodology (the rigor that makes it publishable)

This section is what a reviewer will scrutinize. Nail it before collecting real data.

**Power sensing — two sources, cross-checked:**
1. **Onboard rails** via `tegrastats` / `jtop` (jetson-stats) reading the INA3221 monitors (e.g., `VDD_GPU_SOC`, `VDD_CPU_CVB`, `VIN_SYS_5V0`). Document *which module* and *which rails*, and the sampling rate (INA3221 update rate is limited — typically ~ tens of Hz; state it).
2. ⚠️ **External ground-truth power** at the barrel jack / wall, if you have the gear: a **Monsoon HV monitor**, an **INA226 shunt + logger**, or a **bench power analyzer / programmable load**. This captures **full-system** draw (SoC + carrier + PMIC losses + peripherals) that onboard rails miss, and validates the onboard numbers. *If you only have onboard sensors, we scope the claim to module-rail energy and say so explicitly.*

**Time alignment (the tricky engineering bit):**
- Emit a **frame-boundary marker** into the power log (shared monotonic clock, or a GPIO/serial pulse for the external meter) so power can be integrated over each frame/keyframe window. Validate alignment on a synthetic known-duration load before trusting SLAM numbers.

**Controlled conditions (fix or sweep, never leave floating):**
- **Power mode**: fix `nvpmodel` for the main grid; additionally **sweep modes** as an explicit variable for RQ5.
- **Clocks**: `jetson_clocks` locked (or documented as unlocked) — pick one and be consistent per experiment.
- **Fan/cooling**: fixed fan curve; **thermal steady-state** reached before measuring (warm-up + soak). Randomize run order to avoid thermal drift confounding system comparisons.
- **Input feed**: replay frames at a **fixed rate decoupled from camera**; identical resolution and preprocessing across systems.
- **Repeats**: ≥ **3–5** per cell; report **mean ± std / 95% CI**. GS/learned methods are nondeterministic → repeats are mandatory.
- **Idle baseline**: measure board idle (and idle-with-datasets-loaded) for dynamic-energy subtraction.

**Validation before the real campaign:** run a **repeatability study** (same config ×10) to quantify measurement noise, and a **sanity load** (matmul of known FLOPs) to confirm the energy pipeline reports physically sensible joules.

---

## 9. Experimental matrix & sizing

Full cross-product is intractable; prune deliberately.

**Full grid (illustrative):**
`systems (5) × sequences (12) × perturbations (6) × severities (5) × repeats (3) ≈ 5,400 runs` — too big.

**Pruning strategy (staged):**
1. **Clean baseline grid** (severity 0): `5 × 12 × 3 ≈ 180 runs` → already a full result (Phase 2).
2. **Robustness grid on a representative subset**: 2 sequences/dataset × all perturbations × all severities × 3 repeats, only for systems that survive Phase 0. Keep a **coarse grid** (sev {1,3,5}) over the full system set, and a **fine grid** (sev {1..5}) on a representative subset.
3. **Power-mode sweep (RQ5)** on 1 sequence × all systems × N modes.
4. Skip modality-incompatible cells (don't run RGB-D-only methods on mono-only sequences); log skips explicitly.

Track the matrix as **config-as-code** so the orchestrator can resume, retry, and report coverage.

---

## 10. Software harness architecture

```
harness/
├─ containers/            # one Docker image per SUT (x86 + L4T variants), pinned commits
├─ adapters/              # per-system I/O adapter: dataset in → TUM-format traj + map out
├─ datasets/             # loaders + controlled frame-feeder (fixed-rate replay)
├─ corruptions/           # parameterized perturbation generators (pre-generate to disk)
├─ power/                 # power daemon: onboard (tegrastats/jtop) + external meter, timestamped
├─ orchestrator/          # runs the matrix, handles crashes/timeouts/lost-track, resumable
├─ eval/                  # evo (ATE/RPE), PSNR/SSIM/LPIPS, energy integration, thermal parse
├─ analysis/              # notebooks: Pareto frontiers, degradation curves, stats
└─ store/                 # tidy schema (parquet/sqlite): raw logs + derived metrics + manifest
```

**Key design choices**
- **Containerize per system** — non-negotiable given conflicting CUDA/torch/rasterizer deps (this is exactly your `sm_120` landmine writ large). Isolation also stabilizes energy runs.
- **Standard I/O contract**: every adapter consumes the same frame stream and emits **TUM-format** trajectories + optional map, so eval is uniform.
- **Pre-generated corruptions** keep the measured loop pure.
- **Power daemon runs out-of-process**, writing a timestamped log with frame markers; orchestrator merges by timestamp.
- **Crash/timeout/lost-track handling** as first-class outcomes (they *are* results, not errors).
- **Reproducibility**: pinned images, seeds, config-as-code, a per-run manifest capturing driver/CUDA/torch/bitsandbytes versions and exact commits (mirrors your existing EXP-logging discipline).

---

## 11. Phased plan & milestones

| Phase | Goal | Exit criterion |
|---|---|---|
| **P0 — Bring-up & compatibility** | Build/run each SUT on **office rig** *and* **Jetson**; reproduce each paper's headline number on 1 sequence | Every kept system produces a sane trajectory on ≥1 sequence on both tiers; `sm_120` and L4T build issues resolved or system dropped with justification |
| **P1 — Measurement infra** | Power sync harness (onboard + external), idle baselines, repeatability + sanity-load validation | Energy pipeline reproduces a known load to within a stated tolerance; repeatability CI quantified |
| **P2 — Clean baseline benchmark** | Accuracy/latency/memory/energy/thermal on uncorrupted datasets | Full clean grid collected with CIs; first Pareto plot (accuracy × energy) |
| **P3 — Robustness sweep** | Perturbation × severity grid (the novelty) | Degradation curves + robustness-normalized energy for all surviving systems |
| **P4 — Analysis & write-up** | Pareto surfaces, power-mode sweep, thermal/sustained study, paper | Draft with all figures; claims traceable to raw logs |
| **P5 — Artifact release** | Harness + corrupted-dataset generators + raw logs + notebooks | Reproducible artifact; README + one-command re-run of a representative cell |

*Timeline in weeks depends on effort (§15). Realistically P0 dominates — budget generously for `sm_120`/L4T pain.*

---

## 12. Risks & mitigations

| # | Risk | Likelihood | Mitigation |
|---|---|---|---|
| **R1** | GS/GFM custom CUDA won't build on Blackwell `sm_120` | **High** | `TORCH_CUDA_ARCH_LIST=12.0`; use `sm_120`-patched rasterizer forks; keep torch `2.11+cu128` pinned; treat office rig as *reference/quality* tier and lean on Jetson (`sm_87`, more mature) for the heavy systems if needed |
| **R2** | GFM-SLAM (VGGT/MASt3R) OOMs or is sub-real-time on Jetson | **High** | fp16/int8, reduced resolution, chunked inference; report "infeasible / X J-per-frame at Y fps" as a *finding*, not a failure |
| **R3** | Power measurement mis-synced → wrong J/frame | Med | validate against synthetic known load first; dual-source cross-check; frame-boundary markers |
| **R4** | Onboard-only power under-captures system energy | Med | scope claim to module rails explicitly; acquire external meter if possible (⚠️ §15) |
| **R5** | Modality mismatch → unfair comparison | Med | group by modality; state depth availability; never mix into one ranking |
| **R6** | Thermal drift confounds cross-system comparison | Med | steady-state before measuring; randomized run order; report sustained + burst |
| **R7** | Baseline repos finicky / unreproducible | Med-High | Phase-0 gate reproduces each paper's number before inclusion; drop with justification if not |
| **R8** | Shared office box: disk/Docker pressure, GPU contention | Med | GPU-2 pinned; track disk; schedule around your VLA workload |
| **R9** | Scope creep (matrix explosion) | Med | staged pruning (§9); clean baseline is already a paper-worthy result |

---

## 13. Deliverables & artifact

1. **Paper** (measurement/benchmark venue) — see §15 for target.
2. **Open harness** (containers, adapters, orchestrator, power daemon).
3. **Corrupted-dataset generators** (parameterized, seeded) — reusable beyond this paper.
4. **Raw + derived data** (energy/thermal/accuracy logs) with schema.
5. **Analysis notebooks** reproducing every figure.
6. **Reproducibility manifest** (versions/commits/configs per run).

---

## 14. Open decisions (need your input to finalize)

These materially change the plan; the first two change it the most.

1. ⚠️ **Which Jetson exactly** (model + RAM + JetPack/L4T version)? This gates whether GS-SLAM and especially GFM-SLAM are feasible, and thus the whole three-family framing.
2. ⚠️ **Power-measurement gear:** onboard INA3221 only, or do you also have an **external meter** (Monsoon / INA226 shunt / bench analyzer)? Determines whether energy claims are "module-rail" or "full-system."
3. **Modality scope:** mono only? RGB-D? stereo? visual-inertial? (Affects fairness grouping and which classical baseline: ORB-SLAM3 vs. OpenVINS/VINS-Fusion.)
4. **Live camera or dataset-replay only?** (I recommend replay for reproducibility; live is an optional cross-check if you have a RealSense/OAK.)
5. **Indoor only, or outdoor/driving (KITTI) in scope?**
6. **Target venue + deadline + effort** (solo? how many months? paper vs. thesis chapter vs. course project?). Drives matrix pruning and phase depth.
7. **Any must-include systems** you already care about (or already have building)?
8. **Current state on the office rig:** anything SLAM-related building yet, or is it fresh alongside the OpenVLA env?

---

## 15. References (for positioning; verify latest versions)

*Energy / benchmarking prior art:*
- SLAMBench2: Multi-Objective Head-to-Head Benchmarking for Visual SLAM — arXiv:1808.06820
- Evaluating the Power Efficiency of Visual SLAM on Embedded GPU Systems (ORB-SLAM2, Jetson Nano/TX2/Xavier), 2019
- Challenges and Performance of SLAM Algorithms on Resource-constrained Devices (RDS-SLAM/VDO-SLAM/DeepVO, AGX Orin 64GB, incl. energy) — riverpublishers
- DL-VINS-Factory: Learned Visual Front-Ends in VI-SLAM (Jetson power) — arXiv:2607.01757
- SLAMBooster (energy-per-frame control, ODROID) — arXiv:1811.01516
- SLAM Hive Benchmarking Suite

*GS-SLAM & edge:*
- Photo-SLAM (CVPR 2024) — runs live on Jetson AGX Orin (mono/stereo/RGB-D)
- SplaTAM (CVPR 2024); MonoGS (CVPR 2024); GS-ICP SLAM; RTG-SLAM
- MemGS: Memory-Efficient Gaussian Splatting for Real-Time SLAM (Jetson AGX Orin)
- Edge throughput data points (SplaTAM ~0.78 fps, GS-SLAM ~2.34 fps, MonoGS mapping 3–5 fps on Orin-class): RTGS (MICRO'25, arXiv:2510.06644), REACT3D (MICRO'25)
- Awesome-3DGS-SLAM list — github.com/KwanWaiPang/Awesome-3DGS-SLAM

*GFM-SLAM (geometric foundation models):*
- MASt3R-SLAM: Real-Time Dense SLAM with 3D Reconstruction Priors (CVPR 2025)
- VGGT-SLAM: Dense RGB SLAM Optimized on the SL(4) Manifold (2025, arXiv:2505.12549)
- DUSt3R (CVPR 2024); MASt3R (ECCV 2024); VGGT (CVPR 2025, best paper)
- MASt3R-Fusion (VI + GNSS, 2025, arXiv:2509.20757)
- Curated list: github.com/3D-Vision-World/All-3R-SLAM-in-this-Repo

*Datasets:* Replica, TUM RGB-D, EuRoC MAV, TartanAir, Bonn Dynamic RGB-D, OpenLORIS-Scene, KITTI.
*Tools:* `evo` (traj eval), `jetson-stats`/`jtop`, `tegrastats`, `nvpmodel`, `jetson_clocks`.
