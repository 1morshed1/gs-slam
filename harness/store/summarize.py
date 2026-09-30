"""Per-cell summary over repeats (plan §7 outcome taxonomy, §8: repeats mandatory).

ORB-family trackers are multi-modal even on clean data, so the mean alone misleads:
report median + IQR next to mean ± std, and a three-bucket outcome taxonomy.

Outcome taxonomy (plan §7). A run's stored ``outcome`` records what happened
mechanically; the *converged / diverged* split below is a derived, analysis-time
label applied here so a run that emits a garbage trajectory is not scored as a
success just because it produced a file:

    converged  : outcome == "ok" AND ATE-RMSE <= CATASTROPHIC_ATE_M
    diverged   : outcome == "ok" AND ATE-RMSE >  CATASTROPHIC_ATE_M   (catastrophic)
    hard_fail  : outcome != "ok" (lost_track / timeout / crash / oom / infeasible)

``catastrophic_rate = (n_diverged + n_hard_fail) / n`` is the honest per-cell
failure rate; ``fail_rate`` (hard failures only) is kept for continuity. ATE
statistics are computed over *converged* runs only — the meaningful mode — with
the diverged mode reported separately (count + median) rather than averaged in.

The threshold is a reported parameter, not tuned to a result: pass ``--catastrophic-m``
and use ``--sensitivity`` to show the rate is stable across a range of thresholds
(it is, whenever the ATE distribution is bimodal with a wide gap, e.g. gaussian-noise
sev5 on fr1/desk: ~3 cm vs ~125 cm, so any threshold in [0.1, 1.0] m gives 40%).
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import numpy as np

#: Default ATE-RMSE (metres) above which a finished ("ok") run is catastrophic.
#: On fr1/desk (room-scale) 0.5 m is far past any plausible good-mode error and
#: well below the failure mode (~1.25 m); the split is insensitive to the exact
#: value across [0.1, 1.0] m. Reported alongside every table (plan §7).
CATASTROPHIC_ATE_M = 0.5

#: Thresholds (metres) used by --sensitivity to show the split is robust.
_SENSITIVITY_M = (0.1, 0.25, 0.5, 1.0, 2.0)

_GROUP = ("system", "dataset", "sequence", "modality", "corruption", "severity",
          "power_mode", "hardware_tier")


def summarize(db_path: Path, catastrophic_ate_m: float = CATASTROPHIC_ATE_M) -> list[dict]:
    """Group runs per experimental cell and apply the outcome taxonomy.

    ATE statistics (median/IQR/mean/std/max) are over *converged* runs only.
    ``div_median`` is the median ATE of the diverged (catastrophic) mode.
    """
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
        ok = [r for r in rs if r["outcome"] == "ok" and r["ate_rmse"] is not None]
        conv = np.array([r["ate_rmse"] for r in ok if r["ate_rmse"] <= catastrophic_ate_m])
        div = np.array([r["ate_rmse"] for r in ok if r["ate_rmse"] > catastrophic_ate_m])
        n_hard = sum(r["outcome"] != "ok" for r in rs)
        n = len(rs)
        s = dict(
            zip(_GROUP, key),
            n=n,
            n_converged=int(conv.size),
            n_diverged=int(div.size),
            n_hard_fail=n_hard,
            n_fail=n_hard,  # backward compat: hard failures only
            fail_rate=n_hard / n,
            catastrophic_rate=(int(div.size) + n_hard) / n,
            catastrophic_ate_m=catastrophic_ate_m,
        )
        if conv.size:
            q1, med, q3 = np.percentile(conv, [25, 50, 75])
            s.update(ate_median=med, ate_q1=q1, ate_q3=q3, ate_mean=conv.mean(),
                     ate_std=conv.std(ddof=1) if conv.size > 1 else 0.0, ate_max=conv.max())
        if div.size:
            s["div_median"] = float(np.median(div))
        out.append(s)
    return out


def sensitivity(db_path: Path, thresholds=_SENSITIVITY_M) -> dict[float, list[dict]]:
    """Catastrophic-rate per cell at several thresholds (threshold robustness)."""
    return {t: summarize(db_path, catastrophic_ate_m=t) for t in thresholds}


def _fmt_cm(v) -> str:
    return "     -" if v is None else f"{100 * v:6.2f}"


def main() -> None:
    ap = argparse.ArgumentParser(description="Summarize repeats per cell (plan §7 taxonomy).")
    ap.add_argument("--store", type=Path, default=Path("store/results.sqlite"))
    ap.add_argument("--catastrophic-m", type=float, default=CATASTROPHIC_ATE_M,
                    help="ATE-RMSE (m) above which an 'ok' run is catastrophic/diverged")
    ap.add_argument("--sensitivity", action="store_true",
                    help="also print catastrophic-rate across a range of thresholds")
    a = ap.parse_args()

    print(f"# converged ATE (cm) over ok runs with ATE <= {a.catastrophic_m} m; "
          f"catastr% = (diverged + hard-fail) / n")
    print(f"{'system':10s} {'corruption':17s} sev   n conv div hard catastr%  "
          f"med_cm  q1_cm  q3_cm mean_cm std_cm max_cm div_med_cm")
    for s in summarize(a.store, catastrophic_ate_m=a.catastrophic_m):
        print(f"{s['system']:10s} {s['corruption']:17s} {s['severity']:3d} {s['n']:3d} "
              f"{s['n_converged']:4d} {s['n_diverged']:3d} {s['n_hard_fail']:4d} "
              f"{s['catastrophic_rate']:7.0%}  {_fmt_cm(s.get('ate_median'))} "
              f"{_fmt_cm(s.get('ate_q1'))} {_fmt_cm(s.get('ate_q3'))} "
              f"{_fmt_cm(s.get('ate_mean'))} {_fmt_cm(s.get('ate_std'))} "
              f"{_fmt_cm(s.get('ate_max'))} {_fmt_cm(s.get('div_median'))}")

    if a.sensitivity:
        grids = sensitivity(a.store)
        print("\n# threshold sensitivity: catastrophic-rate per cell")
        hdr = "  ".join(f"{t}m" for t in _SENSITIVITY_M)
        print(f"{'system':10s} {'corruption':17s} sev   {hdr}")
        # Iterate cells via the first grid's key order.
        base = grids[_SENSITIVITY_M[0]]
        for i, s in enumerate(base):
            rates = "  ".join(f"{grids[t][i]['catastrophic_rate']:3.0%}" for t in _SENSITIVITY_M)
            print(f"{s['system']:10s} {s['corruption']:17s} {s['severity']:3d}   {rates}")


if __name__ == "__main__":
    main()
