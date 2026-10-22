import math

import pytest

from reseller_profit.calculator import break_even_price, compute_profit
from reseller_profit.models import ListingInput
from reseller_profit.profiles import load_profile


@pytest.fixture
def ebay():
    return load_profile("ebay")


@pytest.fixture
def amazon():
    return load_profile("amazon")


@pytest.fixture
def mercari():
    return load_profile("mercari")


def test_plain_sale_is_profit(ebay):
    listing = ListingInput(item_cost=10.0, sale_price=50.0,
                           shipping_charged=8.0, shipping_cost=5.0)
    result = compute_profit(listing, ebay)
    assert math.isclose(result.revenue, 58.0)
    assert result.fee_base_label.startswith("buyer total")


def test_fee_math_ebay_with_tax(amazon, ebay):
    # tax 6% => tax_collected = (50 + 8) * 0.06 = 3.48; buyer_total = 61.48
    listing = ListingInput(item_cost=10.0, sale_price=50.0,
                           shipping_charged=8.0, shipping_cost=5.0,
                           tax_rate_percent=6.0)
    result = compute_profit(listing, ebay)
    assert math.isclose(result.tax_collected, 3.48, abs_tol=1e-6)
    assert math.isclose(result.fee_base, 61.48, abs_tol=1e-6)
    # fees: 61.48 * 13.6% + 0.30
    assert math.isclose(result.fees_total, 61.48 * 0.136 + 0.30, abs_tol=1e-6)
    # profit = revenue - tax - fees - shipping_cost - item_cost
    expected = 58.0 - 3.48 - (61.48 * 0.136 + 0.30) - 5.0 - 10.0
    assert math.isclose(result.profit, expected, abs_tol=1e-6)


def test_mercari_fee_on_sale_only(mercari):
    listing = ListingInput(item_cost=10.0, sale_price=50.0,
                           shipping_charged=8.0, shipping_cost=5.0,
                           tax_rate_percent=6.0)
    result = compute_profit(listing, mercari)
    assert math.isclose(result.fee_base, 50.0)
    assert math.isclose(result.fees_total, 5.0)
    assert math.isclose(result.profit, 58.0 - 3.48 - 5.0 - 5.0 - 10.0, abs_tol=1e-6)


def test_amazon_order_fee(amazon):
    listing = ListingInput(item_cost=10.0, sale_price=50.0,
                           shipping_charged=8.0, shipping_cost=5.0)
    result = compute_profit(listing, amazon)
    # base = sale + shipping = 58; fee = 15% * 58 + 0.99
    assert math.isclose(result.fees_total, 58.0 * 0.15 + 0.99, abs_tol=1e-6)


def test_negative_inputs_rejected(ebay):
    with pytest.raises(ValueError, match="negative"):
        compute_profit(ListingInput(item_cost=-1), ebay)
    with pytest.raises(ValueError, match="negative"):
        compute_profit(ListingInput(sale_price=-1), ebay)
    with pytest.raises(ValueError, match="negative"):
        compute_profit(ListingInput(shipping_cost=-1), ebay)


def test_category_override_books(ebay):
    listing = ListingInput(item_cost=1.0, sale_price=10.0, category="Books")
    result = compute_profit(listing, ebay)
    # override 15.1% on buyer_total (10.0 since no shipping/tax) + 0.30
    assert math.isclose(result.fees_total, 10.0 * 0.151 + 0.30, abs_tol=1e-6)


def test_break_even_is_zero_profit(ebay, amazon, mercari):
    for profile in (ebay, amazon, mercari):
        listing = ListingInput(item_cost=12.0, sale_price=40.0,
                               shipping_charged=7.0, shipping_cost=6.0,
                               tax_rate_percent=7.25, category="glassware")
        price = break_even_price(listing, profile)
        assert price is not None
        solved = compute_profit(ListingInput(
            item_cost=listing.item_cost, sale_price=price,
            shipping_charged=listing.shipping_charged,
            shipping_cost=listing.shipping_cost,
            tax_rate_percent=listing.tax_rate_percent,
            category=listing.category), profile)
        assert abs(solved.profit) < 1e-6, profile.name
        assert price < listing.sale_price


def test_break_even_never_profitable(ebay):
    from dataclasses import replace
    from reseller_profit.profiles import FinalValueFee
    greedy = replace(ebay, final_value_fee=FinalValueFee(
        base="buyer_total", percent=150.0, flat=0.0))
    listing = ListingInput(item_cost=10.0, sale_price=100.0)
    assert break_even_price(listing, greedy) is None


def test_break_even_zero_when_free(mercari):
    listing = ListingInput(item_cost=0.0, sale_price=0.0)
    result = compute_profit(listing, mercari)
    assert result.break_even_price == 0.0


def test_break_even_needs_to_cover_flat_fee(ebay):
    listing = ListingInput(item_cost=0.0, sale_price=0.0)
    result = compute_profit(listing, ebay)
    assert result.break_even_price is not None
    assert result.break_even_price > 0.0


def test_margin_and_roi(ebay):
    listing = ListingInput(item_cost=10.0, sale_price=100.0)
    result = compute_profit(listing, ebay)
    assert result.margin_percent == pytest.approx(result.profit, abs=1e-6)
    assert result.roi_percent == pytest.approx(result.profit / 10.0 * 100.0, abs=1e-6)


def test_loss_when_price_equals_cost(mercari):
    listing = ListingInput(item_cost=5.0, sale_price=5.0)
    result = compute_profit(listing, mercari)
    assert math.isclose(result.profit, -5.0 * 0.10, abs_tol=1e-6)

