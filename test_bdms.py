import os
import sys
import tempfile
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bdms import blood_requests as br, db, demo, donations, donors, inventory, reports
from bdms.compat import BLOOD_GROUPS, can_donate_to
from bdms.errors import BDMSError

TODAY = date.today()


def make_donor(conn, phone="9000000001", group="O+", dob="1990-01-01", weight=70, **kw):
    return donors.add_donor(conn, "Test Donor", dob, "M", group, phone, weight, **kw)


class BaseTest(unittest.TestCase):
    def setUp(self):
        self.conn = db.connect(":memory:")

    def tearDown(self):
        self.conn.close()


class DonorTests(BaseTest):
    def test_register_and_get(self):
        i = make_donor(self.conn, phone="+91 90000-00001")
        d = donors.get_donor(self.conn, i)
        self.assertEqual(d["phone"], "919000000001")
        self.assertEqual(d["blood_group"], "O+")

    def test_validation(self):
        with self.assertRaises(BDMSError): make_donor(self.conn, group="Z+")
        with self.assertRaises(BDMSError): make_donor(self.conn, phone="abc")
        with self.assertRaises(BDMSError): make_donor(self.conn, dob="2015-01-01")
        with self.assertRaises(BDMSError): make_donor(self.conn, dob="not-a-date")
        with self.assertRaises(BDMSError): make_donor(self.conn, email="bad@")

    def test_duplicate_phone(self):
        make_donor(self.conn)
        with self.assertRaises(BDMSError): make_donor(self.conn)

    def test_update_search_delete(self):
        i = make_donor(self.conn, city="Hyderabad")
        donors.update_donor(self.conn, i, city="Pune", weight_kg=75)
        self.assertEqual(len(donors.search_donors(self.conn, city="pune")), 1)
        with self.assertRaises(BDMSError): donors.update_donor(self.conn, i, blood_group="A+")
        donors.delete_donor(self.conn, i)
        with self.assertRaises(BDMSError): donors.get_donor(self.conn, i)

    def test_cannot_delete_donor_with_donations(self):
        i = make_donor(self.conn)
        donations.record_donation(self.conn, i)
        with self.assertRaises(BDMSError): donors.delete_donor(self.conn, i)


class EligibilityTests(BaseTest):
    def test_underweight_and_age(self):
        light = make_donor(self.conn, phone="9000000002", weight=45)
        old = make_donor(self.conn, phone="9000000003", dob="1950-01-01")
        self.assertFalse(donors.check_eligibility(self.conn, light)[0])
        self.assertFalse(donors.check_eligibility(self.conn, old)[0])

    def test_interval(self):
        i = make_donor(self.conn)
        donations.record_donation(self.conn, i, TODAY - timedelta(days=10))
        ok, msg = donors.check_eligibility(self.conn, i)
        self.assertFalse(ok); self.assertIn("eligible again", msg)
        with self.assertRaises(BDMSError): donations.record_donation(self.conn, i)
        self.assertTrue(donors.check_eligibility(self.conn, i, TODAY + timedelta(days=60))[0])

    def test_inactive(self):
        i = make_donor(self.conn)
        donors.update_donor(self.conn, i, active="no")
        self.assertFalse(donors.check_eligibility(self.conn, i)[0])

    def test_future_donation_rejected(self):
        i = make_donor(self.conn)
        with self.assertRaises(BDMSError):
            donations.record_donation(self.conn, i, TODAY + timedelta(days=1))


class InventoryTests(BaseTest):
    def test_stock_and_expiry(self):
        a = make_donor(self.conn, phone="9000000004", group="A+")
        b = make_donor(self.conn, phone="9000000005", group="B+")
        donations.record_donation(self.conn, a, TODAY - timedelta(days=50))  # expired
        donations.record_donation(self.conn, b, TODAY - timedelta(days=5))
        s = inventory.stock_summary(self.conn)
        self.assertEqual(s["A+"], 0)
        self.assertEqual(s["B+"], 1)
        self.assertEqual(len(inventory.expiring_soon(self.conn, 60)), 1)
        self.assertIn("A+", inventory.low_stock(self.conn))


class RequestTests(BaseTest):
    _phone = 9100000000

    def _stock(self, group, n):
        for k in range(n):
            RequestTests._phone += 1
            i = make_donor(self.conn, phone=str(RequestTests._phone), group=group)
            donations.record_donation(self.conn, i, TODAY - timedelta(days=k + 1))

    def test_exact_group_preferred_then_universal(self):
        self._stock("A+", 1); self._stock("O-", 2)
        rid = br.create_request(self.conn, "H1", "P1", "A+", 2)
        r = br.fulfill_request(self.conn, rid)
        self.assertEqual(r["status"], "fulfilled")
        left = inventory.stock_summary(self.conn)
        self.assertEqual(left["A+"], 0)
        self.assertEqual(left["O-"], 1)  # only one O- needed

    def test_partial_then_complete(self):
        self._stock("O+", 1)
        rid = br.create_request(self.conn, "H1", "P1", "O+", 2)
        self.assertEqual(br.fulfill_request(self.conn, rid)["status"], "partial")
        self._stock("O-", 1)
        res = br.fulfill_request(self.conn, rid)
        self.assertEqual(res["status"], "fulfilled")
        self.assertEqual(res["issued_total"], 2)
        with self.assertRaises(BDMSError): br.fulfill_request(self.conn, rid)

    def test_incompatible_not_issued(self):
        self._stock("A+", 2)
        rid = br.create_request(self.conn, "H1", "P1", "O+", 1)
        self.assertEqual(br.fulfill_request(self.conn, rid)["status"], "pending")

    def test_cancel_rules(self):
        rid = br.create_request(self.conn, "H1", "P1", "O+", 1)
        br.cancel_request(self.conn, rid)
        self.assertEqual(br.get_request(self.conn, rid)["status"], "cancelled")
        with self.assertRaises(BDMSError): br.cancel_request(self.conn, rid)
        with self.assertRaises(BDMSError): br.create_request(self.conn, "H", "P", "O+", 0)


class CompatReportDemoTests(BaseTest):
    def test_compat_rules(self):
        self.assertTrue(can_donate_to("O-", "AB+"))
        self.assertFalse(can_donate_to("AB+", "O-"))
        self.assertEqual(sum(can_donate_to(g, "AB+") for g in BLOOD_GROUPS), 8)

    def test_demo_and_reports(self):
        self.assertIn("loaded", demo.load_demo(self.conn))
        self.assertIn("already", demo.load_demo(self.conn))
        s = reports.dashboard(self.conn)
        self.assertEqual(s["total_donors"], 10)
        self.assertEqual(s["open_requests"], 2)
        with tempfile.TemporaryDirectory() as tmp:
            n = reports.export_csv(self.conn, "donors", os.path.join(tmp, "d.csv"))
            self.assertEqual(n, 10)
            self.assertTrue(os.path.exists(os.path.join(tmp, "d.csv")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
