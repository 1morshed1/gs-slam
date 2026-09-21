# System patterns

## Architecture

```
harness/
├─ adapters/       # SLAMAdapter: FrameStream → TUM traj + optional map
├─ datasets/       # loaders + fixed-rate feeder
├─ corruptions/    # sev 1–5 generators; pregenerate to disk
├─ power/          # out-of-process sampler backends + frame markers
├─ orchestrator/   # matrix expand + resumable runner
├─ eval/           # evo / quality / energy / thermal
├─ store/          # manifest + sqlite/parquet
├─ analysis/       # notebooks (placeholders)
└─ containers/     # one image per SUT (x86 now; L4T later)
```

## Design contracts (do not break)

1. **I/O contract.** Every system behind `SLAMAdapter`; eval never sees internals. Trajectory = TUM (`timestamp tx ty tz qx qy qz qw`).
2. **Corruptions pre-generated** with deterministic seeds. Never corrupt inside measured loop.
3. **Power sampling out-of-process**; timestamped log + frame-boundary markers; merge by monotonic clock.
4. **Every run emits a manifest** (commit, versions, config, seed) into `store/`.

## Patterns in use

| Pattern | Where | Why |
|---|---|---|
| Adapter registry | `adapters/base.py` + `systems.py` | Matrix validates before systems run |
| Corruption registry | `corruptions/` | Same API, sev-parameterized |
| Config-as-code matrix | `orchestrator/matrix.py` | Resume, prune coarse/fine severity |
| Pluggable power backends | `power/backends.py` | nvidia-smi now; tegrastats TBD |
| Container-per-SUT | `containers/` | Isolates CUDA/torch/rasterizer wars |

## Component relationships

```
matrix → orchestrator.run → adapter.run(stream)
                ↓                ↓
            power sampler    FrameStream (datasets)
                ↓                ↓
            PowerLog ──merge──→ eval.energy / metrics / thermal
                ↓
              store (manifest + results.sqlite)
                ↓
              analysis notebooks
```

## Hardware roles (not interchangeable)

- **Tier A office rig** (`vm-130-131`, Blackwell `sm_120`, GPU-1 only): build, corruptions, accuracy/quality upper bound, analysis. Not primary energy device.
- **Tier B Jetson** (model TBD): real J/frame, thermal, edge feasibility. aarch64 L4T rebuild required.
