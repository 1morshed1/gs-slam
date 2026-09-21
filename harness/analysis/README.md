# analysis/ — notebooks reproducing every figure (plan §10, §13.5)

All notebooks read from `store/results.sqlite` (or its parquet export) — never from raw
logs directly — so figures are traceable to derived metrics.

Planned notebooks:

| Notebook | Produces | Plan ref |
|---|---|---|
| `01_clean_pareto.ipynb` | accuracy × energy Pareto (clean grid) | §11 P2, RQ3 |
| `02_degradation_curves.ipynb` | accuracy-vs-severity per system/corruption; AUC, slope | §6, §11 P3, RQ2 |
| `03_robustness_energy.ipynb` | robustness-normalized energy (J per tracked frame) | §7, RQ3 |
| `04_power_mode_sweep.ipynb` | nvpmodel sweep on energy–latency–accuracy surface | §8, RQ5 |
| `05_thermal_sustained.ipynb` | throttle events, sustained-vs-burst decay | §7, §8, H4 |
| `06_stats.ipynb` | CIs across repeats, fps-vs-J/frame rank disagreement | §8, H4 |

Charts: follow the repo's viz conventions; keep light/dark legible. Report family groups
separately where modality differs (plan §13 fairness).
