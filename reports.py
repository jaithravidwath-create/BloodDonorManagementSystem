"""Dashboard statistics and CSV export."""
from __future__ import annotations

import csv
from pathlib import Path

from .inventory import stock_summary


def dashboard(conn, today=None) -> dict:
    q = lambda sql: conn.execute(sql).fetchone()[0]
    stock = stock_summary(conn, today)
    return {
        "total_donors": q("SELECT COUNT(*) FROM donors"),
        "active_donors": q("SELECT COUNT(*) FROM donors WHERE active = 1"),
        "total_donations": q("SELECT COUNT(*) FROM donations"),
        "units_available": sum(stock.values()),
        "units_issued": q("SELECT COUNT(*) FROM donations WHERE status = 'issued'"),
        "units_expired": q("SELECT COUNT(*) FROM donations WHERE status = 'expired'"),
        "open_requests": q("SELECT COUNT(*) FROM requests WHERE status IN ('pending','partial')"),
        "donors_by_group": {r["blood_group"]: r["n"] for r in conn.execute(
            "SELECT blood_group, COUNT(*) n FROM donors GROUP BY blood_group ORDER BY blood_group")},
    }


def export_csv(conn, table: str, path) -> int:
    if table not in ("donors", "donations", "requests"):
        raise ValueError("table must be donors, donations or requests")
    rows = conn.execute(f"SELECT * FROM {table}").fetchall()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(rows[0].keys() if rows else [c[1] for c in conn.execute(f"PRAGMA table_info({table})")])
        w.writerows([tuple(r) for r in rows])
    return len(rows)
