"""Recording donations (each donation = one 450 ml unit / bag)."""
from __future__ import annotations

from datetime import date, timedelta

from .donors import check_eligibility, get_donor, parse_date
from .errors import BDMSError

SHELF_LIFE_DAYS = 42  # red blood cells


def record_donation(conn, donor_id: int, on=None) -> int:
    on_d = parse_date(on) if on else date.today()
    if on_d > date.today():
        raise BDMSError("Donation date cannot be in the future.")
    ok, reason = check_eligibility(conn, donor_id, on_d)
    if not ok:
        raise BDMSError(f"Donor not eligible: {reason}")
    cur = conn.execute(
        "INSERT INTO donations (donor_id, donated_on, expiry_date) VALUES (?,?,?)",
        (donor_id, on_d.isoformat(), (on_d + timedelta(days=SHELF_LIFE_DAYS)).isoformat()),
    )
    conn.commit()
    return cur.lastrowid


def donation_history(conn, donor_id: int):
    get_donor(conn, donor_id)
    return conn.execute(
        "SELECT * FROM donations WHERE donor_id = ? ORDER BY donated_on DESC, id DESC", (donor_id,)
    ).fetchall()


def all_donations(conn):
    return conn.execute(
        "SELECT dn.*, d.name AS donor_name, d.blood_group FROM donations dn "
        "JOIN donors d ON d.id = dn.donor_id ORDER BY dn.donated_on DESC, dn.id DESC"
    ).fetchall()
