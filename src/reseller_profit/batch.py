import csv
from pathlib import Path
from typing import Dict, IO, List, Optional, Tuple

from reseller_profit.calculator import compute_profit
from reseller_profit.models import ListingInput
from reseller_profit.profiles import FeeProfile, ProfileError, load_profile

REQUIRED_COLUMNS = ("item_cost", "sale_price")

RESULTS_COLUMNS = (
    "name", "category", "profile", "item_cost", "sale_price",
    "shipping_charged", "shipping_cost", "tax_rate_percent", "tax_collected",
    "fee_base", "fees_total", "shipping_net", "profit",
    "margin_percent", "roi_percent", "break_even_price",
)


class RowError(ValueError):
    """One bad CSV row: row number plus a plain-English reason."""


def _number(row: Dict[str, str], column: str, row_number: int, default: float = 0.0) -> float:
    raw = str(row.get(column) or "").strip()
    if not raw:
        return default
    cleaned = raw.replace(",", "").replace("$", "")
    try:
        value = float(cleaned)
    except ValueError as exc:
        raise RowError(f"row {row_number}: column \"{column}\" has {raw!r}, which isn't a number.") from exc
    if value < 0:
        raise RowError(f"row {row_number}: column \"{column}\" can't be negative ({raw}).")
    return value


def _listing_from_row(row: Dict[str, str], row_number: int) -> Tuple[ListingInput, str]:
    missing = [c for c in REQUIRED_COLUMNS if c not in row]
    if missing:
        raise RowError(f"row {row_number}: missing required column(s): {', '.join(missing)}")
    listing = ListingInput(
        name=str(row.get("name") or "").strip() or f"row {row_number}",
        item_cost=_number(row, "item_cost", row_number),
        sale_price=_number(row, "sale_price", row_number),
        shipping_charged=_number(row, "shipping_charged", row_number),
        shipping_cost=_number(row, "shipping_cost", row_number),
        tax_rate_percent=_number(row, "tax_rate", row_number),
        category=str(row.get("category") or "").strip(),
    )
    profile_name = str(row.get("profile") or "").strip()
    return listing, profile_name


def read_listings(csv_source: IO) -> Tuple[List[Tuple[ListingInput, str]], List[str]]:
    """Parse a CSV file handle into (listing, profile-name-or-empty) pairs."""
    entries: List[Tuple[ListingInput, str]] = []
    errors: List[str] = []
    reader = csv.DictReader(csv_source)
    if reader.fieldnames is None:
        return entries, ["CSV file has no header row."]
    fieldnames = [f.strip() for f in reader.fieldnames]
    missing = [c for c in REQUIRED_COLUMNS if c not in fieldnames]
    if missing:
        return entries, [f"CSV is missing required column(s): {', '.join(missing)}. "
                         f"Expected at least: item_cost, sale_price"]
    for row_number, row in enumerate(reader, start=2):
        row = {(k or "").strip(): (v if v is not None else "") for k, v in row.items() if k is not None}
        try:
            entries.append(_listing_from_row(row, row_number))
        except RowError as exc:
            errors.append(str(exc))
        except ValueError as exc:
            errors.append(f"row {row_number}: {exc}")
    return entries, errors


def run_batch(entries: List[Tuple[ListingInput, str]], default_profile_name: str = "ebay",
              profiles_dir: Optional[Path] = None) -> Tuple[List[Dict], List[str]]:
    """Compute every listing. Fatal errors (unknown profile) abort; returns rows and errors."""
    results: List[Dict] = []
    errors: List[str] = []
    profile_cache: Dict[str, FeeProfile] = {}

    def profile_for(name: str, listing_name: str) -> FeeProfile:
        key = (name or default_profile_name).strip().lower()
        if key not in profile_cache:
            try:
                profile_cache[key] = load_profile(key, profiles_dir)
            except (ProfileError, ValueError) as exc:
                raise ValueError(f"{listing_name}: {exc}") from exc
        return profile_cache[key]

    for listing, profile_name in entries:
        if not profile_name and not default_profile_name:
            errors.append(f"{listing.name}: no profile given (add a \"profile\" column "
                          f"or pass --profile).")
            continue
        try:
            profile = profile_for(profile_name, listing.name)
            result = compute_profit(listing, profile)
        except (ValueError, ProfileError) as exc:
            errors.append(str(exc))
            continue
        rounded = {
            "name": listing.name,
            "category": listing.category,
            "profile": profile.name,
            "item_cost": round(listing.item_cost, 2),
            "sale_price": round(listing.sale_price, 2),
            "shipping_charged": round(listing.shipping_charged, 2),
            "shipping_cost": round(listing.shipping_cost, 2),
            "tax_rate_percent": round(listing.tax_rate_percent, 4),
            "tax_collected": round(result.tax_collected, 2),
            "fee_base": round(result.fee_base, 2),
            "fees_total": round(result.fees_total, 2),
            "shipping_net": round(result.shipping_net, 2),
            "profit": round(result.profit, 2),
            "margin_percent": round(result.margin_percent, 1),
            "roi_percent": round(result.roi_percent, 1),
            "break_even_price": (round(result.break_even_price, 2)
                                 if result.break_even_price is not None else ""),
        }
        results.append(rounded)
    return results, errors


def write_results_csv(results: List[Dict], destination: IO) -> None:
    writer = csv.DictWriter(destination, fieldnames=RESULTS_COLUMNS)
    writer.writeheader()
    for row in results:
        writer.writerow(row)
