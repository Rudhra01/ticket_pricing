# Ticket Pricing

A small Python CLI for booking cinema tickets and printing a clear bill.

## Requirements

- Python 3.10 or newer
- No third-party packages

## Run

```bash
python app.py
```

The CLI asks for the cinema/show details, ticket tier, quantity, and discount
settings. It then prints the bill line by line.

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
## Test

```bash
python -m unittest discover -v
```

The pricing logic is in `ticket_pricing.py`, so it can also be reused by
another interface later.