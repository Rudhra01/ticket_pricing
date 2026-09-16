# Ticket Pricing

A small Flask + SQLite cinema booking web application. It keeps the original
Decimal-based pricing rules and adds persistent users, seat reservations,
payment flow, bookings, cancellations, and an admin dashboard.

## Requirements

- Python 3.10 or newer
- Flask 3.x
- No external database is required for local development

## Setup and Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # optional; export the values in your shell
python app.py
```

Open `http://127.0.0.1:5000`. The first run creates `ticket_pricing.db` and
seeds one show with Silver, Gold, and Recliner seats.

The development admin account is `admin@example.com` with password
`Admin123!`. Change it before any shared or deployed use.

Pricing is calculated in this order:

1. Ticket subtotal for the selected tier and quantity
2. Flat festival discount
3. Member percentage discount, limited by its cap
4. Convenience fee for each ticket
5. GST on the discounted tickets plus convenience fee

Prices are calculated with `Decimal` and rounded to two decimal places. The
program rejects negative prices, discounts, fees, and availability values, as
well as invalid discount and GST percentages.

## Debugging

To check for Python syntax errors:

```bash
python -m py_compile ticket_pricing.py app.py test_ticket_pricing.py
```

To see detailed test output, run:

```bash
python -m unittest discover -v
```

For a CLI input problem, check that prices, quantities, availability, and
percentages are entered as numbers. The program prints a booking error instead
of creating a bill when an input is invalid.
## Test and Debug

```bash
python -m unittest discover -v
python -m py_compile app.py database.py ticket_pricing.py
```

The test suite covers pricing, registration and verification, login, real seat
reservation, duplicate-seat protection, mock payment success, cancellation,
refund records, and admin authorization.

For local development, registration and password reset display their links in
the page because no email provider is configured. The payment screen uses a
mock provider with success, failure, and cancellation outcomes. Set
`PAYMENT_PROVIDER` and integrate a provider webhook before accepting real
payments.

## Configuration

Copy `.env.example` and set a long random `SECRET_KEY`. Set `COOKIE_SECURE=1`
when serving over HTTPS. `DATABASE_PATH` can point to a persistent SQLite
file; for higher traffic, replace the database module with PostgreSQL while
keeping the service and route boundaries.

Useful endpoints include `/health`, `/api/shows/<show_id>/availability`, and
`/api/bookings/<booking_id>` for the logged-in owner. Admin operations are
protected by the backend role check, not only by hidden navigation.

The pricing logic remains reusable in `ticket_pricing.py`; database state and
booking transactions are handled in `app.py` and `database.py`.