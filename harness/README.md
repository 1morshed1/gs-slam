# harness/ — Edge Visual-SLAM Energy + Robustness Benchmark

Skeleton for the benchmark described in `../edge-slam-energy-robustness-benchmark-plan.md`.

## Status of each module (rig-first build)

| Module | State | Runs on office rig? | Jetson dep |
|---|---|---|---|
| `adapters/` | interface + stub adapters | yes (feasibility runs) | no |
| `corruptions/` | interface + 3 real generators, rest stubbed | **yes, fully** | no |
| `datasets/` | loaders + fixed-rate feeder | yes | no |
| `eval/` | evo/quality/energy interfaces; evo + quality real, energy stub | yes | partial |
| `power/` | abstract sampler; `nvidia-smi` backend real, `tegrastats` TODO | GPU-only coarse | **backend TBD** |
| `store/` | run manifest + tidy schema (sqlite/parquet) | yes | no |
| `orchestrator/` | config-as-code matrix, resumable runner | yes | no |
| `analysis/` | notebook placeholders | yes | no |
| `containers/` | x86 stubs; L4T variants TODO | build only | **TBD** |

**Decisions locked (2026-09-22):** modality scope = mono + RGB-D + stereo + VI (all four).
**Deferred:** Jetson model, power-measurement gear. Edge + power-backend code is stubbed
behind interfaces so it can be filled once hardware is chosen. See plan §14.

## Design contracts (do not break — these are what keeps cross-family compare fair)

1. **I/O contract.** Every SLAM system is wrapped by a `SLAMAdapter` that consumes the
   same `FrameStream` and emits a **TUM-format trajectory** (`timestamp tx ty tz qx qy qz qw`)
   plus optional map artifacts. Eval never sees system internals.
2. **Corruptions are pre-generated to disk** with deterministic seeds. Never corrupt inside
   the measured loop — it pollutes energy numbers.
3. **Power sampling runs out-of-process**, writes a timestamped log with frame-boundary
   markers; orchestrator merges by monotonic clock.
4. **Every run emits a manifest** (commit, versions, config, seed) into `store/`.

## Quickstart (rig, once deps installed)

```bash
python -m harness.orchestrator.run --config harness/orchestrator/configs/smoke.yaml
```

## Layout

```
harness/
├─ adapters/       # per-system I/O adapter: FrameStream -> TUM traj + map
├─ datasets/       # loaders + fixed-rate frame feeder
├─ corruptions/    # parameterized perturbation generators (pre-generate to disk)
├─ power/          # power daemon: pluggable sampler backends, timestamped + frame markers
├─ orchestrator/   # runs the matrix; crash/timeout/lost-track handling; resumable
├─ eval/           # evo (ATE/RPE), PSNR/SSIM/LPIPS, energy integration, thermal parse
├─ store/          # tidy schema (parquet/sqlite): raw + derived + manifest
├─ analysis/       # notebooks: Pareto, degradation curves, stats
└─ containers/     # one image per SUT (x86 + L4T variants), pinned commits
```
