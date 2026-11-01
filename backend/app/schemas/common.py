"""Shared schema types.

Money is stored as NUMERIC(15,2) and handled as Decimal inside the backend so
that amounts are never rounded by binary floating point. At the API edge it is
accepted as a JSON number or string with at most two decimal places and is
returned as a JSON number, so existing clients keep working.
"""
from decimal import Decimal
from typing import Annotated

from pydantic import Field, PlainSerializer

# Input: positive amount, up to 13 integer digits and 2 decimals.
Money = Annotated[Decimal, Field(gt=0, max_digits=15, decimal_places=2)]
# Input: zero allowed (e.g. a contract whose deposit is not yet required).
MoneyOrZero = Annotated[Decimal, Field(ge=0, max_digits=15, decimal_places=2)]
# Output: serialised as a JSON number.
MoneyOut = Annotated[Decimal, PlainSerializer(lambda v: float(v), return_type=float, when_used="json")]
