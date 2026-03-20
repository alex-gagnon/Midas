def parse_float(s: str) -> float:
    """Strip whitespace/commas and parse as float; return 0.0 on failure."""
    try:
        return float(str(s).strip().replace(",", ""))
    except (ValueError, TypeError):
        return 0.0


def parse_dollar(s: str) -> float:
    """Strip $, +, whitespace/commas and parse as float; return 0.0 on failure."""
    try:
        return float(str(s).strip().lstrip("$").lstrip("+").replace(",", ""))
    except (ValueError, TypeError):
        return 0.0
