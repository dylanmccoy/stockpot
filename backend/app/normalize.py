"""Pure normalization module for ingredient names.

Implements deterministic name normalization per spec.md §2.1.
"""

import re

# Leading descriptors that are stripped from the start of a name (step 4).
LEADING_DESCRIPTORS = {
    "diced",
    "chopped",
    "minced",
    "sliced",
    "shredded",
    "grated",
    "crushed",
    "cubed",
    "julienned",
    "large",
    "small",
    "medium",
    "jumbo",
    "boneless",
    "skinless",
    "ripe",
    "peeled",
}


def _singularize_token(tok: str) -> str:
    """Singularize a single token via the spec.md §2.1 step 5 rule.

    Applied to the final token only in normalize_name, but also used by
    units.normalize_unit_token on the whole (lowered, stripped) string.
    """
    # Irregular map first
    irregular_map = {
        "tomatoes": "tomato",
        "potatoes": "potato",
        "leaves": "leaf",
        "loaves": "loaf",
        "halves": "half",
        "knives": "knife",
        "wolves": "wolf",
    }

    if tok in irregular_map:
        return irregular_map[tok]

    # -ies → -y
    if tok.endswith("ies"):
        return tok[:-3] + "y"

    # -ses / -xes / -zes / -ches / -shes → drop -es
    if tok.endswith(("ses", "xes", "zes", "ches", "shes")):
        return tok[:-2]

    # -oes → -o
    if tok.endswith("oes"):
        return tok[:-2]

    # trailing -s (but not -ss) → drop the -s
    if tok.endswith("s") and not tok.endswith("ss"):
        return tok[:-1]

    # otherwise unchanged
    return tok


def normalize_name(raw: str) -> str:
    """Normalize an ingredient name per spec.md §2.1 pipeline.

    Steps:
    1. strip and lowercase
    2. drop punctuation (except spaces and hyphens)
    3. collapse whitespace
    4. strip leading descriptor tokens
    5. singularize the final token only
    6. return (empty string is valid)
    """
    # Step 1: strip and lowercase
    s = raw.strip().lower()

    # Step 2: drop punctuation, keep spaces and hyphens
    s = re.sub(r"[^\w\s-]", "", s)

    # Step 3: collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()

    # Step 4: strip leading descriptor tokens
    tokens = s.split()
    while tokens and tokens[0] in LEADING_DESCRIPTORS:
        tokens.pop(0)
    s = " ".join(tokens)

    # Step 5: singularize the final token only
    if s:
        tokens = s.split()
        if tokens:
            tokens[-1] = _singularize_token(tokens[-1])
            s = " ".join(tokens)

    # Step 6: return
    return s
