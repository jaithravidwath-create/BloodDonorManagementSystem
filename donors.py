"""Donor registration, search, update, deletion and eligibility rules."""
from __future__ import annotations

import re
import sqlite3
from datetime import date, datetime, timedelta

from .compat import BLOOD_GROUPS
from .errors import BDMSError

MIN_AGE, MAX_AGE = 18, 65
MIN_WEIGHT_KG = 50.0
DONATION_INTERVAL_DAYS = 56  # whole blood

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---------- validation helpers ----------
def parse_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value).strip(), "%Y-%m-%d").date()
    except ValueError:
        raise BDMSError(f"Invalid date '{value}'. Use YYYY-MM-DD.")


def age_on(dob: date, today: date) -> int:
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def normalise_blood_group(value: str) -> str:
    v = str(value).strip().upper().replace(" ", "")
    if v not in BLOOD_GROUPS:
        raise BDMSError(f"Invalid blood group '{value}'. Choose from: {', '.join(BLOOD_GROUPS)}")
    return v


def normalise_phone(value: str) -> str:
    digits = re.sub(r"[\s\-()]", "", str(value))
    if digits.startswith("+"):
        digits = digits[1:]
    if not digits.isdigit() or not 7 <= len(digits) <= 15:
        raise BDMSError("Phone must contain 7-15 digits.")
    return digits


def _clean_name(value: str) -> str:
    name = " ".join(str(value).split())
    if len(name) < 2:
        raise BDMSError("Name must be at least 2 characters.")
    return name


def _clean_email(value: str) -> str:
    value = (value or "").strip()
    if value and not _EMAIL_RE.match(value):
        raise BDMSError("Invalid email address.")
    return value


def _clean_weight(value) -> float:
    try:
        w = float(value)
    except (TypeError, ValueError):
        raise BDMSError("Weight must be a number (kg).")
    if not 20 <= w <= 300:
        raise BDMSError("Weight must be between 20 and 300 kg.")
    return w


# ---------- CRUD ----------
def add_donor(conn, name, dob, gender, blood_group, phone, weight_kg,
              email="", city="", today=None) -> int:
    today = parse_date(today) if today else date.today()
    dob_d = parse_date(dob)
    if dob_d >= today:
        raise BDMSError("Date of birth must be in the past.")
    if age_on(dob_d, today) < MIN_AGE:
        raise BDMSError(f"Donors must be at least {MIN_AGE} years old.")
    gender = str(gender).strip().upper()
    if gender not in ("M", "F", "O"):
        raise BDMSError("Gender must be M, F or O.")
    try:
        cur = conn.execute(
            "INSERT INTO donors (name, dob, gender, blood_group, phone, email, city,"
            " weight_kg, registered_on) VALUES (?,?,?,?,?,?,?,?,?)",
            (_clean_name(name), dob_d.isoformat(), gender, normalise_blood_group(blood_group),
             normalise_phone(phone), _clean_email(email), (city or "").strip(),
             _clean_weight(weight_kg), today.isoformat()),
        )
    except sqlite3.IntegrityError:
        raise BDMSError("A donor with this phone number already exists.")
    conn.commit()
    return cur.lastrowid


def get_donor(conn, donor_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM donors WHERE id = ?", (donor_id,)).fetchone()
    if row is None:
        raise BDMSError(f"No donor with ID {donor_id}.")
    return row


def update_donor(conn, donor_id: int, **fields) -> None:
    get_donor(conn, donor_id)
    cleaners = {
        "name": _clean_name, "phone": normalise_phone, "email": _clean_email,
        "city": lambda v: (v or "").strip(), "weight_kg": _clean_weight,
        "active": lambda v: 1 if str(v).lower() in ("1", "true", "yes", "y") else 0,
    }
    unknown = set(fields) - set(cleaners)
    if unknown:
        raise BDMSError(f"Cannot update field(s): {', '.join(sorted(unknown))}")
    if not fields:
        raise BDMSError("Nothing to update.")
    values = {k: cleaners[k](v) for k, v in fields.items()}
    sets = ", ".join(f"{k} = ?" for k in values)
    try:
        conn.execute(f"UPDATE donors SET {sets} WHERE id = ?", (*values.values(), donor_id))
    except sqlite3.IntegrityError:
        raise BDMSError("Another donor already uses this phone number.")
    conn.commit()


def delete_donor(conn, donor_id: int) -> None:
    get_donor(conn, donor_id)
    n = conn.execute("SELECT COUNT(*) FROM donations WHERE donor_id = ?", (donor_id,)).fetchone()[0]
    if n:
        raise BDMSError("Donor has donation records and cannot be deleted. Deactivate instead.")
    conn.execute("DELETE FROM donors WHERE id = ?", (donor_id,))
    conn.commit()


def search_donors(conn, name=None, blood_group=None, city=None, active_only=False):
    sql, args = "SELECT * FROM donors WHERE 1=1", []
    if name:
        sql += " AND name LIKE ?"; args.append(f"%{name.strip()}%")
    if blood_group:
        sql += " AND blood_group = ?"; args.append(normalise_blood_group(blood_group))
    if city:
        sql += " AND city LIKE ?"; args.append(f"%{city.strip()}%")
    if active_only:
        sql += " AND active = 1"
    return conn.execute(sql + " ORDER BY name COLLATE NOCASE", args).fetchall()


# ---------- eligibility ----------
def last_donation_date(conn, donor_id: int) -> date | None:
    row = conn.execute("SELECT MAX(donated_on) FROM donations WHERE donor_id = ?", (donor_id,)).fetchone()
    return parse_date(row[0]) if row[0] else None


def next_eligible_date(conn, donor_id: int) -> date | None:
    last = last_donation_date(conn, donor_id)
    return last + timedelta(days=DONATION_INTERVAL_DAYS) if last else None


def check_eligibility(conn, donor_id: int, today=None) -> tuple[bool, str]:
    today = parse_date(today) if today else date.today()
    d = get_donor(conn, donor_id)
    if not d["active"]:
        return False, "Donor is deactivated."
    age = age_on(parse_date(d["dob"]), today)
    if age < MIN_AGE:
        return False, f"Under minimum age ({MIN_AGE})."
    if age > MAX_AGE:
        return False, f"Over maximum age ({MAX_AGE})."
    if d["weight_kg"] < MIN_WEIGHT_KG:
        return False, f"Weight below {MIN_WEIGHT_KG:g} kg."
    nxt = next_eligible_date(conn, donor_id)
    if nxt and today < nxt:
        return False, f"Donated recently; eligible again on {nxt.isoformat()}."
    return True, "Eligible to donate."


def eligible_donors(conn, blood_group=None, today=None):
    return [d for d in search_donors(conn, blood_group=blood_group, active_only=True)
            if check_eligibility(conn, d["id"], today)[0]]
