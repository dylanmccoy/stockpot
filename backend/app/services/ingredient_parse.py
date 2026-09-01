"""Pure ingredient parser module.

Implements deterministic ingredient parsing per spec.md §2.3.
"""

import math
import re
from typing import Optional

from app.units import OPAQUE_TOKENS, normalize_unit_token, parse_unit


# Unicode vulgar fractions
_VULGAR_FRACTIONS = {
    "½": 0.5,
    "¼": 0.25,
    "¾": 0.75,
    "⅓": 1.0 / 3.0,
    "⅔": 2.0 / 3.0,
    "⅛": 0.125,
}

# Bounded, whitespace-tolerant "to taste" matcher. Used for BOTH detection and
# removal so the two never disagree (a bare substring test misses "to   taste"
# and false-fires on "to Tastefully ...").
_TO_TASTE_RE = re.compile(r"\bto\s+taste\b", re.IGNORECASE)


def _is_unit_word(candidate: str) -> bool:
    """True if candidate is a known synonym or a deliberately-opaque unit token."""
    if parse_unit(candidate) is not None:
        return True
    normalized = normalize_unit_token(candidate)
    return normalized is not None and normalized in OPAQUE_TOKENS


def _parse_number(s: str) -> Optional[float]:
    """Parse a number in various formats.

    Accepts:
    - Integer: 2
    - Decimal: 0.5
    - Simple fraction: 3/4
    - Mixed number: 1 1/2
    - Vulgar fraction: ½

    Returns None if parsing fails, or if the result is 0, negative, or non-finite.
    """
    s = s.strip()

    if not s:
        return None

    # Try vulgar fraction first
    if s in _VULGAR_FRACTIONS:
        result = _VULGAR_FRACTIONS[s]
        if result > 0 and math.isfinite(result):
            return result
        return None

    # Try mixed number (e.g., "1 1/2")
    # Look for pattern: number space fraction
    mixed_match = re.match(r"^(\d+(?:\.\d+)?)\s+(\d+)/(\d+)$", s)
    if mixed_match:
        try:
            whole = float(mixed_match.group(1))
            numerator = float(mixed_match.group(2))
            denominator = float(mixed_match.group(3))
            if denominator == 0:
                return None
            result = whole + numerator / denominator
            if result > 0 and math.isfinite(result):
                return result
        except (ValueError, ZeroDivisionError):
            return None
        return None

    # Try simple fraction (e.g., "3/4")
    frac_match = re.match(r"^(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)$", s)
    if frac_match:
        try:
            numerator = float(frac_match.group(1))
            denominator = float(frac_match.group(2))
            if denominator == 0:
                return None
            result = numerator / denominator
            if result > 0 and math.isfinite(result):
                return result
        except ValueError:
            return None
        return None

    # Try decimal or integer
    try:
        result = float(s)
        if result > 0 and math.isfinite(result):
            return result
    except ValueError:
        return None

    return None


def parse_ingredient(text: str) -> dict:
    """Parse an ingredient line.

    Returns:
        {"quantity": float | None, "unit": str | None, "item": str, "note": str | None}

    Contract:
    - Never raises for non-blank input
    - item is always non-empty
    - quantity is either a positive finite float or None (never 0, negative, or non-finite)
    """
    # Start with a clean working copy
    working = text.strip()
    original = working  # Keep original for fallback

    # Default result
    quantity: Optional[float] = None
    unit: Optional[str] = None
    item: str = ""
    note: Optional[str] = None

    # Step 1: Check for "to taste" anywhere in the text (this nulls quantity).
    # Detect and remove with the same pattern so they cannot disagree.
    to_taste_found = False
    if _TO_TASTE_RE.search(working):
        to_taste_found = True
        note = "to taste"
        working = _TO_TASTE_RE.sub("", working)
        working = " ".join(working.split())  # collapse whitespace left behind

    # Step 2: Extract parenthetical notes (anywhere, not just trailing)
    # Look for any (...)  in the text
    paren_match = re.search(r"\(([^)]+)\)", working)
    if paren_match and note is None:  # Only extract if we haven't found "to taste"
        note = paren_match.group(1).strip()
        # Remove the parenthetical from working
        working = working[: paren_match.start()] + " " + working[paren_match.end() :]
        working = " ".join(working.split())  # Normalize whitespace

    # Step 3: Try to extract leading number (quantity)
    # First, check for vulgar fraction at the start
    if working:
        first_char = working[0]
        if first_char in _VULGAR_FRACTIONS:
            parsed_qty = _parse_number(first_char)
            if parsed_qty is not None:
                quantity = parsed_qty
                working = working[1:].strip()

    # Try to parse a number at the start (if we haven't found quantity yet)
    if quantity is None and working:
        # Look for a number pattern at the start
        # Matches: 123, 1.5, 1/2, 1 1/2
        number_pattern = r"^(?:(\d+(?:\.\d+)?)\s+(\d+)/(\d+)|(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?))"
        match = re.match(number_pattern, working)
        if match:
            if match.group(1):  # Mixed number
                number_str = match.group(0)
                parsed_qty = _parse_number(number_str)
            elif match.group(4):  # Simple fraction
                number_str = match.group(0)
                parsed_qty = _parse_number(number_str)
            else:  # Integer or decimal
                number_str = match.group(6)
                parsed_qty = _parse_number(number_str)

            if parsed_qty is not None:
                quantity = parsed_qty
                working = working[len(number_str) :].strip()

    # Step 4: Extract unit (if we have a quantity).
    # The word(s) immediately after the number, if a known or opaque unit token.
    # Try a two-word synonym first ("fl oz") before the single leading token.
    if quantity is not None and working:
        tokens = working.split()
        matched = None
        consumed = 0
        if len(tokens) >= 2 and _is_unit_word(f"{tokens[0]} {tokens[1]}"):
            matched, consumed = f"{tokens[0]} {tokens[1]}", 2
        elif tokens and _is_unit_word(tokens[0]):
            matched, consumed = tokens[0], 1

        if matched is not None:
            # Store as it appeared: lower-cased, one trailing "." stripped.
            unit = matched.lower()
            if unit.endswith("."):
                unit = unit[:-1]
            working = " ".join(tokens[consumed:]).strip()

    # Step 5: Everything left is item
    item = working.strip() if working else ""

    # Step 6: Ensure item is not empty
    # If item is empty, use the original text as fallback
    if not item:
        item = original.strip()

    # If still empty, use a generic fallback
    if not item:
        item = "ingredient"

    # Step 7: If "to taste" was found, null the quantity (even if one was parsed)
    if to_taste_found:
        quantity = None

    return {
        "quantity": quantity,
        "unit": unit,
        "item": item,
        "note": note,
    }
