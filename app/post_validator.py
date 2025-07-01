from typing import List

from .models import NameCheckResult, NameSuggestion
from .preprocessor import simplify_trademarks


def validate_suggestions(payload_names: List[str], result: NameCheckResult) -> NameCheckResult:
    """Filter out suggestions too similar to original names."""
    original = simplify_trademarks(payload_names)
    filtered: List[NameSuggestion] = []
    for sugg in result.recommended_names:
        if sugg.name.lower() not in original:
            filtered.append(sugg)
    result.recommended_names = filtered
    return result 