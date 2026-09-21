"""Config-as-code experiment matrix (plan §9).

Expands a declarative config into concrete cells, applying pruning rules:
  - skip modality-incompatible cells (adapter.can_run),
  - coarse severity grid over all systems, fine grid on a representative subset,
  - severity 0 (clean control) always included.
The orchestrator iterates cells; the store makes it resumable by cell_key.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product
from typing import Optional


@dataclass
class ExperimentConfig:
    """Declarative matrix. Loaded from YAML (orchestrator/configs/*.yaml)."""

    systems: list[str]
    sequences: list[tuple[str, str, str]]   # (dataset, sequence, modality)
    corruptions: list[str] = field(default_factory=list)
    severities: list[int] = field(default_factory=lambda: [1, 3, 5])  # coarse default
    fine_severities: list[int] = field(default_factory=lambda: [1, 2, 3, 4, 5])
    fine_subset_systems: list[str] = field(default_factory=list)   # get the fine grid
    repeats: int = 3
    power_modes: list[str] = field(default_factory=lambda: ["default"])
    hardware_tier: str = "office_rig"
    include_clean_control: bool = True


@dataclass(frozen=True)
class Cell:
    system: str
    dataset: str
    sequence: str
    modality: str
    corruption: str
    severity: int
    repeat: int
    power_mode: str


def expand_matrix(cfg: ExperimentConfig) -> list[Cell]:
    """Produce the deduplicated list of cells to run (before modality filtering).

    Modality-incompatibility is filtered in the runner via adapter.can_run(stream),
    because it needs the concrete stream's modalities. Here we expand everything else.
    """
    cells: list[Cell] = []
    for system, (dataset, seq, modality), pmode in product(
        cfg.systems, cfg.sequences, cfg.power_modes
    ):
        # clean control (severity 0, no corruption)
        if cfg.include_clean_control:
            for r in range(cfg.repeats):
                cells.append(Cell(system, dataset, seq, modality, "none", 0, r, pmode))
        # corrupted cells
        sev_grid = (cfg.fine_severities
                    if system in cfg.fine_subset_systems else cfg.severities)
        for corruption, sev, r in product(cfg.corruptions, sev_grid, range(cfg.repeats)):
            cells.append(Cell(system, dataset, seq, modality, corruption, sev, r, pmode))
    # dedup while preserving order
    seen: set[Cell] = set()
    out: list[Cell] = []
    for c in cells:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out
