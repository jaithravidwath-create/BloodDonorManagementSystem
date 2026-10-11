"""Interactive command-line interface."""
from __future__ import annotations

import argparse
import sys
from datetime import date

from . import __version__, blood_requests, db, demo, donations, donors, inventory, reports
from .compat import BLOOD_GROUPS
from .errors import BDMSError

EXPORT_DIR = db.BASE_DIR / "exports"


# ---------- small UI helpers ----------
def table(rows, headers):
    rows = [[("" if c is None else str(c)) for c in r] for r in rows]
    widths = [max(len(h), *(len(r[i]) for r in rows)) if rows else len(h) for i, h in enumerate(headers)]
    line = "-+-".join("-" * w for w in widths)
    print(" | ".join(h.ljust(w) for h, w in zip(headers, widths)))
    print(line)
    for r in rows:
        print(" | ".join(c.ljust(w) for c, w in zip(r, widths)))
    print(f"({len(rows)} row{'s' if len(rows) != 1 else ''})")


def ask(prompt, default=None):
    suffix = f" [{default}]" if default not in (None, "") else ""
    val = input(f"{prompt}{suffix}: ").strip()
    return val if val else (default or "")


def ask_int(prompt):
    val = ask(prompt)
    try:
        return int(val)
    except ValueError:
        raise BDMSError("Please enter a whole number.")


def donor_rows(rows):
    return [(d["id"], d["name"], d["blood_group"], d["gender"], d["phone"], d["city"],
             f"{d['weight_kg']:g}", "Yes" if d["active"] else "No") for d in rows]


DONOR_HEADERS = ["ID", "Name", "Group", "Sex", "Phone", "City", "Kg", "Active"]


# ---------- menu actions ----------
def register_donor(conn):
    print("\n-- Register donor --")
    new_id = donors.add_donor(
        conn,
        name=ask("Full name"), dob=ask("Date of birth (YYYY-MM-DD)"),
        gender=ask("Gender (M/F/O)"), blood_group=ask(f"Blood group ({', '.join(BLOOD_GROUPS)})"),
        phone=ask("Phone"), weight_kg=ask("Weight (kg)"),
        email=ask("Email (optional)"), city=ask("City (optional)"),
    )
    print(f"Donor registered with ID {new_id}.")


def search(conn):
    print("\n-- Search donors (leave blank to skip a filter) --")
    rows = donors.search_donors(conn, ask("Name contains") or None,
                                ask("Blood group") or None, ask("City contains") or None)
    table(donor_rows(rows), DONOR_HEADERS)


def update(conn):
    donor_id = ask_int("Donor ID")
    d = donors.get_donor(conn, donor_id)
    print(f"Editing {d['name']} (press Enter to keep current value)")
    fields = {}
    for key, label in [("name", "Name"), ("phone", "Phone"), ("email", "Email"),
                       ("city", "City"), ("weight_kg", "Weight (kg)")]:
        val = ask(label, d[key])
        if str(val) != str(d[key] if d[key] is not None else ""):
            fields[key] = val
    act = ask("Active (yes/no)", "yes" if d["active"] else "no")
    if (act.lower() in ("yes", "y", "1")) != bool(d["active"]):
        fields["active"] = act
    if not fields:
        print("No changes.")
        return
    donors.update_donor(conn, donor_id, **fields)
    print("Donor updated.")


def delete(conn):
    donor_id = ask_int("Donor ID")
    d = donors.get_donor(conn, donor_id)
    if ask(f"Delete {d['name']}? (yes/no)", "no").lower() in ("yes", "y"):
        donors.delete_donor(conn, donor_id)
        print("Donor deleted.")
    else:
        print("Cancelled.")


def record(conn):
    donor_id = ask_int("Donor ID")
    ok, reason = donors.check_eligibility(conn, donor_id)
    print(f"Eligibility: {reason}")
    if not ok:
        return
    on = ask("Donation date", date.today().isoformat())
    did = donations.record_donation(conn, donor_id, on)
    print(f"Donation #{did} recorded and added to inventory.")


def history(conn):
    donor_id = ask_int("Donor ID")
    d = donors.get_donor(conn, donor_id)
    print(f"History for {d['name']} ({d['blood_group']})")
    rows = donations.donation_history(conn, donor_id)
    table([(r["id"], r["donated_on"], r["expiry_date"], r["status"]) for r in rows],
          ["Unit", "Donated", "Expires", "Status"])
    nxt = donors.next_eligible_date(conn, donor_id)
    if nxt:
        print(f"Next eligible date: {nxt.isoformat()}")


