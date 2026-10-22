from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ListingInput:
    """Everything we need to price one listing.

    All money amounts are in the profile's currency. ``tax_rate_percent``
    is a percent, so ``7.25`` means 7.25% (also written 0.0725 in math
    code). Sales tax is charged to the buyer and passed through: it never
    raises your profit, it can only raise your fees when a profile bases
    fees on ``buyer_total``.
    """

    name: str = ""
    item_cost: float = 0.0
    sale_price: float = 0.0
    shipping_charged: float = 0.0
    shipping_cost: float = 0.0
    tax_rate_percent: float = 0.0
    category: str = ""


@dataclass
class FeeLine:
    """One fee on the way out: a label, what it was figured on, and the amount."""

    label: str
    basis: str
    base_amount: float
    amount: float


@dataclass
class ProfitResult:
    """The full math for one listing, computed against one fee profile."""

    profile_name: str
    profile_display_name: str

    sale_price: float
    item_cost: float
    shipping_charged: float
    shipping_cost: float
    tax_rate_percent: float

    tax_collected: float
    fee_base: float
    fee_base_label: str
    fees: List[FeeLine] = field(default_factory=list)
    fees_total: float = 0.0

    shipping_net: float = 0.0
    revenue: float = 0.0
    profit: float = 0.0
    margin_percent: float = 0.0
    roi_percent: float = 0.0

    break_even_price: Optional[float] = None


def money(value: float) -> str:
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.2f}"


def percent(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}%"
