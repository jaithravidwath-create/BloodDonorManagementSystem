"""Sample data so the app can be explored immediately."""
from __future__ import annotations

from datetime import date, timedelta

from . import blood_requests, donations, donors

_DEMO = [
    ("Aarav Sharma", "1990-03-14", "M", "O+", "9876500001", 72, "aarav@example.com", "Hyderabad"),
    ("Priya Reddy", "1994-07-22", "F", "A+", "9876500002", 58, "priya@example.com", "Hyderabad"),
    ("Rahul Verma", "1988-11-05", "M", "B+", "9876500003", 80, "rahul@example.com", "Secunderabad"),
    ("Sneha Iyer", "1996-01-30", "F", "O-", "9876500004", 55, "sneha@example.com", "Hyderabad"),
    ("Karthik Rao", "1985-09-17", "M", "AB+", "9876500005", 76, "karthik@example.com", "Warangal"),
    ("Ananya Das", "1999-05-09", "F", "A-", "9876500006", 52, "ananya@example.com", "Hyderabad"),
    ("Mohammed Irfan", "1992-12-02", "M", "B-", "9876500007", 68, "irfan@example.com", "Secunderabad"),
    ("Divya Nair", "1991-04-25", "F", "O+", "9876500008", 49, "divya@example.com", "Hyderabad"),
    ("Vikram Singh", "1980-08-19", "M", "O+", "9876500009", 90, "vikram@example.com", "Warangal"),
    ("Lakshmi Menon", "1997-10-11", "F", "AB-", "9876500010", 60, "lakshmi@example.com", "Hyderabad"),
]


def load_demo(conn) -> str:
    if conn.execute("SELECT COUNT(*) FROM donors").fetchone()[0]:
        return "Database already has data; demo data not loaded."
    today = date.today()
    ids = []
    for name, dob, g, bg, ph, wt, em, city in _DEMO:
        ids.append(donors.add_donor(conn, name, dob, g, bg, ph, wt, em, city,
                                    today=today - timedelta(days=200)))
    # (donor index, days ago) - spread so some units are near expiry, some donors recently donated
    for idx, ago in [(0, 100), (0, 20), (1, 70), (2, 60), (3, 10), (4, 90), (5, 30),
                     (6, 58), (8, 75), (8, 15), (9, 40)]:
        try:
            donations.record_donation(conn, ids[idx], today - timedelta(days=ago))
        except Exception:
            pass
    blood_requests.create_request(conn, "City General Hospital", "Ravi Kumar", "O+", 2)
    blood_requests.create_request(conn, "Apollo Care", "Meena Joshi", "A+", 1)
    return "Demo data loaded: 10 donors, sample donations and 2 blood requests."
