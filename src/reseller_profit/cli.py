import argparse
import csv
import sys
from pathlib import Path
from typing import List, Optional

from reseller_profit import __version__
from reseller_profit.batch import (RESULTS_COLUMNS, read_listings, run_batch,
                                   write_results_csv)
from reseller_profit.calculator import compute_profit
from reseller_profit.models import ListingInput, money, percent
from reseller_profit.profiles import PROFILES_PACKAGE_DIR, ProfileError, load_profile, profiles


def listing_from_args(args) -> ListingInput:
    return ListingInput(
        name=args.name or "item",
        item_cost=args.cost,
        sale_price=args.price,
        shipping_charged=args.ship_charged,
        shipping_cost=args.ship_cost,
        tax_rate_percent=args.tax,
        category=args.category or "",
    )


def _print_report(result, stream=None) -> None:
    out = _format_report(result)
    print(out, file=stream or sys.stdout)


def _format_report(result) -> str:
    lines = []
    lines.append(f"Item: {result.profile_display_name} fee profile")
    lines.append(f"  sale price ....... {money(result.sale_price)}")
    lines.append(f"  shipping charged . {money(result.shipping_charged)}"
                 + (f"  (cost {money(result.shipping_cost)}, net {money(result.shipping_net)})"
                    if (result.shipping_charged or result.shipping_cost) else ""))
    lines.append(f"  item cost ........ {money(result.item_cost)}")
    if result.tax_collected:
        lines.append(f"  sales tax collected, passed through: {money(result.tax_collected)}"
                     f" at {result.tax_rate_percent:g}%")
    if result.fees:
        lines.append(f"  fees (charged on {result.fee_base_label}, {money(result.fee_base)}):")
        for fee in result.fees:
            label = fee.label + (f" — on {fee.basis}" if fee.basis else "")
            lines.append(f"    {label:<38} {money(fee.amount)}")
    else:
        lines.append(f"  fees (charged on {result.fee_base_label}, {money(result.fee_base)}) ... {money(0.0)}")
    lines.append(f"  fees total ....... {money(result.fees_total)}")
    lines.append(f"  PROFIT ........... {money(result.profit)}"
                 f"  (margin {percent(result.margin_percent)}, ROI {percent(result.roi_percent)})")
    if result.break_even_price is None:
        lines.append("  break-even ....... never (no sale price makes this profitable)")
    else:
        lines.append(f"  break-even ....... sell at {money(result.break_even_price)}")
    return "\n".join(lines)


def _print_batch_summary(results: List[dict], stream=None) -> None:
    stream = stream or sys.stdout
    if not results:
        print("No rows computed.", file=stream)
        return
    print(f"{len(results)} listing(s):", file=stream)
    for row in results:
        be = row["break_even_price"]
        break_even = f"{money(be)}" if be != "" else "never"
        print(f"  {row['name']:<24} profit {money(row['profit']):>9}"
              f"  (margin {row['margin_percent']:>6}%, break-even {break_even})",
              file=stream)
    total_profit = sum(row["profit"] for row in results)
    print(f"  {'TOTAL':<24} profit {money(total_profit):>9}", file=stream)


