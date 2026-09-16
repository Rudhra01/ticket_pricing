"I need to build the ticket_pricing project from this problem statement.

Please help me make a simple working solution that looks like a normal student project, not over engineered.

Requirements I understood:
Cinema has ticket tiers: Silver, Gold, Recliner
Each tier has its own price
Some tiers can be sold out, so booking should not allow them
User should be able to select tier and quantity
 There is a flat festival discount
 There is also a member percentage discount with a maximum cap
 After discount, add convenience fee per ticket
 Then calculate GST
Money calculation should be accurate to exact paisa, so don't use floating point for money if possible
 Show a clear bill breakup line by line
 It should be reusable for different cinemas/shows, so don't hardcode one particular show

I want you to first inspect the empty repository and decide a simple tech stack based on what is already available. If the repo is empty, use a simple stack that is easy to run in Codespaces.

Please build the project step by step:
1. Create the basic project structure
2. Implement ticket/tier and availability handling
3. Implement pricing and discounts
4. Implement convenience fee and GST
5. Implement exact money/rounding handling
6. Implement a simple interface (CLI or basic web interface, whichever makes more sense)
7. Add some test cases for normal bookings, sold out tiers, discounts, member discount cap, multiple tickets, and rounding
8. Add README.md, REASONING.md and AI_LOGS.md requirements in the repo, but don't make the documentation unnecessarily complicated.

Keep the code simple and readable, like a student would normally do. Don't add unnecessary frameworks, design patterns, Docker, databases, authentication, etc.

Before making files, briefly tell me what approach you are going to use. Then implement it.
"

Built the project as a simple Python CLI using only the standard library.

Implemented:

- Reusable cinema/show and ticket tier models
- Silver, Gold, and Recliner availability handling
- Festival and capped member discounts
- Convenience fee and GST
- Exact paisa calculations with `Decimal`
- Clear bill breakdown
- CLI interface in [app.py](app.py)
- Pricing logic in [ticket_pricing.py](ticket_pricing.py)
- Six focused tests in [test_ticket_pricing.py](test_ticket_pricing.py)
- Documentation in [README.md](README.md), [REASONING.md](REASONING.md), and [AI_LOGS.md](AI_LOGS.md)

Validation completed successfully:

```text
Ran 6 tests ... OK
```

Run it with:

```bash
python app.py
```

Run tests with:

```bash
python -m unittest discover -v
```

What would you like to upgrade?

1. **Web interface** instead of CLI
2. **Better CLI** with menus and input validation
3. **More realistic pricing rules** and booking flow
4. **More tests and stronger error handling**
5. **All of the above**, while keeping it simple and student-friendly

more realistic pricing

Upgraded the pricing to be more realistic while keeping it simple.

Changes include:

- Rejects negative ticket prices, availability, discounts, and fees
- Validates member discount and GST percentages from `0` to `100`
- Shows discounted ticket total and taxable amount in the bill
- Keeps GST calculated after discounts and convenience fees
- Added tests for invalid pricing inputs
- Updated [README.md](README.md), [REASONING.md](REASONING.md), and [AI_LOGS.md](AI_LOGS.md)

Validation passed:

```text
Ran 8 tests ... OK
```

The main changes are in [ticket_pricing.py](ticket_pricing.py).
# AI Logs

## 2026-09-16

- Inspected the repository and found only a placeholder README.
- Chose a standard-library Python CLI with `Decimal` and `unittest`.
- Added reusable tier/show models, availability checks, discount and tax calculation, bill formatting, and tests for the requested cases.
- Upgraded the pricing rules with validation for unrealistic negative values and added discounted/taxable subtotals to the bill.