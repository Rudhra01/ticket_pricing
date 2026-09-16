from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


MONEY_PLACES = Decimal("0.01")


def money(value: Decimal | str | int) -> Decimal:
    """Convert a value to money rounded to the nearest paisa."""
    return Decimal(str(value)).quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)


@dataclass
class TicketTier:
    name: str
    price: Decimal
    available: int

    def __post_init__(self) -> None:
        self.price = money(self.price)
        if self.price < 0:
            raise ValueError("Ticket price cannot be negative")
        if self.available < 0:
            raise ValueError("Ticket availability cannot be negative")


@dataclass
class CinemaShow:
    cinema_name: str
    show_name: str
    tiers: dict[str, TicketTier]

    def get_tier(self, tier_name: str) -> TicketTier:
        try:
            return self.tiers[tier_name]
        except KeyError as error:
            raise ValueError(f"Unknown ticket tier: {tier_name}") from error


@dataclass
class Bill:
    cinema_name: str
    show_name: str
    tier_name: str
    quantity: int
    ticket_price: Decimal
    ticket_total: Decimal
    festival_discount: Decimal
    member_discount: Decimal
    discounted_ticket_total: Decimal
    convenience_fee: Decimal
    taxable_total: Decimal
    gst: Decimal
    total: Decimal

    def lines(self) -> list[str]:
        return [
            f"Cinema: {self.cinema_name}",
            f"Show: {self.show_name}",
            f"Tickets: {self.tier_name} x {self.quantity} @ Rs. {self.ticket_price:.2f}",
            f"Ticket subtotal:             Rs. {self.ticket_total:.2f}",
            f"Festival discount:           -Rs. {self.festival_discount:.2f}",
            f"Member discount:             -Rs. {self.member_discount:.2f}",
            f"Discounted ticket total:     Rs. {self.discounted_ticket_total:.2f}",
            f"Convenience fee:             Rs. {self.convenience_fee:.2f}",
            f"Taxable amount:              Rs. {self.taxable_total:.2f}",
            f"GST:                         Rs. {self.gst:.2f}",
            "----------------------------------------",
            f"Total payable:               Rs. {self.total:.2f}",
        ]


def calculate_bill(
    show: CinemaShow,
    tier_name: str,
    quantity: int,
    festival_discount: Decimal | str | int = Decimal("0"),
    member_percent: Decimal | str | int = Decimal("0"),
    member_discount_cap: Decimal | str | int = Decimal("0"),
    convenience_fee_per_ticket: Decimal | str | int = Decimal("0"),
    gst_percent: Decimal | str | int = Decimal("0"),
) -> Bill:
    if quantity <= 0:
        raise ValueError("Quantity must be greater than zero")

    tier = show.get_tier(tier_name)
    if quantity > tier.available:
        raise ValueError(
            f"Only {tier.available} {tier.name} ticket(s) are available"
        )

    festival_discount_value = money(festival_discount)
    member_discount_cap_value = money(member_discount_cap)
    convenience_fee_value = money(convenience_fee_per_ticket)
    gst_percent_value = Decimal(str(gst_percent))

    if festival_discount_value < 0:
        raise ValueError("Festival discount cannot be negative")
    if member_discount_cap_value < 0:
        raise ValueError("Member discount cap cannot be negative")
    if convenience_fee_value < 0:
        raise ValueError("Convenience fee cannot be negative")
    if gst_percent_value < 0 or gst_percent_value > 100:
        raise ValueError("GST percentage must be between 0 and 100")

    ticket_total = money(tier.price * quantity)
    festival_discount_amount = min(festival_discount_value, ticket_total)
    amount_after_festival = ticket_total - festival_discount_amount

    member_percent_value = Decimal(str(member_percent))
    if member_percent_value < 0 or member_percent_value > 100:
        raise ValueError("Member percentage must be between 0 and 100")
    member_discount_amount = money(
        amount_after_festival * member_percent_value / Decimal("100")
    )
    member_discount_amount = min(
        member_discount_amount, member_discount_cap_value, amount_after_festival
    )

    discounted_total = amount_after_festival - member_discount_amount
    convenience_fee = money(convenience_fee_value * quantity)
    taxable_total = discounted_total + convenience_fee
    gst = money(taxable_total * gst_percent_value / Decimal("100"))
    total = money(taxable_total + gst)

    return Bill(
        cinema_name=show.cinema_name,
        show_name=show.show_name,
        tier_name=tier.name,
        quantity=quantity,
        ticket_price=tier.price,
        ticket_total=ticket_total,
        festival_discount=festival_discount_amount,
        member_discount=member_discount_amount,
        discounted_ticket_total=discounted_total,
        convenience_fee=convenience_fee,
        taxable_total=taxable_total,
        gst=gst,
        total=total,
    )