def eligibility(conn):
    print("\n1) Check one donor   2) List all eligible donors")
    if ask("Choice", "1") == "2":
        rows = donors.eligible_donors(conn, ask("Blood group filter (optional)") or None)
        table(donor_rows(rows), DONOR_HEADERS)
    else:
        ok, reason = donors.check_eligibility(conn, ask_int("Donor ID"))
        print(("ELIGIBLE: " if ok else "NOT ELIGIBLE: ") + reason)


def show_inventory(conn):
    stock = inventory.stock_summary(conn)
    low = inventory.low_stock(conn)
    table([(g, n, "LOW" if g in low else "") for g, n in stock.items()], ["Group", "Units", "Alert"])
    soon = inventory.expiring_soon(conn, 7)
    if soon:
        print("\nExpiring within 7 days:")
        table([(r["id"], r["blood_group"], r["expiry_date"]) for r in soon], ["Unit", "Group", "Expires"])


def new_request(conn):
    rid = blood_requests.create_request(conn, ask("Hospital"), ask("Patient name"),
                                        ask("Blood group needed"), ask("Units needed"))
    print(f"Request #{rid} created. Use 'Fulfil request' to issue stock.")


def fulfil(conn):
    result = blood_requests.fulfill_request(conn, ask_int("Request ID"))
    print(f"Issued {result['issued_now']} unit(s) now; {result['issued_total']} total; "
          f"{result['remaining']} still needed. Status: {result['status'].upper()}")


def requests_menu(conn):
    rows = blood_requests.list_requests(conn)
    table([(r["id"], r["hospital"], r["patient"], r["blood_group"],
            f"{r['units_issued']}/{r['units']}", r["requested_on"], r["status"]) for r in rows],
          ["ID", "Hospital", "Patient", "Group", "Issued", "Date", "Status"])


def cancel(conn):
    blood_requests.cancel_request(conn, ask_int("Request ID to cancel"))
    print("Request cancelled.")


def show_reports(conn):
    s = reports.dashboard(conn)
    print("\n== Dashboard ==")
    for k in ("total_donors", "active_donors", "total_donations", "units_available",
              "units_issued", "units_expired", "open_requests"):
        print(f"{k.replace('_', ' ').title():<20}: {s[k]}")
    print("Donors by group     :", ", ".join(f"{g}={n}" for g, n in s["donors_by_group"].items()) or "-")
    if ask("\nExport to CSV? (yes/no)", "no").lower() in ("yes", "y"):
        for t in ("donors", "donations", "requests"):
            n = reports.export_csv(conn, t, EXPORT_DIR / f"{t}.csv")
            print(f"  exported {n} rows -> {EXPORT_DIR / (t + '.csv')}")


MENU = [
    ("Register donor", register_donor), ("Search donors", search),
    ("Update donor", update), ("Delete donor", delete),
    ("Record donation", record), ("Donor donation history", history),
    ("Check eligibility", eligibility), ("Blood inventory", show_inventory),
    ("New blood request", new_request), ("Fulfil blood request", fulfil),
    ("List blood requests", requests_menu), ("Cancel blood request", cancel),
    ("Reports & CSV export", show_reports), ("Load demo data", lambda c: print(demo.load_demo(c))),
]


def run_menu(conn):
    print(f"\n=== Blood Donor Management System v{__version__} ===")
    alerts = inventory.low_stock(conn)
    if alerts and conn.execute("SELECT COUNT(*) FROM donors").fetchone()[0]:
        print("! Low stock:", ", ".join(f"{g}({n})" for g, n in alerts.items()))
    while True:
        print()
        for i, (label, _) in enumerate(MENU, 1):
            print(f"{i:>2}. {label}")
        print(" 0. Exit")
        choice = input("\nSelect: ").strip()
        if choice == "0":
            print("Goodbye.")
            return
        if not choice.isdigit() or not 1 <= int(choice) <= len(MENU):
            print("Invalid choice.")
            continue
        try:
            MENU[int(choice) - 1][1](conn)
        except BDMSError as e:
            print(f"Error: {e}")
        except (EOFError, KeyboardInterrupt):
            raise
        input("\nPress Enter to continue...")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Blood Donor Management System")
    p.add_argument("--db", help="path to SQLite database (default: data/bdms.db)")
    p.add_argument("--demo", action="store_true", help="load sample data if the database is empty")
    args = p.parse_args(argv)
    conn = db.connect(args.db)
    try:
        if args.demo:
            print(demo.load_demo(conn))
        run_menu(conn)
    except (EOFError, KeyboardInterrupt):
        print("\nExiting.")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
