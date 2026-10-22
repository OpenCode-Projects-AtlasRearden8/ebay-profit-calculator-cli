import json
from pathlib import Path

import pytest

from reseller_profit.profiles import (PROFILES_PACKAGE_DIR, ProfileError,
                                      load_profile, load_profile_file,
                                      profiles)


def test_builtin_profiles_load():
    found = profiles()
    names = {p.name for p in found}
    assert names == {"ebay", "amazon", "mercari"}


def test_load_profile_by_name_and_path():
    by_name = load_profile("ebay")
    by_path = load_profile_file(PROFILES_PACKAGE_DIR / "ebay.json")
    assert by_name.name == by_path.name == "ebay"
    assert by_name.final_value_fee.percent == pytest.approx(13.6)
    assert by_name.final_value_fee.flat == pytest.approx(0.30)
    assert by_name.final_value_fee.base == "buyer_total"
    assert by_name.currency == "USD"


def test_load_profile_custom_dir(tmp_path):
    data = {
        "schema": "asdale-profit-profile/1",
        "name": "yard_sale",
        "final_value_fee": {"base": "sale", "percent": 0.0, "flat": 0.0},
        "order_fee_flat": 0.0,
    }
    path = tmp_path / "yard_sale.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    profile = load_profile("yard_sale", profiles_dir=tmp_path)
    assert profile.name == "yard_sale"
    assert profile.order_fee_flat == 0.0


def test_unknown_profile_message(tmp_path):
    with pytest.raises(ProfileError, match="Available"):
        load_profile("nope", profiles_dir=tmp_path)


def test_missing_file(tmp_path):
    with pytest.raises(ProfileError, match="not found"):
        load_profile(tmp_path / "ghost.json")


def test_invalid_json(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{ this is not json", encoding="utf-8")
    with pytest.raises(ProfileError, match="not valid JSON"):
        load_profile_file(path)


def test_missing_required_fields(tmp_path):
    path = tmp_path / "thin.json"
    path.write_text(json.dumps({"schema": "asdale-profit-profile/1"}), encoding="utf-8")
    with pytest.raises(ProfileError):
        load_profile_file(path)


def test_wrong_schema_rejected(tmp_path):
    data = {"schema": "wrong/2", "name": "x", "final_value_fee": {"base": "sale"}}
    path = tmp_path / "x.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ProfileError, match="schema"):
        load_profile_file(path)


def test_typo_key_caught(tmp_path):
    data = {
        "schema": "asdale-profit-profile/1",
        "name": "typo",
        "final_value_fee": {"base": "sale", "percnt": 10.0},
    }
    path = tmp_path / "typo.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ProfileError, match="percnt"):
        load_profile_file(path)


def test_bad_fee_base_caught(tmp_path):
    data = {
        "schema": "asdale-profit-profile/1",
        "name": "badbase",
        "final_value_fee": {"base": "everything_the_buyer_has"},
    }
    path = tmp_path / "badbase.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ProfileError, match="base"):
        load_profile_file(path)


def test_negative_fee_caught(tmp_path):
    data = {
        "schema": "asdale-profit-profile/1",
        "name": "negative",
        "final_value_fee": {"base": "sale", "percent": -5.0},
    }
    path = tmp_path / "negative.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ProfileError, match="can't be negative"):
        load_profile_file(path)


def test_bad_regex_override_caught(tmp_path):
    data = {
        "schema": "asdale-profit-profile/1",
        "name": "badregex",
        "final_value_fee": {"base": "sale"},
        "category_overrides": [{"match": "([unclosed", "percent": 5.0}],
    }
    path = tmp_path / "badregex.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ProfileError, match="valid regex"):
        load_profile_file(path)
