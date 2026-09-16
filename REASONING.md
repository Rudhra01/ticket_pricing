# Reasoning

- Python was chosen because the repository had no existing framework or dependencies, and Python is available in Codespaces.
- `Decimal` is used instead of `float` so amounts are rounded to exact paisa values.
- `CinemaShow` owns its ticket tiers and availability, so the pricing code is not tied to one cinema or show.
- Pricing order is: ticket subtotal, festival discount, member percentage discount with cap, convenience fee, then GST on the discounted tickets plus fee.
- Invalid negative money values and percentages outside 0-100 are rejected so a booking cannot produce an unrealistic bill.
- The bill includes both the discounted ticket total and taxable amount, making the calculation easy to check.
- The CLI is intentionally small. The reusable part is `calculate_bill`, which can later be called by a web interface without changing the rules.
- The web upgrade uses Flask server-rendered templates because the original repository had no frontend framework or existing visual system to preserve.
- SQLite keeps local setup simple while transactions, foreign keys, indexes, and unique constraints protect booking data.
- Seats are held before payment and changed to booked only after the payment result is verified. A database write lock and availability query prevent two successful requests from taking the same seat.
- The payment implementation is deliberately a development adapter. It provides complete success/failure/cancel state transitions without pretending to verify a real provider signature; a real provider webhook must replace it before production payments.
- Verification and password reset links are shown in development instead of silently pretending that email was sent.