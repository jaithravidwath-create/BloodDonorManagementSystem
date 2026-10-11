"""Hospital blood requests and compatibility-based issuing."""
from __future__ import annotations

from datetime import date

from .compat import BLOOD_GROUPS, compatible_donor_groups
from .donors import normalise_blood_group, parse_date
from .errors import BDMSError
from .inventory import expire_stale

MAX_UNITS_PER_REQUEST = 20


def create_request(conn, hospital, patient, blood_group, units, today=None) -> int:
    hospital, patient = " ".join(str(hospital).split()), " ".join(str(patient).split())
    if not hospital or not patient:
        raise BDMSError("Hospital and patient name are required.")
    try:
        units = int(units)
    except (TypeError, ValueError):
        raise BDMSError("Units must be a whole number.")
    if not 1 <= units <= MAX_UNITS_PER_REQUEST:
        raise BDMSError(f"Units must be between 1 and {MAX_UNITS_PER_REQUEST}.")
    today = parse_date(today) if today else date.today()
    cur = conn.execute(
        "INSERT INTO requests (hospital, patient, blood_group, units, requested_on) VALUES (?,?,?,?,?)",
        (hospital, patient, normalise_blood_group(blood_group), units, today.isoformat()),
    )
    conn.commit()
    return cur.lastrowid


def get_request(conn, request_id: int):
    row = conn.execute("SELECT * FROM requests WHERE id = ?", (request_id,)).fetchone()
    if row is None:
        raise BDMSError(f"No request with ID {request_id}.")
    return row


def list_requests(conn, status=None):
    if status:
        return conn.execute("SELECT * FROM requests WHERE status = ? ORDER BY id DESC", (status,)).fetchall()
    return conn.execute("SELECT * FROM requests ORDER BY id DESC").fetchall()


def fulfill_request(conn, request_id: int, today=None) -> dict:
    """Issue compatible units: exact-group first (saves universal donors), then soonest expiry."""
    req = get_request(conn, request_id)
    if req["status"] in ("fulfilled", "cancelled"):
        raise BDMSError(f"Request is already {req['status']}.")
    expire_stale(conn, today)
    needed = req["units"] - req["units_issued"]
    groups = compatible_donor_groups(req["blood_group"])
    marks = ",".join("?" * len(groups))
    units = conn.execute(
        f"SELECT dn.id FROM donations dn JOIN donors d ON d.id = dn.donor_id "
        f"WHERE dn.status = 'available' AND d.blood_group IN ({marks}) "
        f"ORDER BY (d.blood_group = ?) DESC, dn.expiry_date ASC, dn.id ASC LIMIT ?",
        (*groups, req["blood_group"], needed),
    ).fetchall()
    for u in units:
        conn.execute("UPDATE donations SET status='issued', request_id=? WHERE id=?", (request_id, u["id"]))
    issued_total = req["units_issued"] + len(units)
    status = "fulfilled" if issued_total >= req["units"] else ("partial" if issued_total else "pending")
    conn.execute("UPDATE requests SET units_issued=?, status=? WHERE id=?", (issued_total, status, request_id))
    conn.commit()
    return {"issued_now": len(units), "issued_total": issued_total,
            "remaining": req["units"] - issued_total, "status": status}


def cancel_request(conn, request_id: int) -> None:
    req = get_request(conn, request_id)
    if req["status"] in ("fulfilled", "cancelled"):
        raise BDMSError(f"Request is already {req['status']}.")
    if req["units_issued"] > 0:
        raise BDMSError("Units were already issued for this request; it cannot be cancelled.")
    conn.execute("UPDATE requests SET status='cancelled' WHERE id=?", (request_id,))
    conn.commit()
