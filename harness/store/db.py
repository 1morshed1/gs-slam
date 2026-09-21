"""Result store: sqlite of derived metrics keyed by cell, raw logs on disk beside it.

One row per completed run cell. `cell_key` (from RunManifest) makes the store idempotent
so the orchestrator can resume/retry without duplicating rows (plan §9, §10).
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    cell_key      TEXT PRIMARY KEY,
    run_id        TEXT NOT NULL,
    system        TEXT, family TEXT,
    dataset       TEXT, sequence TEXT, modality TEXT,
    corruption    TEXT, severity INTEGER, repeat INTEGER,
    power_mode    TEXT, hardware_tier TEXT, power_source TEXT,
    outcome       TEXT,
    -- accuracy
    ate_rmse REAL, rpe_trans REAL, rpe_rot REAL, lost_track_rate REAL,
    -- quality (nullable; rendering systems only)
    psnr REAL, ssim REAL, lpips REAL, recon_error REAL,
    -- latency / memory
    ms_p50 REAL, ms_p95 REAL, fps REAL, rt_factor REAL,
    peak_host_ram_mb REAL, peak_vram_mb REAL,
    -- energy
    joules_total REAL, joules_per_frame REAL, joules_per_keyframe REAL,
    avg_power_w REAL, dynamic_joules REAL, edp REAL,
    -- thermal
    peak_temp_c REAL, throttle_events INTEGER,
    -- provenance
    manifest_path TEXT, raw_log_dir TEXT, created_utc TEXT,
    extra_json TEXT
);
"""


@dataclass
class ResultStore:
    db_path: Path

    def __post_init__(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def has_cell(self, cell_key: str) -> bool:
        with self._conn() as c:
            r = c.execute("SELECT 1 FROM runs WHERE cell_key = ?", (cell_key,)).fetchone()
        return r is not None

    def upsert(self, cell_key: str, row: dict[str, Any]) -> None:
        row = dict(row, cell_key=cell_key)
        # stash unknown keys in extra_json so the schema need not chase every field
        known = {c[1] for c in self._columns()}
        extra = {k: v for k, v in row.items() if k not in known}
        if extra:
            row = {k: v for k, v in row.items() if k in known}
            row["extra_json"] = json.dumps(extra)
        cols = ", ".join(row)
        ph = ", ".join("?" for _ in row)
        upd = ", ".join(f"{k}=excluded.{k}" for k in row if k != "cell_key")
        with self._conn() as c:
            c.execute(
                f"INSERT INTO runs ({cols}) VALUES ({ph}) "
                f"ON CONFLICT(cell_key) DO UPDATE SET {upd}",
                list(row.values()),
            )

    def _columns(self) -> list[tuple]:
        with self._conn() as c:
            return c.execute("PRAGMA table_info(runs)").fetchall()

    def to_parquet(self, out: Path) -> None:
        """Export tidy table for analysis notebooks (plan §10 store/)."""
        try:
            import pandas as pd  # optional dep
        except Exception as e:  # pragma: no cover
            raise RuntimeError("pandas required for parquet export") from e
        with self._conn() as c:
            df = pd.read_sql_query("SELECT * FROM runs", c)
        df.to_parquet(out)
