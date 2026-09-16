from decimal import Decimal, InvalidOperation

from ticket_pricing import CinemaShow, TicketTier, calculate_bill


def ask(prompt: str) -> str:
    return input(prompt).strip()


def ask_decimal(prompt: str) -> Decimal:
    while True:
        try:
            return Decimal(ask(prompt))
        except InvalidOperation:
            print("Please enter a valid number.")


def main() -> None:
    print("Cinema Ticket Booking")
    cinema_name = ask("Cinema name: ")
    show_name = ask("Show name: ")

    tiers: dict[str, TicketTier] = {}
    for name in ("Silver", "Gold", "Recliner"):
        price = ask_decimal(f"{name} price (Rs.): ")
        available = int(ask(f"{name} tickets available: "))
        tiers[name] = TicketTier(name, price, available)

    show = CinemaShow(cinema_name, show_name, tiers)
    print("\nAvailable tiers:")
    for tier in tiers.values():
        print(f"- {tier.name}: Rs. {tier.price:.2f} ({tier.available} available)")

    try:
        bill = calculate_bill(
            show=show,
            tier_name=ask("\nChoose tier: "),
            quantity=int(ask("Quantity: ")),
            festival_discount=ask_decimal("Festival discount (Rs.): "),
            member_percent=ask_decimal("Member discount (%): "),
            member_discount_cap=ask_decimal("Member discount cap (Rs.): "),
            convenience_fee_per_ticket=ask_decimal("Convenience fee per ticket (Rs.): "),
            gst_percent=ask_decimal("GST (%): "),
        )
    except (ValueError, InvalidOperation) as error:
        print(f"Booking failed: {error}")
        return

    print("\n---------- BILL ----------")
    print("\n".join(bill.lines()))


if __name__ == "__main__":
    main()