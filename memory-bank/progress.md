# Progress

## What works

| Area | Status |
|---|---|
| Plan document | Draft v0.1 present |
| Package layout `harness/` | Scaffold complete |
| Adapter registry + SUT stubs | Registered; `run()` raises NotImplemented |
| Corruptions | Interface + real: gaussian-noise, jpeg, defocus, motion-blur; others stubbed |
| Datasets | Frame model, loaders, fixed-rate feeder skeleton |
| Power | Abstract sampler; `nvidia-smi` backend real; tegrastats TODO |
| Eval | Energy integrate real (unit-tested); evo/quality wired behind `[rig]`; thermal stub |
| Orchestrator | Matrix expand + prune; resumable runner skeleton; `smoke.yaml` |
| Store | Manifest + sqlite schema helpers; `store/results.sqlite` local (gitignored) |
| Tests | `tests/test_scaffold.py` — registries, matrix, energy, corruption determinism |
| Analysis notebooks | README only (planned list) |
| Containers | README + conventions; no Dockerfiles yet |

## What's left (by phase)

| Phase | Goal | State |
|---|---|---|
| **P0** Bring-up | Build each SUT on rig (+ later Jetson); reproduce headline numbers | Not started |
| **P1** Measurement infra | Power sync, idle baselines, repeatability + sanity load | Partial (rig GPU backend only) |
| **P2** Clean baseline | Uncorrupted grid → first Pareto | Blocked on P0 |
| **P3** Robustness sweep | Perturbation × severity | Generators partial; runs blocked |
| **P4** Analysis & write-up | Notebooks + paper draft | Placeholders |
| **P5** Artifact release | Public harness + data + one-command cell | Later |

## Known issues / blockers

- Jetson model TBD → L4T images + edge feasibility unknown.
- External power meter TBD → claim scope undecided.
- No commits yet on `main` (repo untracked content); remote `origin/main` gone.
- Container adapters all `NotImplementedError`.
- Analysis notebooks not created.
- Full corruption suite incomplete vs plan §6 table.

## Verification today

```bash
pytest   # scaffold tests should pass with numpy (+ optional cv2 for some paths)
```