def cmd_single(args) -> int:
    try:
        listing = listing_from_args(args)
        profile = load_profile(args.profile, args.profiles_dir)
        result = compute_profit(listing, profile)
    except (ValueError, ProfileError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    _print_report(result)
    sys.stdout.flush()
    if profile.disclaimer:
        print(f"\nNote: {profile.disclaimer}", file=sys.stderr)
    return 0


def cmd_break_even(args) -> int:
    try:
        listing = listing_from_args(args)
        profile = load_profile(args.profile, args.profiles_dir)
        result = compute_profit(listing, profile)
    except (ValueError, ProfileError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    if result.break_even_price is None:
        print("No break-even price: with these fees and costs, no reasonable sale "
              "price makes this listing profitable.", file=sys.stderr)
        return 1
    print(money(result.break_even_price))
    return 0


def cmd_batch(args) -> int:
    try:
        with open(args.input, newline="", encoding="utf-8") as handle:
            entries, errors = read_listings(handle)
    except OSError as exc:
        print(f"Error: could not read CSV {args.input}: {exc}", file=sys.stderr)
        return 1
    if errors:
        for message in errors:
            print(f"Skipped: {message}", file=sys.stderr)

    results, fatal = run_batch(entries, default_profile_name=args.profile,
                               profiles_dir=args.profiles_dir)
    for message in fatal:
        print(f"Skipped: {message}", file=sys.stderr)
    all_errors = errors + fatal

    if args.out == "-":
        write_results_csv(results, sys.stdout)
        return 1 if all_errors else 0

    out_path = Path(args.out) if args.out else Path(args.input).with_suffix(".results.csv")
    try:
        with open(out_path, "w", newline="", encoding="utf-8") as handle:
            write_results_csv(results, handle)
    except OSError as exc:
        print(f"Error: could not write {out_path}: {exc}", file=sys.stderr)
        return 1
    _print_batch_summary(results)
    if results:
        print(f"Wrote {out_path}")
    if all_errors:
        print(f"{len(all_errors)} row(s) were skipped; see messages above.", file=sys.stderr)
        return 1
    return 0


def cmd_profiles(args) -> int:
    directory = Path(args.profiles_dir) if args.profiles_dir else PROFILES_PACKAGE_DIR
    print(f"Fee profiles in {directory}:")
    found = profiles(directory)
    if not found:
        print("  (none — put a fee-profile JSON in this folder)")
        return 0
    for profile in found:
        print(f"  {profile.name:<10} {profile.describe()}")
        if profile.description:
            print(f"             {profile.description}")
    return 0


def _add_listing_arguments(parser) -> None:
    parser.add_argument("--cost", required=False, default=0.0, type=float,
                        help="what YOU paid for the item (item cost)")
    parser.add_argument("--price", required=False, default=0.0, type=float,
                        help="the sale price the buyer pays for the item (not counting shipping or tax)")
    parser.add_argument("--ship-cost", default=0.0, type=float,
                        help="what shipping costs YOU to buy at the post office or broker")
    parser.add_argument("--ship-charged", default=0.0, type=float,
                        help="what the BUYER is charged for shipping")
    parser.add_argument("--tax", default=0.0, type=float,
                        help="sales tax rate as a percent, e.g. 7.25")
    parser.add_argument("--category", default="", help="category word or phrase, e.g. 'books'")
    parser.add_argument("--name", default="", help="optional label for the item in the report")
    parser.add_argument("--profile", default="ebay",
                        help="fee profile name (or path to a JSON file); default: ebay")
    parser.add_argument("--profiles-dir", default=None,
                        help="folder to look in for fee-profile JSON files instead of the built-ins")


def build_parser() -> argparse.ArgumentParser:
    epilog = "Examples:\n" \
             "  reseller-profit single --cost 10 --price 50 --ship-cost 5 --ship-charged 8\n" \
             "  reseller-profit break-even --cost 10 --profile mercari\n" \
             "  reseller-profit batch listings.csv --out results.csv"
    parser = argparse.ArgumentParser(
        prog="reseller-profit",
        description="Estimate reseller profit for eBay, Amazon, or Mercari listings "
                    "and find the break-even sale price.",
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--profiles-dir", default=None, help=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest="command", required=True)

    single = sub.add_parser("single", help="profit for one listing")
    _add_listing_arguments(single)
    single.set_defaults(func=cmd_single)

    breakeven = sub.add_parser("break-even", help="just the break-even sale price")
    _add_listing_arguments(breakeven)
    breakeven.set_defaults(func=cmd_break_even)

    batch = sub.add_parser("batch", help="profit for every row of a CSV file")
    batch.add_argument("input", help="CSV with columns described in the README")
    batch.add_argument("--out", default=None,
                       help="results CSV path (default: <input>.results.csv; use - for stdout). "
                            "By default the results file is written next to the input.")
    batch.add_argument("--profile", default="ebay",
                       help="default fee profile when the CSV has no profile column (default: ebay)")
    batch.add_argument("--profiles-dir", default=None,
                       help="folder to look in for fee-profile JSON files instead of the built-ins")
    batch.set_defaults(func=cmd_batch)

    prof = sub.add_parser("profiles", help="list available fee profiles")
    prof.add_argument("--profiles-dir", default=None,
                      help="folder of fee-profile JSON files to list instead of the built-ins")
    prof.set_defaults(func=cmd_profiles)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    profiles_dir = getattr(args, "profiles_dir", None)
    if profiles_dir:
        args.profiles_dir = Path(profiles_dir)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
