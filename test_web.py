import os
import re
import tempfile
import unittest

from app import create_app


class WebFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.database.close()
        self.application = create_app(
            {"TESTING": True, "DATABASE": self.database.name, "SECRET_KEY": "test-secret"}
        )
        self.client = self.application.test_client()

    def tearDown(self) -> None:
        os.unlink(self.database.name)

    def csrf(self):
        self.client.get("/register")
        with self.client.session_transaction() as session:
            return session["csrf_token"]

    def register_and_verify(self, email="customer@example.com"):
        response = self.client.post(
            "/register",
            data={"csrf_token": self.csrf(), "name": "Customer", "email": email, "password": "Customer123!"},
        )
        match = re.search(rb'href="([^\"]*/verify/[^\"]+)"', response.data)
        self.assertIsNotNone(match)
        self.client.get(match.group(1).decode())

    def login(self, email="customer@example.com", password="Customer123!"):
        return self.client.post(
            "/login", data={"csrf_token": self.csrf(), "email": email, "password": password}
        )

    def test_registration_verification_and_login(self):
        self.register_and_verify()
        response = self.login()
        self.assertEqual(response.status_code, 302)
        self.assertIn("Evening Premiere", self.client.get("/").data.decode())

    def test_booking_payment_and_cancellation_flow(self):
        self.register_and_verify()
        self.login()
        seats = self.client.get("/api/shows/1/availability").get_json()
        selected = next(seat for seat in seats if seat["status"] == "available")
        show_page = self.client.get("/shows/1")
        self.assertIn(b"Select seats", show_page.data)
        response = self.client.post(
            "/book",
            data={
                "csrf_token": self.csrf(),
                "show_id": "1",
                "seat_ids": str(self._seat_id(selected["seat_number"])),
                "passenger_name": "Customer",
                "passenger_email": "customer@example.com",
            },
        )
        self.assertEqual(response.status_code, 302)
        payment_url = response.headers["Location"]
        payment_page = self.client.get(payment_url)
        self.assertIn(b"Review and pay", payment_page.data)
        booking_id = int(payment_url.rsplit("/", 1)[-1])
        self.client.get(f"/payment/{booking_id}/success")
        detail = self.client.get(f"/bookings/{booking_id}")
        self.assertIn(b"CONFIRMED", detail.data)
        self.client.post(f"/bookings/{booking_id}/cancel", data={"csrf_token": self.csrf()})
        self.assertIn(b"CANCELLED", self.client.get(f"/bookings/{booking_id}").data)

    def test_mixed_tier_booking_shows_bill_breakup(self):
        self.register_and_verify("mixed@example.com")
        self.login("mixed@example.com")
        response = self.client.post(
            "/book",
            data={
                "csrf_token": self.csrf(),
                "show_id": "1",
                "seat_ids": [str(self._seat_id("S1")), str(self._seat_id("G1"))],
                "passenger_name": "Mixed Customer",
                "passenger_email": "mixed@example.com",
            },
        )
        self.assertEqual(response.status_code, 302)
        payment_page = self.client.get(response.headers["Location"])
        self.assertIn(b"Silver x 1", payment_page.data)
        self.assertIn(b"Gold x 1", payment_page.data)
        self.assertIn(b"Ticket subtotal", payment_page.data)
        self.assertIn(b"Festival discount", payment_page.data)
        self.assertIn(b"GST", payment_page.data)
        self.assertIn(b"Rs. 273.76", payment_page.data)

    def test_same_seat_cannot_be_booked_twice(self):
        self.register_and_verify()
        self.login()
        seat_id = self._seat_id("S1")
        payload = {"csrf_token": self.csrf(), "show_id": "1", "seat_ids": str(seat_id), "passenger_name": "A", "passenger_email": "a@example.com"}
        first = self.client.post("/book", data=payload)
        self.assertEqual(first.status_code, 302)
        self.client.get(first.headers["Location"] + "/success")
        self.client.get("/logout")
        self.register_and_verify("second@example.com")
        self.login("second@example.com")
        second = self.client.post("/book", data={**payload, "csrf_token": self.csrf(), "passenger_name": "B", "passenger_email": "b@example.com"})
        self.assertEqual(second.status_code, 302)
        self.assertIn(b"select", self.client.get(second.headers["Location"]).data.lower())

    def test_customer_cannot_open_admin_page(self):
        self.register_and_verify()
        self.login()
        response = self.client.get("/admin")
        self.assertEqual(response.status_code, 302)

    def _seat_id(self, seat_number):
        with self.application.app_context():
            from database import get_db

            return get_db().execute("SELECT id FROM seats WHERE show_id=1 AND seat_number=?", (seat_number,)).fetchone()[0]


if __name__ == "__main__":
    unittest.main()