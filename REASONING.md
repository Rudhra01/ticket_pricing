# Reasoning

- Python was chosen because the repository had no existing framework or dependencies, and Python is available in Codespaces.
- `Decimal` is used instead of `float` so amounts are rounded to exact paisa values.
- `CinemaShow` owns its ticket tiers and availability, so the pricing code is not tied to one cinema or show.
- Pricing order is: ticket subtotal, festival discount, member percentage discount with cap, convenience fee, then GST on the discounted tickets plus fee.
- Invalid negative money values and percentages outside 0-100 are rejected so a booking cannot produce an unrealistic bill.
- The bill includes both the discounted ticket total and taxable amount, making the calculation easy to check.
- The CLI is intentionally small. The reusable part is `calculate_bill`, which can later be called by a web interface without changing the rules.