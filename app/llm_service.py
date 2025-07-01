import json
import logging
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field

try:
    from langchain_openai import ChatOpenAI
    from langchain.schema import HumanMessage, SystemMessage
    from langchain.output_parsers import PydanticOutputParser
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    logging.warning("LangChain not available, falling back to basic OpenAI")

from .config import get_settings
from .models import NameSuggestion # Import from the canonical source

logger = logging.getLogger(__name__)
settings = get_settings()

class StructuredLLMResponse(BaseModel):
    """Complete response with summarized conflicts and name suggestions."""
    summarized_conflicts: List[str] = Field(
        description="A list of crisp, user-friendly points summarizing the blocking issues."
    )
    recommended_names: List[NameSuggestion] = Field(
        description="List of 5 alternative company names",
        min_items=3,
        max_items=7
    )

class StructuredLLMService:
    """Enhanced LLM service using LangChain for structured responses."""
    
    def __init__(self):
        self.model_fast = settings.openai_model_fast
        self.model_smart = settings.openai_model_smart
        
        if LANGCHAIN_AVAILABLE:
            self.llm_fast = ChatOpenAI(
                model=self.model_fast,
                temperature=0.7,
                openai_api_key=settings.openai_api_key
            )
            self.llm_smart = ChatOpenAI(
                model=self.model_smart,
                temperature=0.7,
                openai_api_key=settings.openai_api_key
            )
        else:
            self.llm_fast = None
            self.llm_smart = None

    def _create_system_prompt(self) -> str:
        """Create a comprehensive system prompt for name suggestion task."""
        return """You are a senior business naming consultant with 15+ years of experience in Indian corporate law and MCA registrations.

EXPERTISE AREAS:
- Indian Companies Act 2013 and Incorporation Rules 2014
- Trademark law and intellectual property conflicts
- Brand strategy and market positioning

CORE OBJECTIVES:
Your first task is to analyze the provided list of raw conflict messages. Summarize and rephrase them into a few crisp, user-friendly points. Focus on the core issue and what it means for the user.

Your second task is to provide 5 strategically crafted alternative company names that resolve these legal conflicts while enhancing brand potential.

CRITICAL COMPLIANCE REQUIREMENTS:
1. LEGAL SAFETY: Names must pass MCA approval with high probability
2. DISTINCTIVENESS: Avoid phonetic, visual, or conceptual similarity to conflicting names
3. TRADEMARK CLEARANCE: Steer clear of protected words and phrases
4. PROFESSIONAL STANDARDS: Names should sound established and trustworthy
5. BUSINESS ALIGNMENT: Preserve industry focus and target market appeal

RESPONSE QUALITY STANDARDS:
- Each name suggestion must include a strategic rationale.
- The conflict summary must be concise and easy to understand.
- Prioritize names that can scale with business growth.

REASONING REQUIREMENTS:
For each suggestion, explain:
1. How it differs from conflicting names
2. Why it maintains business relevance
3. Strategic advantages for brand development"""

    def _create_user_prompt(self, context: Dict[str, Any], blocking_messages: List[str]) -> str:
        """Create the user prompt with context and blocking messages."""
        base_name = context.get("base_name", "")
        check_type = context.get("check_type", "company")

        prompt = f"""A client wants to register a {check_type} with the name "{base_name}" but it has conflicts.

RAW CONFLICT MESSAGES FROM PORTAL:
{chr(10).join(f"- {msg}" for msg in blocking_messages)}

TASK:
1.  Summarize the key issues from the raw messages above into a clear, concise list.
2.  Based on these issues, suggest 5 alternative {check_type} names that resolve the conflicts.

Provide the response in the exact JSON format specified in the schema."""
        
        return prompt

    async def get_analysis_and_suggestions(self, context: Dict[str, Any], blocking_messages: List[str], max_retries: int = 2) -> Dict[str, Any]:
        """Generate analysis and alternative name suggestions using a structured approach."""
        
        if not LANGCHAIN_AVAILABLE or not self.llm_fast:
            logger.warning("LangChain not available, using fallback mock response")
            return {
                "summarized_conflicts": ["Could not connect to the analysis service."],
                "recommended_names": self._fallback_suggestions(context),
            }

        # Set up structured output parser
        parser = PydanticOutputParser(pydantic_object=StructuredLLMResponse)
        
        system_prompt = self._create_system_prompt()
        user_prompt = self._create_user_prompt(context, blocking_messages)
        
        # Add format instructions to user prompt
        format_instructions = parser.get_format_instructions()
        full_user_prompt = f"{user_prompt}\n\nFORMAT INSTRUCTIONS:\n{format_instructions}"
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=full_user_prompt)
        ]
        
        current_llm = self.llm_fast
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Attempting analysis and suggestion generation (attempt {attempt})")
                
                # Get response from LLM
                response = await current_llm.ainvoke(messages)
                content = response.content.strip()
                
                # Parse structured response
                parsed_response = parser.parse(content)
                
                logger.info(f"Successfully generated analysis and {len(parsed_response.recommended_names)} name suggestions")
                # Return the Pydantic object directly
                return parsed_response
                
            except Exception as exc:
                logger.error(f"LLM call failed (attempt {attempt}): {exc}")
                
                if attempt == max_retries:
                    logger.info("All LLM attempts failed, using fallback suggestions")
                    return {
                        "summarized_conflicts": ["Analysis failed. Please check the raw error messages."],
                        "recommended_names": self._fallback_suggestions(context),
                    }
                    
                # Switch to smarter model for retry
                current_llm = self.llm_smart
        
        return {
            "summarized_conflicts": ["An unexpected error occurred during analysis."],
            "recommended_names": self._fallback_suggestions(context),
        }

    def _fallback_suggestions(self, context: Dict[str, Any]) -> List[Dict[str, str]]:
        """Provide fallback suggestions when LLM calls fail."""
        base_name = context.get("base_name", "Business")
        
        # Extract key words from base name for better suggestions
        words = base_name.lower().split()
        key_words = [w for w in words if w not in ['private', 'limited', 'ltd', 'pvt', 'company', 'services']]
        
        if 'digital' in base_name.lower() or 'tech' in base_name.lower():
            return [
                {"name": "Digital Innovation Solutions Private Limited", "reason": "Emphasizes innovation in digital technology"},
                {"name": "Advanced Digital Services Private Limited", "reason": "Highlights advanced digital capabilities"},
                {"name": "Digital Excellence Partners Private Limited", "reason": "Focuses on excellence and partnership"},
                {"name": "NextGen Digital Solutions Private Limited", "reason": "Suggests next-generation digital services"},
                {"name": "Digital Transformation Hub Private Limited", "reason": "Emphasizes digital transformation expertise"},
            ]
        elif 'bharat' in base_name.lower() or 'india' in base_name.lower():
            return [
                {"name": "Bharat Innovation Technologies Private Limited", "reason": "Combines Indian identity with technology focus"},
                {"name": "Digital Bharat Solutions Private Limited", "reason": "Maintains Bharat identity with solution focus"},
                {"name": "Bharat Tech Ventures Private Limited", "reason": "Emphasizes technology and business ventures"},
                {"name": "New Bharat Digital Private Limited", "reason": "Suggests modern digital services for India"},
                {"name": "Bharat Excellence Services Private Limited", "reason": "Focuses on service excellence with Indian identity"},
            ]
        else:
            # Generic business suggestions
            key_word = key_words[0] if key_words else "Business"
            return [
                {"name": f"{key_word.title()} Solutions Private Limited", "reason": "Professional solution-focused approach"},
                {"name": f"Advanced {key_word.title()} Services Private Limited", "reason": "Emphasizes advanced service capabilities"},
                {"name": f"{key_word.title()} Excellence Private Limited", "reason": "Focuses on excellence in the business domain"},
                {"name": f"Professional {key_word.title()} Partners Private Limited", "reason": "Highlights professional partnership approach"},
                {"name": f"{key_word.title()} Innovation Hub Private Limited", "reason": "Suggests innovation and collaborative workspace"},
            ]

# Global service instance
llm_service = StructuredLLMService()

async def get_analysis_and_suggestions(context: Dict[str, Any], blocking_messages: List[str], max_retries: int = 2) -> Dict[str, Any]:
    """Main interface for generating analysis and alternative names."""
    return await llm_service.get_analysis_and_suggestions(context, blocking_messages, max_retries) 