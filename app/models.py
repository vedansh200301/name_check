from typing import List, Literal, Optional
from pydantic import BaseModel, Field, validator


class NameCheckPayload(BaseModel):
    names: List[str] = Field(..., min_items=1, max_items=50, description="Candidate names to evaluate")
    check_type: Literal["company", "trademark"] = Field(..., description="Kind of name check to perform")
    preferred_language: Optional[str] = "en"

    @validator("names", each_item=True)
    def no_empty(cls, v: str):
        if not v.strip():
            raise ValueError("Name cannot be empty or whitespace")
        return v


class NameSuggestion(BaseModel):
    name: str
    reason: Optional[str] = None


class NameCheckResult(BaseModel):
    verdict: Literal["VALID", "NOT VALID"]
    blocking_messages: List[str] = []
    recommended_names: List[NameSuggestion] = [] 