import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from reseller_profit.models import ListingInput

PROFILES_PACKAGE_DIR = Path(__file__).parent / "fee_profiles"

VALID_BASES = ("sale", "sale_plus_shipping", "buyer_total")

KNOWN_TOP_KEYS = (
    "schema",
    "name",
    "display_name",
    "description",
    "currency",
    "final_value_fee",
    "order_fee_flat",
    "category_overrides",
    "notes",
    "disclaimer",
)
KNOWN_FEE_KEYS = ("base", "percent", "flat")
KNOWN_OVERRIDE_KEYS = ("match", "base", "percent", "flat", "note")


class ProfileError(ValueError):
    """Raised when a fee profile JSON is missing, malformed, or mistyped."""


@dataclass
class FeeComponent:
    """A percent-of-base plus a flat amount. Either can be zero."""

    percent: float = 0.0
    flat: float = 0.0

    def amount_on(self, base: float) -> float:
        return base * self.percent / 100.0 + self.flat


@dataclass
class FinalValueFee(FeeComponent):
    """The main cut the platform keeps. ``base`` chooses what it is figured on."""

    base: str = "sale"


@dataclass
class CategoryOverride:
    """Swap in a different fee for listings whose category matches a pattern."""

    match: str = ""
    component: FinalValueFee = field(default_factory=lambda: FinalValueFee("sale"))
    note: str = ""


@dataclass
class FeeProfile:
    """One marketplace's fee rules, loaded from editable JSON."""

    name: str
    source_path: Optional[Path] = None
    display_name: str = ""
    description: str = ""
    currency: str = "USD"
    final_value_fee: FinalValueFee = field(default_factory=lambda: FinalValueFee("sale"))
    order_fee_flat: float = 0.0
    category_overrides: List[CategoryOverride] = field(default_factory=list)
    notes: str = ""
    disclaimer: str = ""

    def override_for_category(self, category: str) -> Optional[CategoryOverride]:
        if not category:
            return None
        for override in self.category_overrides:
            if re.search(override.match, category, re.IGNORECASE):
                return override
        return None

    def describe(self) -> str:
        return self.display_name or self.name


def _require(expr: bool, message: str) -> None:
    if not expr:
        raise ProfileError(message)


def _parse_fee_spec(data: Dict, context: str) -> FinalValueFee:
    _require(isinstance(data, dict), f"{context} must be a JSON object.")
    bad = set(data) - set(KNOWN_FEE_KEYS)
    _require(not bad, f"{context} has unrecognized key(s): {', '.join(sorted(bad))}.")
    _require("base" not in data or data["base"] in VALID_BASES,
             f"{context}: base must be one of {', '.join(VALID_BASES)} (got {data.get('base')!r}).")
    percent = data.get("percent", 0.0)
    flat = data.get("flat", 0.0)
    for label, value in (("percent", percent), ("flat", flat)):
        _require(isinstance(value, (int, float)) and not isinstance(value, bool),
                 f"{context}: {label} must be a number.")
        _require(value >= 0, f"{context}: {label} can't be negative.")
    return FinalValueFee(base=data.get("base", "sale"), percent=float(percent), flat=float(flat))


def _parse_profile(data: Dict, source_path: Optional[Path]) -> FeeProfile:
    _require(isinstance(data, dict), "fee profile must be a JSON object.")
    bad = set(data) - set(KNOWN_TOP_KEYS)
    _require(not bad, f"fee profile has unrecognized key(s): {', '.join(sorted(bad))}.")
    _require(data.get("schema") == "asdale-profit-profile/1",
             "missing or wrong \"schema\"; expected \"asdale-profit-profile/1\".")
    name = data.get("name")
    _require(isinstance(name, str) and name.strip(), "missing \"name\" (short key, e.g. \"ebay\").")
    fvf = data.get("final_value_fee")
    _require(fvf is not None, "missing \"final_value_fee\".")
    final_value_fee = _parse_fee_spec(fvf, "\"final_value_fee\"")

    order_fee_flat = data.get("order_fee_flat", 0.0)
    _require(isinstance(order_fee_flat, (int, float)) and not isinstance(order_fee_flat, bool),
             "\"order_fee_flat\" must be a number.")
    _require(float(order_fee_flat) >= 0, "\"order_fee_flat\" can't be negative.")

    raw = data.get("category_overrides", [])
    _require(isinstance(raw, list), "\"category_overrides\" must be a list.")
    overrides: List[CategoryOverride] = []
    for item in raw:
        _require(isinstance(item, dict), "each category_override must be a JSON object.")
        bad = set(item) - set(KNOWN_OVERRIDE_KEYS)
        _require(not bad, f"category_override has unrecognized key(s): {', '.join(sorted(bad))}.")
        pattern = item.get("match", "")
        _require(isinstance(pattern, str) and pattern.strip(),
                 "category_override needs a \"match\" pattern.")
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ProfileError(f"category_override match {pattern!r} is not a valid regex: {exc}") from exc
        fee_only = {k: item[k] for k in KNOWN_FEE_KEYS if k in item}
        component = _parse_fee_spec(fee_only, f"category_override {pattern!r}")
        overrides.append(CategoryOverride(match=pattern, component=component,
                                          note=str(item.get("note", ""))))

    for override, item in zip(overrides, raw):
        if "base" not in item:
            override.component.base = final_value_fee.base
        if "flat" not in item:
            override.component.flat = final_value_fee.flat

    return FeeProfile(
        name=name,
        source_path=source_path,
        display_name=str(data.get("display_name", "")),
        description=str(data.get("description", "")),
        currency=str(data.get("currency", "USD")),
        final_value_fee=final_value_fee,
        order_fee_flat=float(order_fee_flat),
        category_overrides=overrides,
        notes=str(data.get("notes", "")),
        disclaimer=str(data.get("disclaimer", "")),
    )


def load_profile_file(path: Path) -> FeeProfile:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ProfileError(f"fee profile file not found: {path}") from exc
    except OSError as exc:
        raise ProfileError(f"fee profile file {path} could not be read: {exc}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProfileError(f"fee profile {path.name} is not valid JSON: line {exc.lineno}, "
                           f"column {exc.colno} ({exc.msg}).") from exc
    profile = _parse_profile(data, path)
    return profile


def load_profile(name: str, profiles_dir: Optional[Path] = None) -> FeeProfile:
    """Load by file path, by directory, or by name from the built-in set."""
    if not name:
        raise ProfileError("no fee profile given.")
    guess = Path(name)
    if guess.suffix.lower() == ".json":
        return load_profile_file(guess)
    directory = Path(profiles_dir) if profiles_dir else PROFILES_PACKAGE_DIR
    path = directory / f"{name.strip().lower()}.json"
    if not path.exists():
        available = ", ".join(p.stem for p in sorted(directory.glob("*.json"))) or "(none)"
        raise ProfileError(f"fee profile {name!r} not found. Available in {directory}: {available}")
    return load_profile_file(path)


def profiles(profiles_dir: Optional[Path] = None) -> List[FeeProfile]:
    directory = Path(profiles_dir) if profiles_dir else PROFILES_PACKAGE_DIR
    profiles_list = []
    for path in sorted(directory.glob("*.json")):
        try:
            profiles_list.append(load_profile_file(path))
        except ProfileError:
            continue
    return profiles_list
