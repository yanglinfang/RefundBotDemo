"""
Helpers for working with customer identifiers.
"""

import re

CUSTOMER_ID_PATTERN = re.compile(r"^CUST-[A-Z0-9]+$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_customer_id(value: str) -> bool:
    """Return True when the value matches the canonical customer ID format."""
    if not value:
        return False
    return bool(CUSTOMER_ID_PATTERN.match(value.strip()))


def is_email(value: str) -> bool:
    """Return True when the value looks like an email address."""
    if not value:
        return False
    return bool(EMAIL_PATTERN.match(value.strip()))
