from typing import Dict, List, Tuple
from rapidfuzz import fuzz

from .models import NameCheckPayload


def simplify_trademarks(words: List[str], threshold: int = 85) -> List[str]:
    """Deduplicate by fuzzy similarity (ratio > threshold) in LOWERCASE."""
    uniq: Dict[str, None] = {}
    for word in words:
        key = word.lower()
        if not any(fuzz.ratio(key, k) > threshold for k in uniq.keys()):
            uniq[key] = None
    return list(uniq.keys())


def analyse_payload(payload: NameCheckPayload) -> dict:
    """Return compact context dict for LLM prompt."""
    simplified_names = simplify_trademarks(payload.names)
    return {
        "names": simplified_names,
        "check_type": payload.check_type,
        "preferred_language": payload.preferred_language,
    } 