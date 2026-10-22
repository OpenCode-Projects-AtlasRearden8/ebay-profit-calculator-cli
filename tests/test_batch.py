import csv
import io
import textwrap

import pytest

from reseller_profit.batch import (read_listings, run_batch, write_results_csv)


def make_entries(csv_text):
    return read_listings(io.StringIO(csv_text))


BASIC = textwrap.dedent("""\
    name,item_cost,sale_price,shipping_charged,shipping_cost,tax_rate,category
    Plate,4.00,29.99,6.95,6.15,6.35,collectibles
    Book,0.50,7.99,3.49,3.05,0.00,books
""")


def test_read_listings_basic():
    entries, errors = make_entries(BASIC)
    assert errors == []
    assert len(entries) == 2
    listing, profile_name = entries[0]
    assert listing.name == "Plate"
    assert listing.item_cost == pytest.approx(4.0)
    assert listing.tax_rate_percent == pytest.approx(6.35)
    assert profile_name == ""


def test_missing_required_column():
    entries, errors = make_entries("name,item_cost\nPlate,4.00\n")
    assert entries == []
    assert "sale_price" in errors[0]


def test_bad_number_row_skipped():
    csv_text = ("name,item_cost,sale_price\n"
                "Good,1.00,5.00\n"
                "Bad,free,5.00\n")
    entries, errors = make_entries(csv_text)
    assert len(entries) == 1
    assert len(errors) == 1
    assert "row 3" in errors[0]
    assert "isn't a number" in errors[0]


def test_currency_symbols_and_commas_ok():
    csv_text = 'item_cost,sale_price\n"$1,254.50",29.99\n'
    entries, errors = make_entries(csv_text)
    assert errors == []
    assert entries[0][0].item_cost == pytest.approx(1254.50)


def test_run_batch_with_profiles(tmp_path):
    entries, errors = make_entries(BASIC)
    assert errors == []
    results, fatal = run_batch(entries, default_profile_name="ebay")
    assert fatal == []
    assert [r["name"] for r in results] == ["Plate", "Book"]
    for row in results:
        assert row["profile"] == "ebay"
        assert row["break_even_price"] != ""
        assert row["profit"]


def test_run_batch_per_row_profile(tmp_path):
    csv_text = ("item_cost,sale_price,profile\n"
                "5.00,20.00,mercari\n"
                "5.00,20.00,amazon\n")
    entries, _ = make_entries(csv_text)
    results, errors = run_batch(entries, default_profile_name="ebay")
    assert errors == []
    assert results[0]["profile"] == "mercari"
    assert results[1]["profile"] == "amazon"
    # mercari fee = 10% of 20 = 2; amazon = 15% of 20 + 0.99 = 3.99
    assert results[0]["fees_total"] == pytest.approx(2.0)
    assert results[1]["fees_total"] == pytest.approx(3.99)


def test_run_batch_unknown_profile_is_row_error():
    entries, _ = make_entries("item_cost,sale_price,profile\n1.00,5.00,ghostplatform\n")
    results, errors = run_batch(entries, default_profile_name="ebay")
    assert results == []
    assert len(errors) == 1
    assert "ghostplatform" in errors[0]


def test_results_csv_round_trip():
    entries, _ = make_entries(BASIC)
    results, _ = run_batch(entries, default_profile_name="ebay")
    buffer = io.StringIO()
    write_results_csv(results, buffer)
    rows = list(csv.DictReader(io.StringIO(buffer.getvalue())))
    assert rows[0]["name"] == "Plate"
    assert rows[0]["fee_base"]  # written as text
    assert float(rows[0]["profit"]) == pytest.approx(results[0]["profit"], abs=0.01)
    assert set(rows[0].keys()) == set(rows[1].keys())
