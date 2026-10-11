# Blood Donor Management System (BDMS)

A complete, menu-driven Python application for managing blood donors, donations,
blood stock and hospital requests. Pure standard library (Python 3.9+) with SQLite storage.
No installation or dependencies needed.

## Run

```bash
python main.py --demo      # first run: loads 10 sample donors, donations and requests
python main.py             # normal run (data saved in data/bdms.db)
python main.py --db my.db  # use a different database file
```

## Run the tests

```bash
python -m unittest discover -s tests -v
```

## Features

| Area | What it does |
|------|--------------|
| Donors | Register, search (name / group / city), update, deactivate, delete (only if no donations) |
| Validation | Dates, phone (7-15 digits, unique), email, weight, blood group, minimum age 18 |
| Eligibility | Age 18-65, weight >= 50 kg, active, 56 days since last donation; lists eligible donors |
| Donations | Each donation = 1 unit with 42-day shelf life; full history and next eligible date |
| Inventory | Stock per blood group, automatic expiry, low-stock alerts (< 5 units), expiring-soon list |
| Requests | Hospital requests; issuing uses ABO/Rh compatibility, exact group first (saves O-), earliest expiry first; supports partial fulfilment |
| Reports | Dashboard statistics and CSV export of donors, donations, requests (to `exports/`) |

## Project layout

```
main.py              entry point
bdms/
  cli.py             interactive menu
  db.py              SQLite connection and schema
  donors.py          donor CRUD, validation, eligibility rules
  donations.py       recording donations, history
  inventory.py       stock, expiry, alerts
  blood_requests.py  requests, compatibility-based issuing
  compat.py          blood group compatibility table
  reports.py         dashboard and CSV export
  demo.py            sample data
tests/test_bdms.py   16 unit tests
```

## Configuration

Set `BDMS_DB=/path/to/file.db` to change the default database location.
Eligibility thresholds are constants at the top of `bdms/donors.py`; shelf life is in
`bdms/donations.py`.

*Note: eligibility rules are general guidelines for demonstration. Real blood banks must follow
their national regulations and medical screening.*

## License

MIT - see [LICENSE](LICENSE).
