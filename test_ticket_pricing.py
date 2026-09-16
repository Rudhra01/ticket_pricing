import unittest
from decimal import Decimal

from ticket_pricing import CinemaShow, TicketTier, calculate_bill


def sample_show() -> CinemaShow:
    return CinemaShow(
        "City Cinema",
        "Evening Show",
        {
            "Silver": TicketTier("Silver", "100.00", 10),
            "Gold": TicketTier("Gold", "150.00", 2),
            "Recliner": TicketTier("Recliner", "250.00", 0),
        },
    )


class TicketPricingTests(unittest.TestCase):
    def test_normal_booking(self) -> None:
        bill = calculate_bill(sample_show(), "Silver", 1, gst_percent="18")
        self.assertEqual(bill.taxable_total, Decimal("100.00"))
        self.assertEqual(bill.total, Decimal("118.00"))

    def test_sold_out_tier_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "available"):
            calculate_bill(sample_show(), "Recliner", 1)

    def test_festival_and_member_discounts(self) -> None:
        bill = calculate_bill(
            sample_show(),
            "Gold",
            1,
            festival_discount="20",
            member_percent="10",
            member_discount_cap="50",
            gst_percent="18",
        )
        self.assertEqual(bill.member_discount, Decimal("13.00"))
        self.assertEqual(bill.discounted_ticket_total, Decimal("117.00"))
        self.assertEqual(bill.total, Decimal("138.06"))

    def test_member_discount_cap_is_applied(self) -> None:
        bill = calculate_bill(
            sample_show(), "Gold", 1, member_percent="50", member_discount_cap="30"
        )
        self.assertEqual(bill.member_discount, Decimal("30.00"))

    def test_multiple_tickets_and_fee(self) -> None:
        bill = calculate_bill(
            sample_show(), "Silver", 3, convenience_fee_per_ticket="12.50", gst_percent="18"
        )
        self.assertEqual(bill.ticket_total, Decimal("300.00"))
        self.assertEqual(bill.convenience_fee, Decimal("37.50"))
        self.assertEqual(bill.taxable_total, Decimal("337.50"))
        self.assertEqual(bill.total, Decimal("398.25"))

    def test_rounding_is_to_exact_paisa(self) -> None:
        bill = calculate_bill(
            sample_show(),
            "Silver",
            1,
            member_percent="33.333",
            member_discount_cap="100",
            gst_percent="18",
        )
        self.assertEqual(bill.member_discount, Decimal("33.33"))
        self.assertEqual(bill.total, Decimal("78.67"))

    def test_negative_pricing_inputs_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "negative"):
            calculate_bill(sample_show(), "Silver", 1, festival_discount="-1")
        with self.assertRaisesRegex(ValueError, "negative"):
            calculate_bill(sample_show(), "Silver", 1, convenience_fee_per_ticket="-1")
        with self.assertRaisesRegex(ValueError, "GST"):
            calculate_bill(sample_show(), "Silver", 1, gst_percent="101")

    def test_negative_tier_values_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "price"):
            TicketTier("Invalid", "-10", 1)
        with self.assertRaisesRegex(ValueError, "availability"):
            TicketTier("Invalid", "10", -1)


if __name__ == "__main__":
    unittest.main()