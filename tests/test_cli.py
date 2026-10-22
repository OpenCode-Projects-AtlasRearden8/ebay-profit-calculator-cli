import csv
import io

import pytest

from reseller_profit.cli import main


BASIC_CSV = "item_cost,sale_price,shipping_charged,shipping_cost,tax_rate,category\n4.00,29.99,6.95,6.15,6.35,collectibles\n"


def test_single_output(capsys):
    code = main(["single", "--cost", "10", "--price", "50",
                 "--ship-cost", "5", "--ship-charged", "8", "--profile", "ebay"])
    out = capsys.readouterr()
    assert code == 0
    assert "PROFIT" in out.out
    assert "break-even" in out.out
    assert "$" in out.out


def test_break_even_output(capsys):
    code = main(["break-even", "--cost", "10", "--profile", "ebay"])
    out = capsys.readouterr()
    assert code == 0
    assert out.out.startswith("$")


def test_profiles_command(capsys):
    code = main(["profiles"])
    out = capsys.readouterr()
    assert code == 0
    for name in ("ebay", "amazon", "mercari"):
        assert name in out.out


def test_bad_profile_exits_nonzero(capsys):
    code = main(["single", "--cost", "1", "--price", "5", "--profile", "ghost"])
    err = capsys.readouterr()
    assert code == 1
    assert "not found" in err.err


def test_negative_cost_exits_nonzero(capsys):
    code = main(["single", "--cost", "-5", "--price", "20"])
    err = capsys.readouterr()
    assert code == 1
    assert "negative" in err.err


def test_batch_writes_results(tmp_path, capsys):
    csv_path = tmp_path / "listings.csv"
    csv_path.write_text(BASIC_CSV, encoding="utf-8")
    code = main(["batch", str(csv_path), "--profile", "ebay"])
    out = capsys.readouterr()
    assert code == 0
    results_path = tmp_path / "listings.results.csv"
    assert results_path.exists()
    assert "1 listing(s)" in out.out
    rows = list(csv.DictReader(io.open(results_path, encoding="utf-8")))
    assert len(rows) == 1
    assert rows[0]["profit"]


def test_batch_custom_out_stdout(tmp_path, capsys):
    csv_path = tmp_path / "listings.csv"
    csv_path.write_text(BASIC_CSV, encoding="utf-8")
    code = main(["batch", str(csv_path), "--out", "-", "--profile", "mercari"])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out.startswith("name,category,profile")
    assert "mercari" in captured.out


def test_batch_bad_rows_reported(tmp_path, capsys):
    csv_path = tmp_path / "listings.csv"
    csv_path.write_text(BASIC_CSV + "Ghost_Item,bogus,5.00\n", encoding="utf-8")
    code = main(["batch", str(csv_path), "--profile", "ebay"])
    captured = capsys.readouterr()
    assert code == 1
    assert "row 3" in captured.err
    assert "isn't a number" in captured.err
    assert "skipped" in captured.err.lower()
    results_path = tmp_path / "listings.results.csv"
    rows = list(csv.DictReader(io.open(results_path, encoding="utf-8")))
    assert len(rows) == 1


def test_batch_missing_file(tmp_path, capsys):
    code = main(["batch", str(tmp_path / "nothere.csv")])
    err = capsys.readouterr()
    assert code == 1
    assert "could not read" in err.err


def test_version(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0


def test_help(capsys):
    with pytest.raises(SystemExit):
        main(["single", "--help"])
    captured = capsys.readouterr()
    assert "--ship-cost" in captured.out
