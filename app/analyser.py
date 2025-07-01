from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .models import NameSuggestion, NameCheckResult


class ConflictAnalyser:
    """Parse MCA-style conflict JSON and produce structured verdict + context."""

    def __init__(self, data: Dict[str, Any]):
        self.data = data
        # Correctly use "error" key from incoming JSON, with fallback to "error_list"
        self.errors = data.get("error", data.get("error_list", []))
        self.name_similarity = data.get("name_similarity", [])
        self.trademarks = data.get("trademark", [])

    @property
    def base_name(self) -> str:
        # Infer proposed name from first name_similarity row, with robust checking.
        if self.name_similarity and len(self.name_similarity) > 0 and self.name_similarity[0]:
            return self.name_similarity[0][0]
        
        # Fallback for old format or different structures.
        if self.errors:
            first_error = self.errors[0]
            if isinstance(first_error, dict):
                # New format: "message": "Proposed name... PRO DIGITAL BHARAT SERVICES ..."
                # This is not a reliable way to get the name, but it's a fallback.
                # A better approach would be to have a dedicated 'proposed_name' field in the payload.
                pass  # Cannot reliably extract from message
            elif isinstance(first_error, list) and len(first_error) > 1:
                return first_error[1] # Old list-based format

        return "Unknown" # Return a default if no name can be found

    def has_blocking_error(self) -> bool:
        for row in self.errors:
            if not row:
                continue
            # Handle both dict and list formats for resilience
            severity = ""
            if isinstance(row, dict):
                severity = str(row.get("severity", "info")).lower()
            elif isinstance(row, list) and row:
                severity = str(row[0]).lower()
            
            if severity not in ["info", "success"]:
                return True
        return False

    def conflict_messages(self) -> List[str]:
        return [str(row[2]) for row in self.errors if len(row) > 2]

    def raw_blocking_messages(self) -> List[str]:
        messages = []
        for row in self.errors:
            if not row:
                continue
            
            if isinstance(row, dict):
                if msg := row.get("message"):
                    messages.append(str(msg))
            elif isinstance(row, list) and len(row) > 2:
                messages.append(str(row[2]))
        return messages

    def similar_names(self) -> List[str]:
        return [row[0] for row in self.name_similarity if row]

    def trademark_words(self) -> List[str]:
        words = []
        for row in self.trademarks:
            # Add defensive check for list type and content
            if isinstance(row, list) and len(row) > 0:
                words.append(str(row[0]))
        return words

    # === High-level API ===
    async def analyse_async(self, check_type: str = "company") -> NameCheckResult:
        if not self.has_blocking_error():
            return NameCheckResult(
                verdict="VALID",
                blocking_messages=[],  # Should be empty for valid names
                recommended_names=[],
            )

        # Need alternatives
        raw_messages = self.raw_blocking_messages()
        context = {
            "base_name": self.base_name,
            "check_type": check_type,
            "similar_names": self.similar_names()[:20],  # truncate to keep prompt small
            "trademark_words": self.trademark_words()[:20],
        }
        from .llm_service import get_analysis_and_suggestions  # avoid circular import

        llm_output = await get_analysis_and_suggestions(context, raw_messages)

        return NameCheckResult(
            verdict="NOT VALID",
            blocking_messages=llm_output.summarized_conflicts,
            recommended_names=llm_output.recommended_names,
        )

    # Synchronous wrapper for non-async callers
    def analyse(self, check_type: str = "company") -> NameCheckResult:
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Running within existing event loop; create task and wait
            return asyncio.run_coroutine_threadsafe(self.analyse_async(check_type), loop).result()
        else:
            return asyncio.run(self.analyse_async(check_type)) 