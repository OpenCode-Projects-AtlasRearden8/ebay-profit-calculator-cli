"""Reseller profit calculator: eBay, Amazon, Mercari.

A small, beginner-friendly library and CLI for estimating profit on a
marketplace listing and finding the break-even sale price.
"""

__version__ = "1.0.0"

from reseller_profit.models import ListingInput, ProfitResult
from reseller_profit.profiles import FeeProfile, ProfileError, load_profile, profiles
from reseller_profit.calculator import break_even_price, compute_profit

__all__ = [
    "ListingInput",
    "ProfitResult",
    "FeeProfile",
    "ProfileError",
    "load_profile",
    "profiles",
    "compute_profit",
    "break_even_price",
    "__version__",
]
