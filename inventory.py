"""Blood stock: availability, expiry and alerts."""
from __future__ import annotations

from datetime import date, timedelta

from .compat import BLOOD_GROUPS
from .donors import parse_date

LOW_STOCK_THRESHOLD = 5


def expire_stale(conn, today=None) -> int:
    """Mark available units past their expiry date as expired. Returns count."""
    today = parse_date(today) if today else date.today()
    cur = conn.execute(
        "UPDATE donations SET status = 'expired' WHERE status = 'available' AND expiry_date < ?",
        (today.isoformat(),),
    )
    conn.commit()
    return cur.rowcount


def stock_summary(conn, today=None) -> dict[str, int]:
    expire_stale(conn, today)
    summary = {g: 0 for g in BLOOD_GROUPS}
    for r in conn.execute(
        "SELECT d.blood_group g, COUNT(*) n FROM donations dn JOIN donors d ON d.id = dn.donor_id "
        "WHERE dn.status = 'available' GROUP BY d.blood_group"
    ):
        summary[r["g"]] = r["n"]
    return summary


def low_stock(conn, threshold: int = LOW_STOCK_THRESHOLD, today=None) -> dict[str, int]:
    return {g: n for g, n in stock_summary(conn, today).items() if n < threshold}


def expiring_soon(conn, days: int = 7, today=None):
    today = parse_date(today) if today else date.today()
    expire_stale(conn, today)
    limit = today + timedelta(days=days)
    return conn.execute(
        "SELECT dn.id, d.blood_group, dn.donated_on, dn.expiry_date FROM donations dn "
        "JOIN donors d ON d.id = dn.donor_id "
        "WHERE dn.status = 'available' AND dn.expiry_date <= ? ORDER BY dn.expiry_date",
        (limit.isoformat(),),
    ).fetchall()
