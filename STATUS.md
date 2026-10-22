# STATUS.md — Reseller Profit Calculator

Last updated: 2026-10-22

## What was built

A local-first Python CLI and library (`reseller_profit`, installed command:
`reseller-profit`) that estimates reseller profit for eBay, Amazon, and
Mercari listings and finds the break-even sale price.

- **Library** (`src/reseller_profit/`):
  - `models.py` — `ListingInput` / `ProfitResult` / `FeeLine` dataclasses.
  - `profiles.py` — loads and strictly validates fee profiles from editable
    JSON (`asdale-profit-profile/1` schema). Unknown keys, negative fees,
    invalid regexes, wrong `base` values, and typos all fail loudly with
    plain-English messages. Profile resolution: by name from the built-in
    folder, by path, or by custom folder.
  - `calculator.py` — profit math (fees, tax pass-through, shipping net,
    margin, ROI) and break-even solving by bisection; returns `None` when no
    price can ever be profitable.
  - `batch.py` — CSV in / CSV out batch mode with per-row error reporting;
    accepts `$` and `,` in money cells; per-row `profile` column supported.
  - `cli.py` — argparse CLI with subcommands `single`, `break-even`,
    `batch`, `profiles`; both `reseller-profit` and `profitcalc` entry
    points, plus `python -m reseller_profit`.
- **Editable fee profiles** (`src/reseller_profit/fee_profiles/`):
  `ebay.json`, `amazon.json`, `mercari.json`. Rates are data, not
  hard-coded claims: each file carries `notes` and `disclaimer` fields and
  is meant to be copied and edited. Category overrides inherit the main
  fee's `flat`/`base` unless overridden.
- **Sample data**: `sample_listings.csv` (five rows across all three
  platforms, includes the higher book rate on eBay).
- **Tests**: 43 pytest tests covering calculator math (hand-verified fee
  arithmetic), profile loading/validation, batch parsing including error
  rows, CLI exit codes and output formats, and a break-even property check
  (profit at the solved break-even price is ~zero for all built-in profiles).
- **Packaging**: `pyproject.toml` (setuptools, src layout, package data),
  MIT `LICENSE` (Copyright (c) 2026 Asdale Dynamics, LLC), plain-English
  `README.md`.
- Init behavior: configurable; no network calls anywhere, no secrets, no
  personal data.

## How to run it

```bash
pip install .                       # or: pip install -e . for development
reseller-profit profiles            # list fee profiles and where they live
reseller-profit single --cost 10 --price 50 --ship-charged 8 --ship-cost 5 --profile ebay
reseller-profit break-even --cost 12 --profile mercari
reseller-profit batch sample_listings.csv        # writes sample_listings.results.csv
reseller-profit batch listings.csv --out -
```

Library use: `from reseller_profit import ListingInput, load_profile, compute_profit`.

## Verification results (this machine, Python 3.13.5)

- `python -m pytest -q` → **43 passed**.
- `python -m build` → built `sdist` + wheel successfully.
- Wheel smoke test: installed the wheel into a clean venv; `reseller-profit`
  and `profitcalc` both ran; fee-profile JSONs shipped as package data;
  `python -m reseller_profit --version` → `reseller-profit 1.0.0`.
- End-to-end CLI: `single`, `break-even`, `profiles`, and
  `batch sample_listings.csv` all produced sensible output (e.g. vanity
  plate: profit $18.80, margin 50.9%, break-even $6.25; batch TOTAL profit
  $61.73 across five rows).
- Error paths checked: unknown profile, negative inputs, bad CSV numbers,
  missing CSV columns — each exits nonzero with a plain-English message and
  leaves the good rows computed.
- Git initialized locally; one commit on `main`. Never pushed, no remote,
  nothing published.

## Known gaps

- FBA/fulfillment fees and Amazon referral-fee nuances beyond the override
  list aren't modeled (fold them into `item_cost`/`shipping_cost` today).
- Fee profiles are editable patterns, not a maintained fee database; rates
  are starting points and users must verify against the marketplaces.
- Break-even varies only the sale price (tax and shipping held fixed);
  no co-optimization of shipping-charged vs price.
- Ads/promoted-listing costs, promotions, refunds/returns, multi-quantity
  sell-through, currency conversion, VAT/GST, and international site fees
  are out of scope for v1.
- Tax is a single percent applied to item price + charged shipping; no
  state-by-state or tax-inclusive handling.
