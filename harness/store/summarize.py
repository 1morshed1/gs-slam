"""Per-cell summary over repeats (plan §8: repeats mandatory).

ORB-family trackers are multi-modal even on clean data, so the mean alone misleads:
report median + IQR next to mean ± std, and failure rate over all repeats.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import numpy as np

_GROUP = ("system", "dataset", "sequence", "modality", "corruption", "severity",
          "power_mode", "hardware_tier")


def summarize(db_path: Path) -> list[dict]:
    with sqlite3.connect(db_path) as c:
        c.row_factory = sqlite3.Row
        rows = c.execute(
            f"SELECT {', '.join(_GROUP)}, outcome, ate_rmse FROM runs"
        ).fetchall()
    groups: dict[tuple, list[sqlite3.Row]] = {}
    for r in rows:
        groups.setdefault(tuple(r[k] for k in _GROUP), []).append(r)

    out = []
    for key, rs in sorted(groups.items(), key=lambda kv: [str(v) for v in kv[0]]):
        ate = np.array([r["ate_rmse"] for r in rs
                        if r["outcome"] == "ok" and r["ate_rmse"] is not None])
        n_fail = sum(r["outcome"] != "ok" for r in rs)
        s = dict(zip(_GROUP, key), n=len(rs), n_fail=n_fail, fail_rate=n_fail / len(rs))
        if ate.size:
            q1, med, q3 = np.percentile(ate, [25, 50, 75])
            s.update(ate_median=med, ate_q1=q1, ate_q3=q3, ate_mean=ate.mean(),
                     ate_std=ate.std(ddof=1) if ate.size > 1 else 0.0, ate_max=ate.max())
        out.append(s)
    return out


def _fmt_cm(v) -> str:
    return "     -" if v is None else f"{100 * v:6.2f}"


def main() -> None:
    ap = argparse.ArgumentParser(description="Summarize repeats per cell.")
    ap.add_argument("--store", type=Path, default=Path("store/results.sqlite"))
    a = ap.parse_args()
    print(f"{'system':10s} {'corruption':17s} sev   n fail  med_cm  q1_cm  q3_cm mean_cm std_cm max_cm")
    for s in summarize(a.store):
        print(f"{s['system']:10s} {s['corruption']:17s} {s['severity']:3d} {s['n']:3d} "
              f"{s['fail_rate']:4.0%} {_fmt_cm(s.get('ate_median'))} {_fmt_cm(s.get('ate_q1'))} "
              f"{_fmt_cm(s.get('ate_q3'))} {_fmt_cm(s.get('ate_mean'))} {_fmt_cm(s.get('ate_std'))} "
              f"{_fmt_cm(s.get('ate_max'))}")


if __name__ == "__main__":
    main()
