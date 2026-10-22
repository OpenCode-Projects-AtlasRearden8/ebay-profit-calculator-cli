# Reseller Profit Calculator

A friendly command-line tool that answers the questions every reseller asks
before hitting "List": **"Will this listing actually make me money?"** and
**"What's the lowest price I can sell at without losing money?"**

It works for eBay, Amazon, and Mercari listings. It does the boring fee math
for you — item cost, sale price, shipping, sales tax, and marketplace fees —
and it never pretends to know fees it wasn't told about: every rate lives in
a plain JSON file you can open and edit yourself.

Part of the [Asdale Dynamics](https://dylanasdale.github.io) toolbox of
beginner-friendly tools. Written to be read: the code, the fee profiles, and
the README all try to explain themselves in plain English.

## Install

You need Python 3.9 or newer. From this folder:

```bash
pip install .
```

That gives you a `reseller-profit` command (plus a shorter alias,
`profitcalc`). For development, use `pip install -e .` and `pip install
pytest` to run the tests.

## Quick start

Say you bought something for $10, you'll list it at $50, you're charging the
buyer $8 shipping but shipping really costs you $5:

```bash
reseller-profit single --cost 10 --price 50 --ship-charged 8 --ship-cost 5 --profile ebay
```

You'll get something like:

```
  fee_base charged on buyer total (price + shipping + tax):
  fees total ....... $9.87
  PROFIT ........... $33.13  (margin 56.6%, ROI 331.3%)
  break-even ....... sell at $9.87
```

Two big numbers and what they mean:

- **PROFIT** — what goes in your pocket after the platform takes its cut.
  *Margin* is profit as a slice of what the buyer paid; *ROI* is profit
  compared to what you paid for the item.
- **break-even** — the sale price where profit is exactly $0. Anything below
  it loses money, anything above it makes money.

Copy the numbers in this README and you should see these same ones
(they're also covered by the automated tests).

## The four commands

| Command | What it does |
| --- | --- |
| `reseller-profit single ...` | Profit, fees, margin, ROI, and break-even for one listing |
| `reseller-profit break-even ...` | Just the break-even sale price |
| `reseller-profit batch listings.csv` | The same math for every row of a CSV file |
| `reseller-profit profiles` | List the fee profiles you can use |

### Inputs for `single` and `break-even`

| Flag | Meaning | Default |
| --- | --- | --- |
| `--cost` | What YOU paid for the item | `$0` |
| `--price` | Sale price the buyer pays for the item (not counting shipping or tax) | `$0` |
| `--ship-charged` | What you charge the buyer for shipping | `$0` |
| `--ship-cost` | What shipping actually costs you | `$0` |
| `--tax` | Sales tax rate as a percent, e.g. `7.25` | `0` |
| `--category` | A category word like `books`, to trigger category-specific fee rates | *(none)* |
| `--profile` | Fee profile name or path to a JSON file | `ebay` |
| `--profiles-dir` | Folder to look in for custom fee-profile JSON files | built-ins |

How tax is handled, in one sentence: the platform collects it from the buyer
and passes it to you to remit, so it never changes your profit by itself —
but some platforms do charge their fee *on the tax too*, and the fee profile
decides whether that's modeled (see `base` below).

## Fee profiles: the numbers live in JSON, not in code

Marketplace fees are a moving target — they vary by category, seller level,
and year. So this tool ships fee *patterns*, not fee *claims*: JSON files you
can read, edit, and swap in one argument.

Find them with:

```bash
reseller-profit profiles
python -c "import reseller_profit.profiles as p; print(p.PROFILES_PACKAGE_DIR)"
```

Copy one out, edit it, and point at it with either `--profiles-dir` (a folder
of profiles) or `--profile path/to/my-ebay.json` (a specific file). The
structure is small:

```json
{
  "schema": "asdale-profit-profile/1",
  "name": "ebay",
  "display_name": "eBay (US, standard seller)",
  "currency": "USD",
  "final_value_fee": {
    "base": "buyer_total",
    "percent": 13.6,
    "flat": 0.30
  },
  "order_fee_flat": 0.0,
  "category_overrides": [
    { "match": "book|magazine|vhs", "percent": 15.1,
      "note": "eBay's higher rate for books, movies, and music." }
  ]
}
```

Field by field:

- **`final_value_fee`** — the main cut the platform keeps.
  - `base` chooses what the percent applies to:
    - `"sale"` — just the item price (Mercari)
    - `"sale_plus_shipping"` — item price plus shipping (Amazon, most of the time)
    - `"buyer_total"` — item price plus shipping plus sales tax (eBay's policy)
  - `percent` — the percentage, `13.6` means 13.6%
  - `flat` — a fixed per-sale amount on top, like eBay's $0.30
- **`order_fee_flat`** — anything flat and per-order, like Amazon's $0.99
  individual-seller fee (set it to `0` if you pay the monthly Pro plan).
- **`category_overrides`** — a `match` pattern (simple regular expression,
  matched without case sensitivity against your `--category` text) plus the
  different fee to use for those items. Any of `base`, `percent`, or `flat`
  you leave out is inherited from the main `final_value_fee`.

The files say it plainly too, in their own `notes` and `disclaimer` fields:
**these are edited-by-you starting points, not official data.** If a fee
changes, you change the JSON — no code knowledge needed. The tool also
catches typos (a misspelled key like `"percnt"` fails loudly instead of
silently turning off a fee).

## Batch mode: one CSV in, one CSV out

Make a CSV like `sample_listings.csv` in this repo (this exact file runs end
to end):

```csv
name,category,item_cost,sale_price,shipping_charged,shipping_cost,tax_rate,profile
Vintage Vanity Plate,collectibles,4.00,29.99,6.95,6.15,6.35,ebay
Mass Market Paperback,books,0.50,7.99,3.49,3.05,0.00,ebay
USB-C Cable (Lot of 2),electronics,7.50,19.99,0.00,4.45,0.00,amazon
```

Column notes:

- Required: `item_cost` and `sale_price`.
- Optional: `name`, `category`, `shipping_charged`, `shipping_cost`,
  `tax_rate` (a percent), and `profile` (per-row, e.g. mix platforms in one
  file). Anything missing is treated as zero.
- Money like `$1,254.50` and `1,254.50` is fine — dollar signs and commas
  are stripped before parsing.
- `category` and `tax_rate` also accept the explicit names `category`
  and `tax_rate` only; there are no hidden aliases to trip over.

Run it:

```bash
reseller-profit batch listings.csv --profile ebay
```

You get a human-readable summary in the terminal (per-row profit, margin,
break-even, and a TOTAL) plus a results CSV — by default
`listings.results.csv` next to your input, or an exact path with `--out
results.csv`, or `--out -` to stream the CSV to the terminal.

Rows that can't be computed (a typo like `free` in a number column, an
unknown profile name) are skipped with a plain-English message on each,
the good rows still get computed, and the command exits with an error code
so scripts can tell something was off.

## Using it from Python

The CLI is a thin shell around a importable library:

```python
from reseller_profit import ListingInput, load_profile, compute_profit

listing = ListingInput(item_cost=10.0, sale_price=50.0,
                       shipping_charged=8.0, shipping_cost=5.0,
                       tax_rate_percent=0.0, category="books")
result = compute_profit(listing, load_profile("ebay"))
print(result.profit, result.margin_percent, result.break_even_price)
```

`compute_profit` returns a `ProfitResult` with every intermediate number:
`fees` (one line per fee, what it was charged on), `fee_base`,
`tax_collected`, `shipping_net`, `revenue`, `profit`, `margin_percent`,
`roi_percent`, and `break_even_price`.

## Known gaps (honest list)

- **FBA and fulfillment fees aren't modeled.** Amazon pick-and-pack costs
  belong in `item_cost` or `shipping_cost` for now; an FBA fee line in the
  profile schema is the natural next step.
- Fee profiles are patterns, not a fee database — there's no auto-updating
  of marketplace rates, by design (local-first, no APIs, no accounts).
- **Break-even only varies the sale price.** It holds shipping charged, tax,
  and item cost fixed; it won't co-optimize "charge more for shipping"
  tradeoffs.
- Promotions, seller-funded ad rates (e.g. eBay promoted listings), returned
  or refunded items, and multi-quantity sold-through aren't modeled.
- International selling (currency conversion, international site fees,
  VAT/GST) isn't modeled; profiles are USD-shaped by default.
- Tax is a simple percent on item + charged shipping; it doesn't differ by
  state or handle tax-inclusive pricing.

## Development

```bash
pip install -e .
pip install pytest
python -m pytest          # the whole test suite (43 tests)
```

Project layout: `src/reseller_profit/` holds the library and CLI
(`calculator.py` does the math, `profiles.py` reads and validates the JSON
fee profiles, `batch.py` runs CSV mode, `cli.py` is the command line).
Fee-profile JSONs live in `src/reseller_profit/fee_profiles/`.

## License

MIT. Copyright (c) 2026 Asdale Dynamics, LLC.
This is a practical-estimates tool from a small company that likes plain
English — it is not financial, tax, or accounting advice.
