from dataclasses import replace
from typing import Optional

from reseller_profit.models import FeeLine, ListingInput, ProfitResult
from reseller_profit.profiles import FeeProfile


def _validate(listing: ListingInput) -> None:
    for label, value in (
        ("item_cost", listing.item_cost),
        ("sale_price", listing.sale_price),
        ("shipping_charged", listing.shipping_charged),
        ("shipping_cost", listing.shipping_cost),
        ("tax_rate_percent", listing.tax_rate_percent),
    ):
        if value < 0:
            raise ValueError(f"{label} can't be negative (got {value}).")


def fee_base_amount(sale_price: float, shipping_charged: float, tax_collected: float, base: str) -> float:
    if base == "sale":
        return sale_price
    if base == "sale_plus_shipping":
        return sale_price + shipping_charged
    if base == "buyer_total":
        return sale_price + shipping_charged + tax_collected
    raise ValueError(f"unknown fee base {base!r}")


def fees_for_price(listing: ListingInput, profile: FeeProfile, sale_price: float):
    """Fee lines and the total for a given sale price. Used by the solver too."""
    taxed = replace(listing, sale_price=sale_price)
    tax_collected = (sale_price + taxed.shipping_charged) * taxed.tax_rate_percent / 100.0
    override = profile.override_for_category(taxed.category)
    fee_spec = override.component if override else profile.final_value_fee
    base_label = {"sale": "sale price", "sale_plus_shipping": "sale + shipping",
                  "buyer_total": "buyer total (price + shipping + tax)"}[fee_spec.base]
    base = fee_base_amount(sale_price, taxed.shipping_charged, tax_collected, fee_spec.base)

    lines = []
    percent_amount = base * fee_spec.percent / 100.0
    if fee_spec.percent:
        lines.append(FeeLine(f"final value fee ({fee_spec.percent:g}%)", base_label, base, percent_amount))
    if fee_spec.flat:
        lines.append(FeeLine("final value fee (flat)", "", base, fee_spec.flat))
    if profile.order_fee_flat:
        lines.append(FeeLine("order fee (flat)", "", base, profile.order_fee_flat))
    total = percent_amount + fee_spec.flat + profile.order_fee_flat
    return lines, total, base, base_label, tax_collected, override


def _core_profit(listing: ListingInput, profile: FeeProfile, with_break_even: bool) -> ProfitResult:
    _validate(listing)
    lines, fees_total, base, base_label, tax_collected, _ = fees_for_price(
        listing, profile, listing.sale_price)

    shipping_net = listing.shipping_charged - listing.shipping_cost
    revenue = listing.sale_price + listing.shipping_charged
    profit = revenue - tax_collected - fees_total - listing.shipping_cost - listing.item_cost

    margin = profit / revenue * 100.0 if revenue > 0 else 0.0
    roi = profit / listing.item_cost * 100.0 if listing.item_cost > 0 else 0.0

    return ProfitResult(
        profile_name=profile.name,
        profile_display_name=profile.describe(),
        sale_price=listing.sale_price,
        item_cost=listing.item_cost,
        shipping_charged=listing.shipping_charged,
        shipping_cost=listing.shipping_cost,
        tax_rate_percent=listing.tax_rate_percent,
        tax_collected=tax_collected,
        fee_base=base,
        fee_base_label=base_label,
        fees=lines,
        fees_total=fees_total,
        shipping_net=shipping_net,
        revenue=revenue,
        profit=profit,
        margin_percent=margin,
        roi_percent=roi,
        break_even_price=break_even_price(listing, profile) if with_break_even else None,
    )


def compute_profit(listing: ListingInput, profile: FeeProfile) -> ProfitResult:
    """Full profit math for one listing. Raises ValueError on negative inputs."""
    return _core_profit(listing, profile, with_break_even=True)


def break_even_price(listing: ListingInput, profile: FeeProfile) -> Optional[float]:
    """The sale price where profit is exactly zero, shipping and tax held fixed.

    Returns None when no price in a sane range makes the listing profitable
    (for example if fees are 150% of the buyer total).
    """
    _validate(listing)
    taxed = replace(listing, sale_price=0.0)
    baseline = _core_profit(taxed, profile, with_break_even=False).profit

    if baseline >= 0:
        return 0.0

    def profit_at(price: float) -> float:
        taxed = replace(listing, sale_price=price)
        return _core_profit(taxed, profile, with_break_even=False).profit

    high = max(1.0, listing.item_cost + listing.shipping_cost + 10.0)
    for _ in range(60):
        if profit_at(high) > 0.0:
            break
        high *= 2.0
    else:
        return None

    low = 0.0
    for _ in range(100):
        mid = (low + high) / 2.0
        if profit_at(mid) <= 0.0:
            low = mid
        else:
            high = mid
    return high
